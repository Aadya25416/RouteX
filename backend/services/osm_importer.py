"""OpenStreetMap road network ingestion service preserving graph topology and directionality."""

import logging
import os
from pathlib import Path
from typing import Any
import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import Settings, get_settings
from backend.database import sync_engine
from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus

logger = logging.getLogger(__name__)

# Default base speed estimations in km/h by road classification
DEFAULT_SPEED_BY_CLASS: dict[str, float] = {
    "motorway": 80.0,
    "trunk": 60.0,
    "primary": 50.0,
    "secondary": 40.0,
    "tertiary": 30.0,
    "residential": 25.0,
    "service": 20.0,
    "track": 15.0,
    "unclassified": 30.0,
}


def parse_speed(speed_val: Any, default_speed: float) -> float:
    """Parses maxspeed attribute which can be a string, list, or None."""
    if not speed_val:
        return default_speed
    if isinstance(speed_val, list):
        speed_val = speed_val[0]
    if isinstance(speed_val, (int, float)):
        return float(speed_val)
    if isinstance(speed_val, str):
        # Extract numeric prefix if present (e.g. '50 mph' or '40')
        parts = speed_val.split()
        if parts:
            try:
                num = float(parts[0])
                if "mph" in speed_val.lower():
                    return num * 1.60934
                return num
            except ValueError:
                pass
    return default_speed


