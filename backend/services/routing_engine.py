"""Routing Engine for NER-LINK.

Calculates distance-efficient and fastest-safe routes over the directed
road graph using PostGIS coordinate snapping, NetworkX multigraph routing,
and explicit road-state safety policies.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_AsGeoJSON, ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from geoalchemy2.shape import from_shape, to_shape
import networkx as nx
from shapely.geometry import LineString
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus
from backend.models.routing import RouteMode, RouteRecommendation
from backend.schemas.routing import RouteRecommendationResponse, SafetySummary, SnappedPoint

logger = logging.getLogger(__name__)


class RoutingEngine:
    """Core routing engine operating on directed graph topology with safety constraints."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def snap_coordinate_to_node(
        self,
        lat: float,
        lon: float,
        max_snapping_distance_m: float = 10000.0,
    ) -> SnappedPoint:
        """
        Snaps a WGS84 coordinate to the nearest routable RoadNode in PostGIS.
        Rejects coordinates that exceed max_snapping_distance_m from the network.
        """
        # Validate coordinates
        if not (-90.0 <= lat <= 90.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid latitude: {lat}. Must be between -90 and 90.",
            )
        if not (-180.0 <= lon <= 180.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid longitude: {lon}. Must be between -180 and 180.",
            )

        point_geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        dist_expr = ST_Distance(cast(RoadNode.geom, Geography), cast(point_geom, Geography))

        query = (
            select(
                RoadNode.id,
                RoadNode.latitude,
                RoadNode.longitude,
                dist_expr.label("distance_m"),
            )
            .order_by(dist_expr.asc())
            .limit(1)
        )

        res = await self.session.execute(query)
        row = res.first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Road network graph has no nodes loaded.",
            )

        node_id, n_lat, n_lon, distance_m = row
        if distance_m > max_snapping_distance_m:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Coordinates ({lat:.5f}, {lon:.5f}) are too far from a routable road "
                    f"({distance_m:.1f}m > limit {max_snapping_distance_m:.1f}m). Snapping rejected."
                ),
            )

        return SnappedPoint(
            node_id=node_id,
            distance_m=float(distance_m),
            latitude=float(n_lat),
            longitude=float(n_lon),
        )

    async def snap_coordinate_to_segment(
        self,
        lat: float,
        lon: float,
        max_distance_m: float = 2000.0,
    ) -> tuple[str | None, float | None]:
        """Snaps a GPS point to the nearest road segment for tracking."""
        point_geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        dist_expr = ST_Distance(cast(RoadSegment.geom, Geography), cast(point_geom, Geography))

        query = (
            select(
                RoadSegment.id,
                dist_expr.label("distance_m"),
            )
            .order_by(dist_expr.asc())
            .limit(1)
        )
        res = await self.session.execute(query)
        row = res.first()
        if not row:
            return None, None

        seg_id, dist_m = row
        if dist_m > max_distance_m:
            return None, float(dist_m)
        return seg_id, float(dist_m)

    async def load_graph(
        self,
        mode: RouteMode,
        require_verified_safe: bool = False,
    ) -> nx.MultiDiGraph:
        """
        Builds the active NetworkX MultiDiGraph from PostgreSQL, applying
        exclusion and penalty policies for road states.
        """
        G = nx.MultiDiGraph()

        # Load nodes
        nodes_res = await self.session.execute(select(RoadNode))
        for n in nodes_res.scalars().all():
            G.add_node(
                n.id,
                lat=n.latitude,
                lon=n.longitude,
                elevation=n.elevation_m,
            )

        # Load edges with states
        edges_query = select(RoadSegment, RoadSegmentState).outerjoin(
            RoadSegmentState, RoadSegment.id == RoadSegmentState.road_segment_id
        )
        edges_res = await self.session.execute(edges_query)

        for seg, st in edges_res.all():
            seg_status = st.status if st else RoadStatus.UNKNOWN.value
            safety_score = st.safety_score if st else 100.0

            # POLICY: Confirmed BLOCKED segments are ALWAYS excluded
            if seg_status == RoadStatus.BLOCKED.value:
                continue

            # POLICY: If require_verified_safe is requested, UNKNOWN is strictly excluded
            if require_verified_safe and seg_status == RoadStatus.UNKNOWN.value:
                continue

            # Calculate cost based on mode
            if mode == RouteMode.SHORTEST_DISTANCE:
                # Mode A: Shortest Distance
                # Length is primary cost; penalties applied for risk/restrictions
                base_cost = seg.length_m
                if seg_status == RoadStatus.AT_RISK.value:
                    cost = base_cost * 1.5
                elif seg_status == RoadStatus.RESTRICTED.value:
                    cost = base_cost * 2.0
                else:
                    cost = base_cost
            else:
                # Mode B: Fastest Safe (travel time in seconds with safety penalties)
                base_time = seg.base_travel_time_s
                if seg_status == RoadStatus.AT_RISK.value:
                    cost = base_time * 2.5
                elif seg_status == RoadStatus.RESTRICTED.value:
                    cost = base_time * 3.0
                elif seg_status == RoadStatus.UNKNOWN.value:
                    cost = base_time * 1.2
                else:
                    cost = base_time

            G.add_edge(
                seg.u_node_id,
                seg.v_node_id,
                key=seg.key,
                id=seg.id,
                cost=cost,
                length_m=seg.length_m,
                base_travel_time_s=seg.base_travel_time_s,
                status=seg_status,
                safety_score=safety_score,
                road_class=seg.road_class,
                oneway=seg.oneway,
            )

        return G

    async def calculate_route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        mode: RouteMode = RouteMode.SHORTEST_DISTANCE,
        trip_id: uuid.UUID | None = None,
        max_snapping_distance_m: float = 10000.0,
        require_verified_safe: bool = False,
        persist: bool = True,
        reason: str | None = None,
    ) -> RouteRecommendationResponse:
        """
        Calculates an admissible route between origin and destination.
        Snaps endpoints, computes path, derives safety metrics, and persists recommendation.
        """
        # 1. Snap origin and destination
        snapped_origin = await self.snap_coordinate_to_node(
            origin_lat, origin_lon, max_snapping_distance_m=max_snapping_distance_m
        )
        snapped_dest = await self.snap_coordinate_to_node(
            destination_lat, destination_lon, max_snapping_distance_m=max_snapping_distance_m
        )

        # 2. Build graph with policy constraints
        G = await self.load_graph(mode=mode, require_verified_safe=require_verified_safe)

        source_node = snapped_origin.node_id
        target_node = snapped_dest.node_id

        # Edge case: Same node
        if source_node == target_node:
            node_data = G.nodes.get(source_node, {})
            pt_coord = [node_data.get("lon", origin_lon), node_data.get("lat", origin_lat)]
            line_coords = [pt_coord, pt_coord]
            safety_summary = SafetySummary(
                safety_status="VERIFIED_SAFE",
                meets_safety_policy=True,
                reasons=["Origin and destination snap to the same road node."],
            )
            now = datetime.now(timezone.utc)
            geom_shapely = LineString(line_coords)
            geom_db = from_shape(geom_shapely, srid=4326)

            rec_id = None
            if persist:
                rec = RouteRecommendation(
                    trip_id=trip_id,
                    mode=mode.value,
                    ordered_segment_ids=[],
                    ordered_node_ids=[source_node],
                    snapped_origin_node_id=source_node,
                    snapped_destination_node_id=target_node,
                    snapped_origin_distance_m=snapped_origin.distance_m,
                    snapped_destination_distance_m=snapped_dest.distance_m,
                    route_geom=geom_db,
                    distance_m=0.0,
                    eta_seconds=0.0,
                    safety_score_summary=100.0,
                    safety_summary=safety_summary.model_dump(),
                    meets_safety_policy=True,
                    avoided_hazard_count=0,
                    reason=reason or "Zero-distance route (same node)",
                    computed_at=now,
                )
                self.session.add(rec)
                await self.session.commit()
                await self.session.refresh(rec)
                rec_id = rec.id

            return RouteRecommendationResponse(
                id=rec_id,
                trip_id=trip_id,
                mode=mode,
                snapped_origin=snapped_origin,
                snapped_destination=snapped_dest,
                ordered_node_ids=[source_node],
                ordered_segment_ids=[],
                route_geojson={"type": "LineString", "coordinates": line_coords},
                distance_m=0.0,
                eta_seconds=0.0,
                meets_safety_policy=True,
                safety_summary=safety_summary,
                avoided_hazard_count=0,
                reason=reason,
                computed_at=now,
            )

        # 3. Path finding
        if source_node not in G:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapped origin node '{source_node}' is disconnected from active graph.",
            )
        if target_node not in G:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapped destination node '{target_node}' is disconnected from active graph.",
            )

        try:
            path_nodes = nx.shortest_path(G, source=source_node, target=target_node, weight="cost")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            msg = (
                "NO_SAFE_ROUTE: No eligible routable path exists between "
                f"node {source_node} and node {target_node} under the '{mode.value}' policy."
            )
            if require_verified_safe:
                msg += " (Policy required verified safe edges only; UNKNOWN edges were excluded)."
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )

        # 4. Extract chosen edges lossless from MultiDiGraph
        chosen_segment_ids: list[str] = []
        total_distance_m = 0.0
        total_eta_seconds = 0.0
        unknown_segments: list[str] = []
        at_risk_segments: list[str] = []
        restricted_segments: list[str] = []
        score_sum = 0.0

        for u, v in zip(path_nodes[:-1], path_nodes[1:]):
            edges_uv = G[u][v]
            # Select edge with lowest cost
            best_key = min(edges_uv, key=lambda k: edges_uv[k].get("cost", float("inf")))
            edge = edges_uv[best_key]

            seg_id = edge["id"]
            chosen_segment_ids.append(seg_id)
            total_distance_m += edge["length_m"]
            total_eta_seconds += edge["base_travel_time_s"]
            score_sum += edge.get("safety_score", 100.0)

            st = edge.get("status", RoadStatus.UNKNOWN.value)
            if st == RoadStatus.UNKNOWN.value:
                unknown_segments.append(seg_id)
            elif st == RoadStatus.AT_RISK.value:
                at_risk_segments.append(seg_id)
            elif st == RoadStatus.RESTRICTED.value:
                restricted_segments.append(seg_id)

        avg_safety_score = score_sum / len(chosen_segment_ids) if chosen_segment_ids else 100.0

        # 5. Safety policy summary & disclosure
        reasons: list[str] = []
        meets_safety_policy = True
        safety_status = "VERIFIED_SAFE"
        disclaimer = None

        if unknown_segments:
            meets_safety_policy = False
            safety_status = "UNVERIFIED"
            reasons.append(f"Route traverses {len(unknown_segments)} unverified segments (UNKNOWN status).")
            disclaimer = (
                f"Caution: Route contains {len(unknown_segments)} segments without recent ground observations. "
                "Accessibility is unverified."
            )

        if at_risk_segments:
            meets_safety_policy = False
            if safety_status != "UNVERIFIED":
                safety_status = "AT_RISK"
            reasons.append(f"Route traverses {len(at_risk_segments)} segments flagged AT_RISK.")

        if restricted_segments:
            meets_safety_policy = False
            if safety_status not in ["UNVERIFIED", "AT_RISK"]:
                safety_status = "RESTRICTED"
            reasons.append(f"Route traverses {len(restricted_segments)} segments flagged RESTRICTED.")

        safety_summary = SafetySummary(
            safety_status=safety_status,
            meets_safety_policy=meets_safety_policy,
            unknown_segment_count=len(unknown_segments),
            at_risk_segment_count=len(at_risk_segments),
            restricted_segment_count=len(restricted_segments),
            blocked_segment_count=0,
            unknown_segments=unknown_segments,
            at_risk_segments=at_risk_segments,
            restricted_segments=restricted_segments,
            disclaimer=disclaimer,
            reasons=reasons,
        )

        # 6. Retrieve geometries in order and assemble route LineString
        # Fetch road segments geometries from DB in one query
        segs_res = await self.session.execute(
            select(
                RoadSegment.id,
                RoadSegment.u_node_id,
                RoadSegment.v_node_id,
                func.ST_AsGeoJSON(RoadSegment.geom).label("geojson"),
            ).where(RoadSegment.id.in_(chosen_segment_ids))
        )
        geom_map = {row.id: (row.u_node_id, row.v_node_id, json.loads(row.geojson)) for row in segs_res.all()}

        assembled_coords: list[list[float]] = []
        for i, seg_id in enumerate(chosen_segment_ids):
            u_id = path_nodes[i]
            v_id = path_nodes[i + 1]
            seg_info = geom_map.get(seg_id)
            if not seg_info:
                continue

            orig_u, orig_v, geojson_data = seg_info
            coords = geojson_data.get("coordinates", [])

            # Check if segment coordinates need reversal based on traversal direction
            if orig_u == v_id and orig_v == u_id:
                coords = list(reversed(coords))

            if assembled_coords and coords:
                # Avoid duplicating consecutive junction node coordinate
                if assembled_coords[-1] == coords[0]:
                    assembled_coords.extend(coords[1:])
                else:
                    assembled_coords.extend(coords)
            else:
                assembled_coords.extend(coords)

        if len(assembled_coords) < 2:
            # Fallback to straight line between snapped nodes
            n1 = G.nodes[source_node]
            n2 = G.nodes[target_node]
            assembled_coords = [[n1.get("lon", 0.0), n1.get("lat", 0.0)], [n2.get("lon", 0.0), n2.get("lat", 0.0)]]

        shapely_line = LineString(assembled_coords)
        db_line_geom = from_shape(shapely_line, srid=4326)
        now = datetime.now(timezone.utc)

        # 7. Persist route recommendation
        rec_id = None
        if persist:
            rec = RouteRecommendation(
                trip_id=trip_id,
                mode=mode.value,
                ordered_segment_ids=chosen_segment_ids,
                ordered_node_ids=path_nodes,
                snapped_origin_node_id=source_node,
                snapped_destination_node_id=target_node,
                snapped_origin_distance_m=snapped_origin.distance_m,
                snapped_destination_distance_m=snapped_dest.distance_m,
                route_geom=db_line_geom,
                distance_m=round(total_distance_m, 2),
                eta_seconds=round(total_eta_seconds, 2),
                safety_score_summary=round(avg_safety_score, 2),
                safety_summary=safety_summary.model_dump(),
                meets_safety_policy=meets_safety_policy,
                avoided_hazard_count=0,
                is_active=True,
                reason=reason or f"Calculated under mode {mode.value}",
                computed_at=now,
            )
            self.session.add(rec)
            await self.session.commit()
            await self.session.refresh(rec)
            rec_id = rec.id

        return RouteRecommendationResponse(
            id=rec_id,
            trip_id=trip_id,
            mode=mode,
            snapped_origin=snapped_origin,
            snapped_destination=snapped_dest,
            ordered_node_ids=path_nodes,
            ordered_segment_ids=chosen_segment_ids,
            route_geojson={"type": "LineString", "coordinates": assembled_coords},
            distance_m=round(total_distance_m, 2),
            eta_seconds=round(total_eta_seconds, 2),
            meets_safety_policy=meets_safety_policy,
            safety_summary=safety_summary,
            avoided_hazard_count=0,
            reason=reason,
            computed_at=now,
        )
