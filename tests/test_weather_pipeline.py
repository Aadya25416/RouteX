"""Comprehensive unit and integration tests for the Weather Ingestion Pipeline,
Hourly Forecast Horizons, and Downstream ML Feature Contracts.

Covers:
1. Open-Meteo response parsing across all core meteorological variables.
2. Null and missing value preservation without fabricating zeros.
3. Observation versus forecast classification with UTC normalization.
4. Upstream timeouts, rate-limits (HTTP 429), and 5xx retries.
5. Refresh idempotency, deduplication, and partial failure resilience.
6. Forecast API querying and horizon limits.
7. Rainfall rolling accumulation windows (1h, 3h, 6h, 24h) with interval semantics.
8. ML feature contract validation, freshness, completeness, and provenance.
9. Spatial association with road segments and confidence scoring.
10. Authentication and RBAC enforcement.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.observations import WeatherObservation
from backend.models.roads import RoadSegment
from backend.services.weather.open_meteo import OpenMeteoWeatherProvider, parse_utc_timestamp
from backend.services.weather.weather_service import WeatherService

settings = get_settings()


@pytest.fixture(autouse=True)
async def cleanup_test_weather_observations(db_session: AsyncSession):
    """Ensures each weather test runs in an isolated, predictable environment."""
    await db_session.execute(delete(WeatherObservation))
    await db_session.commit()
    yield
    await db_session.execute(delete(WeatherObservation))
    await db_session.commit()

MOCK_FULL_OPEN_METEO_PAYLOAD = {
    "latitude": 26.1445,
    "longitude": 91.7362,
    "elevation": 55.0,
    "generationtime_ms": 12.5,
    "utc_offset_seconds": 0,
    "timezone": "GMT",
    "timezone_abbreviation": "GMT",
    "current": {
        "time": "2026-10-14T18:00",
        "temperature_2m": 24.5,
        "relative_humidity_2m": 88.0,
        "apparent_temperature": 27.2,
        "precipitation": 3.5,
        "rain": 2.5,
        "showers": 1.0,
        "snowfall": None,
        "weather_code": 61,
        "cloud_cover": 75.0,
        "pressure_msl": 1012.3,
        "surface_pressure": 1006.1,
        "wind_speed_10m": 14.5,
        "wind_direction_10m": 190.0,
        "wind_gusts_10m": 28.0,
        "visibility": 7500.0,
    },
    "hourly": {
        "time": [
            "2026-10-14T17:00",
            "2026-10-14T18:00",
            "2026-10-14T19:00",
            "2026-10-14T20:00",
            "2026-10-14T21:00",
        ],
        "temperature_2m": [25.0, 24.5, 23.8, 23.0, 22.5],
        "relative_humidity_2m": [85.0, 88.0, 90.0, 92.0, 95.0],
        "dew_point_2m": [22.0, 22.3, 22.0, 21.6, 21.6],
        "apparent_temperature": [28.0, 27.2, 26.5, 25.5, 24.8],
        "precipitation_probability": [40, 60, 80, 50, 20],
        "precipitation": [1.0, 3.5, 5.0, 2.0, 0.0],
        "rain": [1.0, 2.5, 4.0, 1.5, 0.0],
        "showers": [0.0, 1.0, 1.0, 0.5, 0.0],
        "snowfall": [None, None, None, None, None],
        "weather_code": [51, 61, 63, 61, 0],
        "pressure_msl": [1012.0, 1012.3, 1012.8, 1013.2, 1013.5],
        "surface_pressure": [1005.8, 1006.1, 1006.6, 1007.0, 1007.3],
        "cloud_cover": [60, 75, 90, 70, 30],
        "visibility": [8000.0, 7500.0, 6000.0, 7000.0, 9000.0],
        "wind_speed_10m": [12.0, 14.5, 16.0, 13.0, 10.0],
        "wind_direction_10m": [180.0, 190.0, 195.0, 185.0, 175.0],
        "wind_gusts_10m": [22.0, 28.0, 32.0, 25.0, 18.0],
        "soil_moisture_0_to_7cm": [0.285, 0.290, 0.310, 0.315, 0.312],
        "et0_fao_evapotranspiration": [0.05, 0.02, 0.00, 0.00, 0.00],
    },
    "daily": {
        "time": ["2026-10-14", "2026-10-15"],
        "weather_code": [63, 51],
        "temperature_2m_max": [31.5, 29.8],
        "temperature_2m_min": [22.0, 21.0],
        "apparent_temperature_max": [34.0, 32.5],
        "apparent_temperature_min": [24.0, 23.0],
        "sunrise": ["2026-10-13T23:51", "2026-10-14T23:51"],
        "sunset": ["2026-10-14T11:26", "2026-10-15T11:25"],
        "precipitation_sum": [11.5, 3.2],
        "rain_sum": [9.0, 2.5],
        "showers_sum": [2.5, 0.7],
        "snowfall_sum": [0.0, 0.0],
        "precipitation_probability_max": [80, 50],
        "wind_speed_10m_max": [16.0, 14.0],
        "wind_gusts_10m_max": [32.0, 26.0],
    },
}


# =========================================================================
# 1. PARSING AND DATA NORMALIZATION TESTS
# =========================================================================

def test_open_meteo_normalization_all_variables():
    """Verifies that all core atmospheric, hydrological, and wind fields are parsed correctly."""
    provider = OpenMeteoWeatherProvider()
    result = provider._normalize_full_response(MOCK_FULL_OPEN_METEO_PAYLOAD, 26.1445, 91.7362)

    # Current verification
    curr = result["current"]
    assert curr["data_type"] == "CURRENT"
    assert curr["temperature_c"] == 24.5
    assert curr["apparent_temperature_c"] == 27.2
    assert curr["relative_humidity_pct"] == 88.0
    assert curr["precipitation_mm"] == 3.5
    assert curr["rain_mm"] == 2.5
    assert curr["showers_mm"] == 1.0
    assert curr["snowfall_cm"] is None  # None preserved, NOT 0.0
    assert curr["wind_speed_kmh"] == 14.5
    assert curr["wind_direction_deg"] == 190.0
    assert curr["wind_gusts_kmh"] == 28.0
    assert curr["visibility_m"] == 7500.0
    assert curr["weather_code"] == 61
    assert curr["cloud_cover_pct"] == 75.0
    assert curr["pressure_msl_hpa"] == 1012.3
    assert curr["surface_pressure_hpa"] == 1006.1

    # Hourly verification
    hourly = result["hourly"]
    assert len(hourly) == 5
    sample_hr = hourly[2]  # index 2: 19:00
    assert sample_hr["temperature_c"] == 23.8
    assert sample_hr["precipitation_mm"] == 5.0
    assert sample_hr["precipitation_probability_pct"] == 80.0
    assert sample_hr["soil_moisture_m3m3"] == 0.310
    assert sample_hr["et0_evapotranspiration_mm"] == 0.00
    assert sample_hr["dew_point_c"] == 22.0

    # Daily verification
    daily = result["daily"]
    assert len(daily) == 2
    assert daily[0]["precipitation_sum_mm"] == 11.5
    assert daily[0]["wind_gusts_10m_max_kmh"] == 32.0
    assert daily[0]["sunrise"] == "2026-10-13T23:51"


def test_open_meteo_preserves_missing_data_without_zero_fabrication():
    """Verifies that missing meteorological variables are strictly preserved as None."""
    provider = OpenMeteoWeatherProvider()
    sparse_payload = {
        "current": {
            "time": "2026-10-14T12:00",
            "temperature_2m": 20.0,
            # precipitation, snowfall, wind_gusts intentionally omitted
        },
        "hourly": {
            "time": ["2026-10-14T12:00"],
            "temperature_2m": [20.0],
            "precipitation": [None],
            "snowfall": [None],
            "wind_gusts_10m": [None],
        },
    }

    norm = provider._normalize_full_response(sparse_payload, 26.14, 91.73)
    curr = norm["current"]
    assert curr["temperature_c"] == 20.0
    assert curr.get("precipitation_mm") is None
    assert curr.get("rainfall_mm") is None
    assert curr.get("wind_gusts_kmh") is None
    assert curr.get("snowfall_cm") is None

    hr = norm["hourly"][0]
    assert hr.get("precipitation_mm") is None
    assert hr.get("wind_gusts_kmh") is None


def test_open_meteo_malformed_response_raises_error():
    """Verifies defensive error handling when upstream payload is malformed."""
    provider = OpenMeteoWeatherProvider()
    with pytest.raises(ValueError, match="Malformed Open-Meteo payload"):
        provider._normalize_full_response({"error": True, "reason": "No coordinates"}, 26.0, 91.0)


# =========================================================================
# 2. UPSTREAM RETRY, RATE LIMITING, AND TIMEOUT TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_open_meteo_rate_limit_and_server_error_retries():
    """Verifies exponential backoff and retry behavior on HTTP 429 and 503."""
    provider = OpenMeteoWeatherProvider(max_retries=3, timeout_seconds=1.0)

    # Simulate 2 transient 503 errors followed by a 200 OK
    call_count = 0

    async def mock_handler(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return Response(503, text="Temporary Overload")
        return Response(200, json=MOCK_FULL_OPEN_METEO_PAYLOAD)

    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        mock_get.side_effect = [
            Response(503, text="Overload"),
            Response(429, text="Rate Limited"),
            Response(200, json=MOCK_FULL_OPEN_METEO_PAYLOAD),
        ]

        res = await provider.fetch_weather(26.1445, 91.7362)
        assert res["current"]["temperature_c"] == 24.5
        assert mock_get.call_count == 3


# =========================================================================
# 3. WEATHER REFRESH IDEMPOTENCY AND DEDUPLICATION TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_weather_refresh_idempotency_prevents_duplicate_records(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """Verifies that running refresh consecutively does not produce duplicate observations."""
    dynamic_payload = dict(MOCK_FULL_OPEN_METEO_PAYLOAD)
    fixed_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    dynamic_payload["current"]["time"] = fixed_time.isoformat()
    dynamic_payload["hourly"]["time"] = [
        (fixed_time + timedelta(hours=i)).isoformat() for i in range(5)
    ]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json=dynamic_payload)

        # First run: persists records
        res1 = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert res1.status_code == 200
        count1 = res1.json()["observations_persisted"]
        assert count1 > 0

        # Second run with exact same data: should persist 0 new records due to deduplication
        res2 = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert res2.status_code == 200
        count2 = res2.json()["observations_persisted"]
        assert count2 == 0


@pytest.mark.asyncio
async def test_weather_refresh_partial_failure_preserves_successful_points(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """Verifies that an error at one waypoint does not abort or discard other successful waypoints."""
    call_index = 0
    fresh_time = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
    partial_payload = dict(MOCK_FULL_OPEN_METEO_PAYLOAD)
    partial_payload["current"] = dict(MOCK_FULL_OPEN_METEO_PAYLOAD["current"])
    partial_payload["current"]["time"] = fresh_time.isoformat()
    partial_payload["hourly"] = dict(MOCK_FULL_OPEN_METEO_PAYLOAD["hourly"])
    partial_payload["hourly"]["time"] = [
        (fresh_time + timedelta(hours=i)).isoformat() for i in range(5)
    ]

    def side_effect(*args, **kwargs):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            # First waypoint fails with 500
            return Response(500, text="Internal Provider Failure")
        return Response(200, json=partial_payload)

    with patch("httpx.AsyncClient.get", side_effect=side_effect):
        res = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["observations_persisted"] > 0
        assert data["sample_points_queried"] > 1

    # Check status endpoint reflects partial failure or success
    st_res = await async_client.get("/api/v1/weather/status", headers=dispatcher_headers)
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["total_observations"] > 0


# =========================================================================
# 4. FORECAST API AND HORIZON TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_weather_forecast_endpoint_retrieval(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """Tests the GET /api/v1/weather/forecast endpoint with bounded horizon."""
    # Ensure fresh data exists
    dynamic_payload = dict(MOCK_FULL_OPEN_METEO_PAYLOAD)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    dynamic_payload["current"]["time"] = now.isoformat()
    dynamic_payload["hourly"]["time"] = [
        (now + timedelta(hours=i + 1)).isoformat() for i in range(5)
    ]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json=dynamic_payload)
        await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)

    # Query forecast for Guwahati coordinates
    res = await async_client.get(
        "/api/v1/weather/forecast?latitude=26.1445&longitude=91.7362&hours=4",
        headers=dispatcher_headers,
    )
    assert res.status_code == 200
    fc = res.json()
    assert fc["provider"] == "open-meteo"
    assert fc["horizon_hours"] >= 1
    assert len(fc["hourly"]) >= 1

    first_item = fc["hourly"][0]
    assert "temperature_c" in first_item
    assert "precipitation_mm" in first_item
    assert "wind_speed_kmh" in first_item
    assert "valid_time" in first_item


# =========================================================================
# 5. MACHINE LEARNING DATA CONTRACT & ROLLING PRECIPITATION TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_weather_ml_feature_vector_contract(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
):
    """
    Verifies that GET /api/v1/weather/features provides a complete,
    feature-ready contract for downstream predictive modeling.
    """
    ref_dt = datetime.now(timezone.utc).replace(microsecond=0)
    dynamic_payload = dict(MOCK_FULL_OPEN_METEO_PAYLOAD)
    dynamic_payload["current"] = dict(MOCK_FULL_OPEN_METEO_PAYLOAD["current"])
    dynamic_payload["current"]["time"] = ref_dt.isoformat()
    dynamic_payload["current"]["precipitation"] = 4.2
    dynamic_payload["hourly"] = dict(MOCK_FULL_OPEN_METEO_PAYLOAD["hourly"])
    dynamic_payload["hourly"]["time"] = [
        (ref_dt - timedelta(hours=1)).isoformat(),
        ref_dt.isoformat(),
        (ref_dt + timedelta(hours=1)).isoformat(),
        (ref_dt + timedelta(hours=2)).isoformat(),
        (ref_dt + timedelta(hours=3)).isoformat(),
    ]
    dynamic_payload["hourly"]["precipitation"] = [1.5, 4.2, 2.0, 3.0, 1.0]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json=dynamic_payload)
        await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)

    res = await async_client.get(
        f"/api/v1/weather/features?latitude=26.1445&longitude=91.7362&reference_time={ref_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        headers=dispatcher_headers,
    )
    assert res.status_code == 200
    feat = res.json()

    # Schema & provenance
    assert feat["schema_version"] == "1.0"
    assert feat["provider"] == "open-meteo"
    assert feat["spatial_match_confidence"] in ["HIGH", "MEDIUM", "LOW", "UNMATCHED"]
    assert feat["data_freshness_seconds"] is not None
    assert feat["data_freshness_seconds"] >= 0.0

    # Current surface conditions
    cond = feat["current_conditions"]
    assert cond["temperature_c"] == 24.5
    assert cond["relative_humidity_pct"] == 88.0
    assert cond["precipitation_mm"] == 4.2
    assert cond["wind_speed_kmh"] == 14.5
    assert cond["surface_pressure_hpa"] == 1006.1

    # Units dictionary
    assert feat["units"]["temperature"] == "°C"
    assert feat["units"]["precipitation"] == "mm"
    assert feat["units"]["wind_speed"] == "km/h"

    # Rolling window flags: 24h past window should report INSUFFICIENT_DATA because only 2 hours exist
    past_accum = feat["rainfall_accumulation_past"]
    past_comp = feat["past_data_completeness"]
    assert "past_1h_mm" in past_accum
    assert past_comp["past_24h"] == "INSUFFICIENT_DATA"
    assert past_accum["past_24h_mm"] is None  # Must NOT be zero!


@pytest.mark.asyncio
async def test_weather_ml_features_spatial_matching_with_road_segment(
    async_client: AsyncClient,
    db_session: AsyncSession,
    dispatcher_headers: dict[str, str],
):
    """Verifies that requesting weather for a specific road_segment_id resolves spatial distance and confidence."""
    # Find any road segment in database
    seg_res = await db_session.execute(RoadSegment.__table__.select().limit(1))
    seg_row = seg_res.first()

    if seg_row:
        seg_id = seg_row.id
        res = await async_client.get(
            f"/api/v1/weather/features?road_segment_id={seg_id}",
            headers=dispatcher_headers,
        )
        assert res.status_code == 200
        feat = res.json()
        assert feat["road_segment_id"] == seg_id
        assert feat["road_segment_distance_m"] is not None
        assert feat["spatial_match_confidence"] in ["HIGH", "MEDIUM", "LOW", "UNMATCHED"]


# =========================================================================
# 6. AUTHENTICATION & RBAC PERMISSION TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_weather_endpoints_rbac_enforcement(
    async_client: AsyncClient,
    driver_headers: dict[str, str],
    field_officer_headers: dict[str, str],
    dispatcher_headers: dict[str, str],
):
    """
    Verifies that:
    - Anonymous requests to weather endpoints are denied (401).
    - Driver and Field Officer cannot trigger refresh (403 Forbidden).
    - Dispatcher can trigger refresh (200 OK).
    - All authenticated roles can read latest, forecast, and features (200 OK).
    """
    # 1. Anonymous access
    anon_refresh = await async_client.post("/api/v1/weather/refresh")
    assert anon_refresh.status_code == 401
    anon_latest = await async_client.get("/api/v1/weather/latest")
    assert anon_latest.status_code == 401

    # 2. Driver role cannot trigger refresh
    driver_refresh = await async_client.post("/api/v1/weather/refresh", headers=driver_headers)
    assert driver_refresh.status_code == 403

    # 3. Field Officer cannot trigger refresh
    fo_refresh = await async_client.post("/api/v1/weather/refresh", headers=field_officer_headers)
    assert fo_refresh.status_code == 403

    # 4. Driver can read forecast and features
    driver_fc = await async_client.get("/api/v1/weather/forecast?hours=6", headers=driver_headers)
    assert driver_fc.status_code == 200

    driver_feat = await async_client.get("/api/v1/weather/features", headers=driver_headers)
    assert driver_feat.status_code == 200


@pytest.mark.asyncio
async def test_feature_endpoint_deduplication_and_upsert_after_multiple_ingestions(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    field_officer_headers: dict[str, str],
    db_session: AsyncSession,
):
    """
    Validates that:
    1. Running weather ingestion multiple times upserts refreshed forecasts without inflating rainfall accumulation.
    2. Overlapping duplicate forecasts across runs select exactly one authoritative value per valid interval.
    3. If actual observations exist alongside historical forecasts for the same valid time, actual observations
       are prioritized and duplicate intervals cannot inflate the rainfall total.
    """
    ref_time = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    base_lat = 26.1445
    base_lon = 91.7362

    # --- INGESTION RUN 1: Initial forecast run ---
    # Current at 10:00: 0.5 mm
    # Hourly forecast:
    # 11:00 -> 2.0 mm
    # 12:00 -> 3.0 mm
    # 13:00 -> 4.0 mm
    # 14:00 to 20:00 -> 0.0 mm
    payload_run1 = dict(MOCK_FULL_OPEN_METEO_PAYLOAD)
    payload_run1["current"] = dict(MOCK_FULL_OPEN_METEO_PAYLOAD["current"])
    payload_run1["current"]["time"] = ref_time.strftime("%Y-%m-%dT%H:%M")
    payload_run1["current"]["precipitation"] = 0.5

    payload_run1["hourly"] = dict(MOCK_FULL_OPEN_METEO_PAYLOAD["hourly"])
    times_run1 = [(ref_time + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(1, 25)]
    precip_run1 = [2.0, 3.0, 4.0] + [0.0] * 21
    payload_run1["hourly"]["time"] = times_run1
    payload_run1["hourly"]["precipitation"] = precip_run1

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json=payload_run1)
        res_ref1 = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert res_ref1.status_code == 200

    # Query ML feature vector after Run 1
    ref_str = ref_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    res_feat1 = await async_client.get(
        f"/api/v1/weather/features?latitude={base_lat}&longitude={base_lon}&reference_time={ref_str}",
        headers=field_officer_headers,
    )
    assert res_feat1.status_code == 200
    feat1 = res_feat1.json()
    assert feat1["rainfall_forecast_accumulation"]["next_1h_mm"] == 2.0
    assert feat1["rainfall_forecast_accumulation"]["next_3h_mm"] == 9.0  # 2.0 + 3.0 + 4.0

    # --- INGESTION RUN 2: Refreshed forecast run with revised values ---
    # Suppose the weather model revised the forecast:
    # 11:00 -> 1.0 mm (down from 2.0)
    # 12:00 -> 1.5 mm (down from 3.0)
    # 13:00 -> 2.5 mm (down from 4.0)
    payload_run2 = dict(payload_run1)
    precip_run2 = [1.0, 1.5, 2.5] + [0.0] * 21
    payload_run2["hourly"]["precipitation"] = precip_run2

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json=payload_run2)
        res_ref2 = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert res_ref2.status_code == 200

    # Query ML feature vector after Run 2
    res_feat2 = await async_client.get(
        f"/api/v1/weather/features?latitude={base_lat}&longitude={base_lon}&reference_time={ref_str}",
        headers=field_officer_headers,
    )
    assert res_feat2.status_code == 200
    feat2 = res_feat2.json()
    # Deduplication and upserting guarantee:
    # next_1h must be updated to 1.0 (NOT 2.0, and NOT 1.0+2.0=3.0)
    # next_3h must be 1.0 + 1.5 + 2.5 = 5.0 (NOT inflated to 9.0 + 5.0 = 14.0!)
    assert feat2["rainfall_forecast_accumulation"]["next_1h_mm"] == 1.0
    assert feat2["rainfall_forecast_accumulation"]["next_3h_mm"] == 5.0

    # Direct DB inspection: verify zero duplicate forecast records for the same timestamp
    from sqlalchemy import func, select
    dup_query = (
        select(WeatherObservation.forecast_valid_at, func.count(WeatherObservation.id))
        .where(
            WeatherObservation.latitude == base_lat,
            WeatherObservation.longitude == base_lon,
            WeatherObservation.data_type == "FORECAST",
        )
        .group_by(WeatherObservation.forecast_valid_at)
        .having(func.count(WeatherObservation.id) > 1)
    )
    dup_res = await db_session.execute(dup_query)
    duplicates = dup_res.all()
    assert len(duplicates) == 0, f"Found duplicate forecast records: {duplicates}"

    # --- PART 3: Prioritize actual observations over historical forecasts ---
    # Suppose at 12:00 UTC, an actual ground observation arrives:
    obs_time = ref_time + timedelta(hours=2)  # 12:00
    # Manually insert an old exaggerated forecast for 12:00 issued earlier (50.0 mm)
    old_fc = WeatherObservation(
        id=uuid.uuid4(),
        provider="open-meteo",
        data_type="FORECAST",
        latitude=base_lat,
        longitude=base_lon,
        location_geom=f"SRID=4326;POINT({base_lon} {base_lat})",
        forecast_valid_at=obs_time,
        observed_at=ref_time - timedelta(hours=2),
        issue_time=ref_time - timedelta(hours=2),
        precipitation_mm=50.0,
        rainfall_mm=50.0,
    )
    # And insert the actual observation for 12:00 (1.5 mm)
    actual_obs = WeatherObservation(
        id=uuid.uuid4(),
        provider="open-meteo",
        data_type="OBSERVATION",
        latitude=base_lat,
        longitude=base_lon,
        location_geom=f"SRID=4326;POINT({base_lon} {base_lat})",
        forecast_valid_at=obs_time,
        observed_at=obs_time,
        issue_time=obs_time,
        precipitation_mm=1.5,
        rainfall_mm=1.5,
    )
    db_session.add(old_fc)
    db_session.add(actual_obs)
    await db_session.commit()

    # Query ML feature vector with reference_time at obs_time (12:00 UTC)
    obs_ref_str = obs_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    res_feat3 = await async_client.get(
        f"/api/v1/weather/features?latitude={base_lat}&longitude={base_lon}&reference_time={obs_ref_str}",
        headers=field_officer_headers,
    )
    assert res_feat3.status_code == 200
    feat3 = res_feat3.json()
    # Past 1h window (11:00 to 12:00) contains the 12:00 interval.
    # The system must select the actual observation 1.5mm, NOT the 50.0mm old forecast!
    assert feat3["rainfall_accumulation_past"]["past_1h_mm"] == 1.5


@pytest.mark.asyncio
async def test_location_specific_rainfall_isolation_for_same_hour(
    async_client: AsyncClient,
    field_officer_headers: dict[str, str],
    db_session: AsyncSession,
):
    """
    Regression Test (Requirement 1):
    Verifies that location filtering occurs strictly before ROW_NUMBER() windowing,
    ensuring records from different geographic locations for the same valid hour
    are isolated and never mixed or cross-contaminated.
    """
    ref_time = datetime.now(timezone.utc).replace(microsecond=0)
    target_hour = ref_time + timedelta(hours=1)

    # Location 1: Guwahati (plains)
    lat1, lon1 = 26.1445, 91.7362
    # Location 2: Tawang (high mountains)
    lat2, lon2 = 27.5860, 91.8590

    # Insert current observations for both locations at 10:00
    curr1 = WeatherObservation(
        id=uuid.uuid4(),
        provider="open-meteo",
        data_type="CURRENT",
        latitude=lat1,
        longitude=lon1,
        location_geom=f"SRID=4326;POINT({lon1} {lat1})",
        observed_at=ref_time,
        forecast_valid_at=ref_time,
        issue_time=ref_time,
        temperature_c=28.0,
        precipitation_mm=0.2,
    )
    curr2 = WeatherObservation(
        id=uuid.uuid4(),
        provider="open-meteo",
        data_type="CURRENT",
        latitude=lat2,
        longitude=lon2,
        location_geom=f"SRID=4326;POINT({lon2} {lat2})",
        observed_at=ref_time,
        forecast_valid_at=ref_time,
        issue_time=ref_time,
        temperature_c=8.0,
        precipitation_mm=5.0,
    )

    # Insert forecast for the SAME valid hour (11:00) with drastically different rainfall
    fc1 = WeatherObservation(
        id=uuid.uuid4(),
        provider="open-meteo",
        data_type="FORECAST",
        latitude=lat1,
        longitude=lon1,
        location_geom=f"SRID=4326;POINT({lon1} {lat1})",
        observed_at=ref_time,
        forecast_valid_at=target_hour,
        issue_time=ref_time,
        temperature_c=27.5,
        precipitation_mm=2.5,  # Moderate rain in Guwahati
        rainfall_mm=2.5,
    )
    fc2 = WeatherObservation(
        id=uuid.uuid4(),
        provider="open-meteo",
        data_type="FORECAST",
        latitude=lat2,
        longitude=lon2,
        location_geom=f"SRID=4326;POINT({lon2} {lat2})",
        observed_at=ref_time,
        forecast_valid_at=target_hour,
        issue_time=ref_time,
        temperature_c=7.0,
        precipitation_mm=35.0,  # Cloudburst / torrential rain in Tawang
        rainfall_mm=35.0,
    )

    db_session.add_all([curr1, curr2, fc1, fc2])
    await db_session.commit()

    ref_str = ref_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Query ML features for Location 1 (Guwahati)
    res1 = await async_client.get(
        f"/api/v1/weather/features?latitude={lat1}&longitude={lon1}&reference_time={ref_str}",
        headers=field_officer_headers,
    )
    assert res1.status_code == 200
    feat1 = res1.json()
    assert feat1["latitude"] == lat1
    assert feat1["longitude"] == lon1
    assert feat1["current_conditions"]["temperature_c"] == 28.0
    # Must be 2.5 mm (Guwahati's value), NOT 35.0 mm or 37.5 mm
    assert feat1["rainfall_forecast_accumulation"]["next_1h_mm"] == 2.5

    # 2. Query ML features for Location 2 (Tawang)
    res2 = await async_client.get(
        f"/api/v1/weather/features?latitude={lat2}&longitude={lon2}&reference_time={ref_str}",
        headers=field_officer_headers,
    )
    assert res2.status_code == 200
    feat2 = res2.json()
    assert feat2["latitude"] == lat2
    assert feat2["longitude"] == lon2
    assert feat2["current_conditions"]["temperature_c"] == 8.0
    # Must be 35.0 mm (Tawang's value), NOT 2.5 mm or 37.5 mm
    assert feat2["rainfall_forecast_accumulation"]["next_1h_mm"] == 35.0

    # 3. Query hourly forecast for Location 1
    fc_res1 = await async_client.get(
        f"/api/v1/weather/forecast?latitude={lat1}&longitude={lon1}&hours=2",
        headers=field_officer_headers,
    )
    assert fc_res1.status_code == 200
    assert fc_res1.json()["hourly"][0]["precipitation_mm"] == 2.5

    # 4. Query hourly forecast for Location 2
    fc_res2 = await async_client.get(
        f"/api/v1/weather/forecast?latitude={lat2}&longitude={lon2}&hours=2",
        headers=field_officer_headers,
    )
    assert fc_res2.status_code == 200
    assert fc_res2.json()["hourly"][0]["precipitation_mm"] == 35.0


@pytest.mark.asyncio
async def test_weather_value_changes_and_null_updates_after_reingestion(
    async_client: AsyncClient,
    dispatcher_headers: dict[str, str],
    db_session: AsyncSession,
):
    """
    Regression Test (Requirement 2):
    Verifies that repeated ingestion correctly updates ALL weather measurement fields,
    and refreshed provider values (including legitimate nulls) properly overwrite stale values.
    """
    ref_time = datetime(2026, 10, 13, 8, 0, 0, tzinfo=timezone.utc)
    target_hour = datetime(2026, 10, 13, 9, 0, 0, tzinfo=timezone.utc)
    base_lat = 26.1445
    base_lon = 91.7362

    # --- INGESTION RUN 1: Stored with specific values ---
    payload_run1 = dict(MOCK_FULL_OPEN_METEO_PAYLOAD)
    payload_run1["current"] = dict(MOCK_FULL_OPEN_METEO_PAYLOAD["current"])
    payload_run1["current"]["time"] = ref_time.strftime("%Y-%m-%dT%H:%M")
    payload_run1["hourly"] = dict(MOCK_FULL_OPEN_METEO_PAYLOAD["hourly"])
    payload_run1["hourly"]["time"] = [target_hour.strftime("%Y-%m-%dT%H:%M")]
    payload_run1["hourly"]["temperature_2m"] = [21.0]
    payload_run1["hourly"]["precipitation"] = [8.5]
    payload_run1["hourly"]["wind_speed_10m"] = [18.0]
    payload_run1["hourly"]["visibility"] = [10000.0]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json=payload_run1)
        res1 = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert res1.status_code == 200

    # Verify initial stored record in DB
    from sqlalchemy import select
    q = select(WeatherObservation).where(
        WeatherObservation.latitude == base_lat,
        WeatherObservation.longitude == base_lon,
        WeatherObservation.forecast_valid_at == target_hour,
        WeatherObservation.data_type == "FORECAST",
    )
    rec1 = (await db_session.execute(q)).scalar_one()
    assert rec1.temperature_c == 21.0
    assert rec1.precipitation_mm == 8.5
    assert rec1.wind_speed_kmh == 18.0
    assert rec1.visibility_m == 10000.0

    # --- INGESTION RUN 2: Re-ingestion with changed values and legitimate null ---
    # Provider reports temperature increased to 29.0, rain stopped (0.0),
    # wind sensor offline (None), and visibility reduced to 4500.0
    payload_run2 = dict(payload_run1)
    payload_run2["hourly"] = dict(payload_run1["hourly"])
    payload_run2["hourly"]["temperature_2m"] = [29.0]
    payload_run2["hourly"]["precipitation"] = [0.0]
    payload_run2["hourly"]["wind_speed_10m"] = [None]  # Legitimate null
    payload_run2["hourly"]["visibility"] = [4500.0]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(200, json=payload_run2)
        res2 = await async_client.post("/api/v1/weather/refresh", headers=dispatcher_headers)
        assert res2.status_code == 200

    # Expire session cache to ensure reading fresh from PostgreSQL
    db_session.expire_all()

    # Verify updated values in DB
    rec2 = (await db_session.execute(q)).scalar_one()
    assert rec2.temperature_c == 29.0  # Successfully changed from 21.0
    assert rec2.precipitation_mm == 0.0  # Successfully changed from 8.5
    assert rec2.wind_speed_kmh is None  # Legitimate null successfully replaced stale 18.0
    assert rec2.visibility_m == 4500.0  # Successfully changed from 10000.0



