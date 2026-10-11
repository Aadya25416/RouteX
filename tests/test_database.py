"""Tests for database connectivity, PostGIS functions, and schema constraints."""

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.roads import RoadNode, RoadSegment, RoadSegmentState, RoadStatus


@pytest.mark.asyncio
async def test_postgis_extension_and_spatial_query(db_session: AsyncSession):
    # Verify PostGIS version function works
    res = await db_session.execute(text("SELECT PostGIS_Version();"))
    version = res.scalar()
    assert version is not None
    assert "3." in version

    # Verify spatial distance calculation in PostGIS
    dist_res = await db_session.execute(
        text("SELECT ST_Distance(ST_MakePoint(91.7362, 26.1445)::geography, ST_MakePoint(91.8594, 27.5861)::geography);")
    )
    distance_meters = dist_res.scalar()
    assert distance_meters is not None
    assert distance_meters > 100000.0  # ~160km between Guwahati and Tawang area


@pytest.mark.asyncio
async def test_road_segment_state_safety_score_constraints(db_session: AsyncSession):
    # Clean up test nodes/segments if existing
    await db_session.execute(text("DELETE FROM road_nodes WHERE id LIKE 'test_node_%';"))
    await db_session.commit()

    # Create dummy nodes and edge
    node1 = RoadNode(
        id="test_node_1",
        geom="SRID=4326;POINT(91.73 26.14)",
        longitude=91.73,
        latitude=26.14,
    )
    node2 = RoadNode(
        id="test_node_2",
        geom="SRID=4326;POINT(91.74 26.15)",
        longitude=91.74,
        latitude=26.15,
    )
    db_session.add_all([node1, node2])
    await db_session.flush()

    edge = RoadSegment(
        id="test_edge_1",
        u_node_id="test_node_1",
        v_node_id="test_node_2",
        geom="SRID=4326;LINESTRING(91.73 26.14, 91.74 26.15)",
        length_m=100.0,
        base_travel_time_s=10.0,
        road_class="secondary",
        oneway=False,
    )
    db_session.add(edge)
    await db_session.flush()

    # Valid road state
    valid_state = RoadSegmentState(
        road_segment_id="test_edge_1",
        status=RoadStatus.UNKNOWN.value,
        safety_score=85.0,
        disruption_probability=0.15,
    )
    db_session.add(valid_state)
    await db_session.commit()

    # Verify saved state
    saved = await db_session.execute(
        select(RoadSegmentState).where(RoadSegmentState.road_segment_id == "test_edge_1")
    )
    st = saved.scalar_one()
    assert st.status == "UNKNOWN"
    assert st.safety_score == 85.0
    assert st.disruption_probability == 0.15

    # Test invalid safety score > 100 violates CheckConstraint
    st.safety_score = 150.0
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Clean up
    await db_session.execute(text("DELETE FROM road_nodes WHERE id LIKE 'test_node_%';"))
    await db_session.commit()