class OSMImporter:
    """Ingests OpenStreetMap road network into PostGIS preserving topology and directionality."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def fetch_graph(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        network_type: str | None = None,
        cache_path: str | Path | None = None,
    ) -> nx.MultiDiGraph:
        """
        Retrieves a directed road network graph from OSM or local GraphML cache.
        bbox format: (south, west, north, east).
        OSMnx 2.x bbox argument format: (left, bottom, right, top) = (west, south, east, north).
        """
        bbox = bbox or self.settings.corridor_bbox
        network_type = network_type or self.settings.OSM_NETWORK_TYPE
        south, west, north, east = bbox

        if cache_path and os.path.exists(cache_path):
            logger.info(f"Loading cached graph from {cache_path}")
            return ox.load_graphml(cache_path)

        logger.info(
            f"Fetching OSM road graph for bbox: S={south}, W={west}, N={north}, E={east} "
            f"network_type='{network_type}' (Attribution: © OpenStreetMap contributors under ODbL)"
        )

        # In OSMnx 2.x, bbox is (left, bottom, right, top) = (west, south, east, north)
        ox_bbox = (west, south, east, north)
        graph = ox.graph_from_bbox(
            bbox=ox_bbox,
            network_type=network_type,
            simplify=True,
            retain_all=False,
            truncate_by_edge=True,
        )

        if cache_path:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            logger.info(f"Saving graph cache to {cache_path}")
            ox.save_graphml(graph, cache_path)

        return graph

    def persist_graph(
        self,
        graph: nx.MultiDiGraph,
        corridor_name: str | None = None,
        session: Session | None = None,
    ) -> dict[str, int]:
        """
        Persists graph nodes and edges into PostgreSQL/PostGIS.
        Ensures stable canonical IDs, directed topology, and UNKNOWN initial operational state.
        """
        corridor_name = corridor_name or self.settings.CORRIDOR_NAME
        own_session = False
        if session is None:
            session = Session(sync_engine)
            own_session = True

        nodes_created = 0
        nodes_updated = 0
        edges_created = 0
        edges_updated = 0

        try:
            logger.info(f"Persisting {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges...")

            # 1. Process and persist canonical nodes
            for osmid, data in graph.nodes(data=True):
                node_id = f"node_osm_{osmid}"
                lon = float(data["x"])
                lat = float(data["y"])
                elev = float(data.get("elevation", 0.0)) if "elevation" in data else None
                geom_ewkt = f"SRID=4326;POINT({lon} {lat})"

                existing_node = session.get(RoadNode, node_id)
                if existing_node:
                    existing_node.osm_node_id = int(osmid)
                    existing_node.geom = geom_ewkt
                    existing_node.longitude = lon
                    existing_node.latitude = lat
                    existing_node.elevation_m = elev
                    nodes_updated += 1
                else:
                    new_node = RoadNode(
                        id=node_id,
                        osm_node_id=int(osmid),
                        geom=geom_ewkt,
                        longitude=lon,
                        latitude=lat,
                        elevation_m=elev,
                    )
                    session.add(new_node)
                    nodes_created += 1

            session.flush()

            # 2. Process and persist directed edges and their initial UNKNOWN states
            for u, v, k, data in graph.edges(keys=True, data=True):
                u_node_id = f"node_osm_{u}"
                v_node_id = f"node_osm_{v}"
                edge_id = f"edge_{u}_{v}_{k}"

                osm_way_id_raw = data.get("osmid")
                osm_way_id = int(osm_way_id_raw[0] if isinstance(osm_way_id_raw, list) else osm_way_id_raw) if osm_way_id_raw else None

                name_raw = data.get("name")
                name = str(name_raw[0] if isinstance(name_raw, list) else name_raw) if name_raw else None

                highway_raw = data.get("highway", "unclassified")
                road_class = str(highway_raw[0] if isinstance(highway_raw, list) else highway_raw)

                length_m = float(data.get("length", 10.0))
                default_spd = DEFAULT_SPEED_BY_CLASS.get(road_class, 30.0)
                speed_kmh = parse_speed(data.get("maxspeed"), default_spd)
                speed_m_s = max(speed_kmh * (1000.0 / 3600.0), 1.0)
                travel_time_s = length_m / speed_m_s

                oneway = bool(data.get("oneway", False))
                access_val = data.get("access", "yes")
                access_allowed = access_val not in ["no", "private"]
                bridge = bool(data.get("bridge", False))
                tunnel = bool(data.get("tunnel", False))

                # Geometry: use line geometry if available, otherwise line between endpoints
                geom_obj = data.get("geometry")
                if geom_obj is None:
                    u_node = graph.nodes[u]
                    v_node = graph.nodes[v]
                    geom_obj = LineString([(u_node["x"], u_node["y"]), (v_node["x"], v_node["y"])])

                coords_str = ", ".join([f"{x} {y}" for x, y in geom_obj.coords])
                geom_ewkt = f"SRID=4326;LINESTRING({coords_str})"

                existing_edge = session.get(RoadSegment, edge_id)
                if existing_edge:
                    existing_edge.osm_way_id = osm_way_id
                    existing_edge.u_node_id = u_node_id
                    existing_edge.v_node_id = v_node_id
                    existing_edge.key = int(k)
                    existing_edge.geom = geom_ewkt
                    existing_edge.length_m = length_m
                    existing_edge.base_speed_kmh = speed_kmh
                    existing_edge.base_travel_time_s = travel_time_s
                    existing_edge.road_class = road_class
                    existing_edge.name = name
                    existing_edge.oneway = oneway
                    existing_edge.access_allowed = access_allowed
                    existing_edge.bridge = bridge
                    existing_edge.tunnel = tunnel
                    existing_edge.corridor_name = corridor_name
                    edges_updated += 1
                else:
                    new_edge = RoadSegment(
                        id=edge_id,
                        osm_way_id=osm_way_id,
                        u_node_id=u_node_id,
                        v_node_id=v_node_id,
                        key=int(k),
                        geom=geom_ewkt,
                        length_m=length_m,
                        base_speed_kmh=speed_kmh,
                        base_travel_time_s=travel_time_s,
                        road_class=road_class,
                        name=name,
                        oneway=oneway,
                        access_allowed=access_allowed,
                        bridge=bridge,
                        tunnel=tunnel,
                        corridor_name=corridor_name,
                    )
                    session.add(new_edge)
                    edges_created += 1

                # Ensure associated RoadSegmentState exists with status UNKNOWN
                existing_state = session.execute(
                    select(RoadSegmentState).where(RoadSegmentState.road_segment_id == edge_id)
                ).scalar_one_or_none()

                if not existing_state:
                    initial_state = RoadSegmentState(
                        road_segment_id=edge_id,
                        status=RoadStatus.UNKNOWN.value,  # Unknown status per PRD
                        safety_score=100.0,
                        disruption_probability=None,
                        score_confidence=None,
                        status_reason_codes=["initial_import"],
                        source_reference="osm_ingestion",
                    )
                    session.add(initial_state)

            session.commit()
            logger.info(
                f"Import completed successfully. "
                f"Nodes: {nodes_created} created, {nodes_updated} updated. "
                f"Edges: {edges_created} created, {edges_updated} updated."
            )

            return {
                "nodes_created": nodes_created,
                "nodes_updated": nodes_updated,
                "edges_created": edges_created,
                "edges_updated": edges_updated,
                "total_nodes": graph.number_of_nodes(),
                "total_edges": graph.number_of_edges(),
            }
        except Exception as exc:
            session.rollback()
            logger.error(f"Failed to persist road graph: {exc}")
            raise
        finally:
            if own_session:
                session.close()
