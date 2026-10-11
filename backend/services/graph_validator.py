"""Graph topology and routability validation service."""

import logging
from typing import Any
import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.database import sync_engine
from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus

logger = logging.getLogger(__name__)


class GraphValidator:
    """Validates topology, directionality, and routability of the persisted road graph."""

    def __init__(self, session: Session | None = None):
        self.session = session or Session(sync_engine)
        self._own_session = session is None

    def build_networkx_graph(self) -> nx.DiGraph:
        """Constructs a directed graph directly from PostgreSQL/PostGIS tables."""
        G = nx.DiGraph()

        # Load nodes
        nodes = self.session.execute(select(RoadNode)).scalars().all()
        for n in nodes:
            G.add_node(
                n.id,
                osm_id=n.osm_node_id,
                lon=n.longitude,
                lat=n.latitude,
                elevation=n.elevation_m,
            )

        # Load edges and operational status
        query = select(RoadSegment, RoadSegmentState).outerjoin(
            RoadSegmentState, RoadSegment.id == RoadSegmentState.road_segment_id
        )
        results = self.session.execute(query).all()

        for seg, st in results:
            current_status = st.status if st else RoadStatus.UNKNOWN.value
            current_score = st.safety_score if st else 100.0

            # Weight for distance-based shortest path
            G.add_edge(
                seg.u_node_id,
                seg.v_node_id,
                id=seg.id,
                osm_way_id=seg.osm_way_id,
                length_m=seg.length_m,
                weight=seg.length_m,
                base_travel_time_s=seg.base_travel_time_s,
                road_class=seg.road_class,
                oneway=seg.oneway,
                status=current_status,
                safety_score=current_score,
            )

        return G

    def validate(self) -> dict[str, Any]:
        """Runs comprehensive graph topology diagnostics."""
        G = self.build_networkx_graph()

        node_count = G.number_of_nodes()
        edge_count = G.number_of_edges()

        if node_count == 0 or edge_count == 0:
            return {
                "valid": False,
                "node_count": node_count,
                "edge_count": edge_count,
                "message": "Graph is empty. Please run the OSM importer first.",
            }

        # Analyze connected components
        weakly_connected = list(nx.weakly_connected_components(G))
        strongly_connected = list(nx.strongly_connected_components(G))
        largest_wcc = max(weakly_connected, key=len)

        # Check directionality / one-way constraints
        oneway_edges = [
            (u, v, data) for u, v, data in G.edges(data=True) if data.get("oneway") is True
        ]
        # For one-way edges, ensure reverse edge does not exist with the same oneway tag
        oneway_violations = 0
        for u, v, data in oneway_edges:
            if G.has_edge(v, u) and G[v][u].get("id") == data.get("id"):
                oneway_violations += 1

        # Test sample path within the largest component
        path_test = None
        if len(largest_wcc) >= 2:
            wcc_nodes = list(largest_wcc)
            start_node = wcc_nodes[0]
            # Find a reachable target node
            for target_node in wcc_nodes[1:20]:
                if nx.has_path(G, start_node, target_node):
                    path = nx.dijkstra_path(G, start_node, target_node, weight="weight")
                    length = nx.dijkstra_path_length(G, start_node, target_node, weight="weight")
                    path_test = {
                        "source": start_node,
                        "target": target_node,
                        "hops": len(path) - 1,
                        "distance_m": round(length, 2),
                        "path_node_ids": path,
                    }
                    break

        return {
            "valid": True,
            "node_count": node_count,
            "edge_count": edge_count,
            "weakly_connected_components": len(weakly_connected),
            "largest_component_size": len(largest_wcc),
            "strongly_connected_components": len(strongly_connected),
            "oneway_edges_count": len(oneway_edges),
            "oneway_violations": oneway_violations,
            "sample_path": path_test,
        }

    def close(self):
        if self._own_session:
            self.session.close()
