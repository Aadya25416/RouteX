"""Tests for OSM graph ingestion, topology preservation, directionality, and idempotency."""

import networkx as nx
import pytest
from shapely.geometry import LineString
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from backend.database import sync_engine
from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus
from backend.services.graph_validator import GraphValidator
from backend.services.osm_importer import OSMImporter


def create_mock_directed_graph() -> nx.MultiDiGraph:
    """
    Constructs a directed MultiDiGraph with explicit one-way and bidirectional edges:
    Node 101 -> Node 102: One-way edge (101 -> 102 only)
    Node 102 <-> Node 103: Bidirectional edge (102 -> 103 and 103 -> 102)
    Node 103 -> Node 104: One-way edge (103 -> 104 only)
    """
    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:4326"

    # Nodes around Guwahati (latitude ~26.15, longitude ~91.75)
    G.add_node(101, x=91.740, y=26.140, osmid=101)
    G.add_node(102, x=91.745, y=26.145, osmid=102)
    G.add_node(103, x=91.750, y=26.150, osmid=103)
    G.add_node(104, x=91.755, y=26.155, osmid=104)

    # 101 -> 102 (Oneway)
    G.add_edge(
        101,
        102,
        key=0,
        osmid=1001,
        name="MG Road OneWay",
        highway="primary",
        length=500.0,
        maxspeed="50",
        oneway=True,
        geometry=LineString([(91.740, 26.140), (91.745, 26.145)]),
    )

    # 102 <-> 103 (Two-way: both directions present in graph)
    G.add_edge(
        102,
        103,
        key=0,
        osmid=1002,
        name="GS Road TwoWay",
        highway="secondary",
        length=600.0,
        maxspeed="40",
        oneway=False,
        geometry=LineString([(91.745, 26.145), (91.750, 26.150)]),
    )
    G.add_edge(
        103,
        102,
        key=0,
        osmid=1002,
        name="GS Road TwoWay",
        highway="secondary",
        length=600.0,
        maxspeed="40",
        oneway=False,
        geometry=LineString([(91.750, 26.150), (91.745, 26.145)]),
    )

    # 103 -> 104 (Oneway)
    G.add_edge(
        103,
        104,
        key=0,
        osmid=1003,
        name="Zoo Road OneWay",
        highway="tertiary",
        length=700.0,
        maxspeed="30",
        oneway=True,
        geometry=LineString([(91.750, 26.150), (91.755, 26.155)]),
    )

    return G


def test_osm_import_topology_and_directionality():
    # Clean up test nodes if present
    with Session(sync_engine) as session:
        session.execute(text("DELETE FROM road_nodes WHERE id LIKE 'node_osm_10%';"))
        session.commit()

    graph = create_mock_directed_graph()
    importer = OSMImporter()

    # 1. First import
    results1 = importer.persist_graph(graph=graph, corridor_name="Test-Corridor")
    assert results1["nodes_created"] == 4
    assert results1["edges_created"] == 4

    # 2. Check Idempotency: re-running persist_graph should not create duplicate records
    results2 = importer.persist_graph(graph=graph, corridor_name="Test-Corridor")
    assert results2["nodes_created"] == 0
    assert results2["edges_created"] == 0
    assert results2["nodes_updated"] == 4
    assert results2["edges_updated"] == 4

    # 3. Verify Road Status convention: all imported roads must be UNKNOWN, not OPEN
    with Session(sync_engine) as session:
        states = session.execute(
            select(RoadSegmentState).where(RoadSegmentState.road_segment_id.like("edge_10%"))
        ).scalars().all()
        assert len(states) == 4
        for st in states:
            assert st.status == RoadStatus.UNKNOWN.value
            assert st.safety_score == 100.0

    # 4. Validate graph topology and directionality constraints
    validator = GraphValidator()
    try:
        report = validator.validate()
        assert report["valid"] is True
        assert report["node_count"] >= 4
        assert report["edge_count"] >= 4

        G = validator.build_networkx_graph()

        # Path 101 -> 104 MUST exist
        assert nx.has_path(G, "node_osm_101", "node_osm_104")
        forward_path = nx.dijkstra_path(G, "node_osm_101", "node_osm_104", weight="weight")
        assert forward_path == [
            "node_osm_101",
            "node_osm_102",
            "node_osm_103",
            "node_osm_104",
        ]

        # Reverse path 104 -> 101 MUST NOT exist because 101->102 and 103->104 are one-way!
        assert not nx.has_path(G, "node_osm_104", "node_osm_101")

        # Two-way segment between 102 and 103 MUST be traversable in both directions
        assert nx.has_path(G, "node_osm_102", "node_osm_103")
        assert nx.has_path(G, "node_osm_103", "node_osm_102")
    finally:
        validator.close()

    # Clean up test records
    with Session(sync_engine) as session:
        session.execute(text("DELETE FROM road_nodes WHERE id LIKE 'node_osm_10%';"))
        session.commit()
