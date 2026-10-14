# Weather Data Collection & Validation Pipeline Specification

**Version:** 1.0.0  
**Status:** Implemented & Verified  
**Target Corridor:** Guwahati–Tawang (Configurable Study Region)  
**External Provider:** Open-Meteo API (`https://api.open-meteo.com/v1/forecast`)  

---

## 1. Overview & Architecture

The Weather Ingestion and Validation Pipeline in NER-LINK provides reliable, timestamped weather observations and multi-day hourly forecasts to support logistics risk assessment, disruption detection, and future machine learning models.

The system is designed with:
- **Corridor-Based Waypoint Sampling:** Samples discrete spatial waypoints across the mountain-plains corridor to reflect elevation changes and micro-climates without redundant API calls.
- **Strict Distinction Between Observations and Forecasts:** Differentiates `CURRENT`, `OBSERVATION`, `FORECAST`, and `DAILY_SUMMARY` data types with separate `observed_at`, `issue_time`, and `forecast_valid_at` timestamps.
- **Meteorological Interval Semantics:** Explicit interval accumulation for precipitation over rolling windows without double-counting overlapping refresh intervals or fabricating zero-rainfall values.
- **Resilient Upstream Handling:** Bounded exponential backoff retries for rate limits (HTTP 429) and upstream errors (HTTP 5xx), preserving historical observations during outages.
- **Feature-Ready ML Handoff:** Dedicated feature vector endpoint (`GET /api/v1/weather/features`) providing rolling rainfall windows (1h, 3h, 6h, 24h past and future), data freshness, and completeness flags (`COMPLETE`, `PARTIAL`, `INSUFFICIENT_DATA`).

---

## 2. Configured Variables, Units & Rationale

All variables requested from Open-Meteo have been selected based on road disruption, landslide risk, flash flood hazards, and high-altitude transport hazards in the North Eastern Region.

| Variable Category | Open-Meteo Parameter | Persisted Field | Units | Physical / Risk Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **Precipitation** | `precipitation` | `precipitation_mm` | mm | Total precipitation over the 1-hour interval; primary driver of road washouts and flash floods. |
| | `rain` | `rain_mm` | mm | Liquid rain component; critical for soil saturation modeling. |
| | `showers` | `showers_mm` | mm | Convective precipitation pulses common in monsoon terrain. |
| | `snowfall` | `snowfall_cm` | cm | Crucial for high-altitude passes (e.g., Sela Pass at 13,700 ft). |
| | `precipitation_probability` | `precipitation_probability_pct` | % | Forecast probability for rain event likelihood modeling. |
| **Atmospheric** | `temperature_2m` | `temperature_c` | °C | Freezing/icing conditions on mountain passes; engine performance. |
| | `relative_humidity_2m` | `relative_humidity_pct` | % | Fog and moisture condensation indicator. |
| | `dew_point_2m` | `dew_point_c` | °C | Condensation and icing threshold predictor. |
| | `apparent_temperature` | `apparent_temperature_c` | °C | Wind chill factor for personnel and driver safety. |
| | `pressure_msl` | `pressure_msl_hpa` | hPa | Mean sea level barometric pressure for storm/cyclone tracking. |
| | `surface_pressure` | `surface_pressure_hpa` | hPa | True station pressure across extreme elevation gradients (50m to 4,200m). |
| **Wind** | `wind_speed_10m` | `wind_speed_kmh` | km/h | High-profile cargo vehicle stability. |
| | `wind_direction_10m` | `wind_direction_deg` | ° | Wind vector / crosswind risk on mountain ridges. |
| | `wind_gusts_10m` | `wind_gusts_kmh` | km/h | Sudden gusts causing tree falls or vehicle instability. |
| **Visibility & State** | `visibility` | `visibility_m` | m | Heavy fog, monsoon blinding, or cloud immersion on passes. |
| | `weather_code` | `weather_code` | int | WMO standard code (0 = Clear sky to 99 = Heavy thunderstorm with hail). |
| | `cloud_cover` | `cloud_cover_pct` | % | Satellite optical image cloud contamination correlation. |
| **Hydrological** | `et0_fao_evapotranspiration` | `et0_evapotranspiration_mm` | mm | Reference evapotranspiration; key parameter for soil drainage after heavy rain. |
| | `soil_moisture_0_to_1cm` | `soil_moisture_m3m3` | m³/m³ | Volumetric soil moisture for empirical landslide triggering models. |

---

## 3. Current Conditions vs. Forecast Semantics

### Temporal Semantics
1. **Current Conditions (`data_type = CURRENT`)**:
   - `observed_at`: Exact timestamp provided by the provider's `current` payload (or server fetch time if omitted).
   - `issue_time`: Same as `observed_at`.
   - `forecast_valid_at`: Same as `observed_at`.
2. **Forecast Records (`data_type = FORECAST`)**:
   - `observed_at`: Ingestion time when NER-LINK retrieved this forecast from Open-Meteo.
   - `issue_time`: Model run / issue timestamp provided by Open-Meteo or set to the batch fetch time.
   - `forecast_valid_at`: Specific future hourly timestamp to which this forecast applies.
3. **Daily Summaries (`data_type = DAILY_SUMMARY`)**:
   - Aggregated daily statistics calculated and provided directly by Open-Meteo's `daily` endpoint (e.g., `precipitation_sum`, `wind_speed_10m_max`, `temperature_2m_max`, `temperature_2m_min`).

### Precipitation Interval Interpretation & Anti-Inflation Guarantees
- Hourly precipitation (`precipitation_mm`) is an **interval quantity** representing the total accumulated rainfall over the preceding 60 minutes ending at `forecast_valid_at`.
- It is **never** treated as an instantaneous rate (mm/h).
- **Upsert on Ingestion:** When weather ingestion runs consecutively or on a recurring schedule, refreshed forecasts for matching `(provider, data_type, forecast_valid_at, latitude, longitude)` are **upserted in-place**, updating forecast values with the latest model run predictions rather than creating duplicate interval rows or skipping updates.
- **Authoritative Value Selection:** Rolling precipitation accumulation queries (`past_1h`, `past_3h`, `past_6h`, `past_24h` and `next_1h`, `next_3h`, `next_6h`, `next_24h`) use `ROW_NUMBER() OVER (PARTITION BY forecast_valid_at ORDER BY ...)`:
  - Selects **exactly one** record per 1-hour interval within the half-open window `(w_start, ref_time]` or `(ref_time, w_end]`.
  - For past windows, actual `OBSERVATION` / `CURRENT` records are prioritized over older `FORECAST` records.
  - Between records of the same priority, the latest `issue_time` and `ingested_at` is selected.
  - This mathematically guarantees that duplicate intervals across multiple ingestion runs cannot inflate or double-count rainfall totals.
- Missing values (`None`) are **never** coerced to `0.0`. If measurements are missing in a window, the interval status is flagged as `PARTIAL` or `INSUFFICIENT_DATA`.

---

## 4. Corridor Waypoints & Spatial Sampling

The platform configures representative waypoints covering the elevation and topographical profile of the corridor:

| Waypoint Name | Latitude | Longitude | Terrain / Elevation Notes |
| :--- | :--- | :--- | :--- |
| **Guwahati** | 26.1445 | 91.7362 | Brahmaputra valley floor, plains logistics hub (~55m) |
| **Rangia** | 26.4716 | 91.6288 | Northern plains transit junction |
| **Tezpur** | 26.6528 | 92.7926 | Eastern valley corridor / Brahmaputra crossing |
| **Balipara** | 26.8285 | 92.8228 | Foothill transition zone |
| **Bhalukpong** | 27.0125 | 92.6450 | Assam–Arunachal border checkpoint, canyon entrance (~213m) |
| **Bomdila** | 27.2644 | 92.4239 | Ridge pass, administrative headquarters (~2,217m) |
| **Dirang** | 27.3592 | 92.2384 | High-altitude river valley (~1,560m) |
| **Sela Pass** | 27.5042 | 92.1039 | Mountain pass, snow and sub-zero hazards (~4,170m / 13,700 ft) |
| **Tawang** | 27.5861 | 91.8594 | High Himalayan destination plateau (~3,048m) |

When an observation is ingested, the system locates the nearest `RoadSegment` in PostGIS within `GPS_SNAP_THRESHOLD_M` (100m) to associate `road_segment_id`. If outside the threshold, coordinates are stored cleanly with `road_segment_id = null`.

---

## 5. Configuration & Environment Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `WEATHER_PROVIDER` | `str` | `"open_meteo"` | Weather provider implementation key. |
| `WEATHER_API_BASE_URL` | `str` | `"https://api.open-meteo.com/v1"` | Upstream API endpoint. |
| `WEATHER_API_KEY` | `str` | `""` | Optional commercial Open-Meteo customer key. If blank, free tier is used. |
| `WEATHER_REQUEST_TIMEOUT_SECONDS` | `float` | `10.0` | Upstream HTTP request timeout. |
| `WEATHER_MAX_RETRIES` | `int` | `3` | Maximum retry attempts for transient 429/5xx errors. |
| `WEATHER_RETRY_BACKOFF_SECONDS` | `float` | `0.5` | Exponential backoff factor (0.5s, 1.0s, 2.0s...). |
| `WEATHER_STALE_THRESHOLD_MINUTES` | `int` | `120` | Threshold in minutes after which weather data is marked stale. |
| `WEATHER_FORECAST_DAYS` | `int` | `3` | Default forecast horizon in days (hourly resolution up to 7 days). |

---

## 6. Database Schema & Migration

### Migration Identifier: `00bb6c356bdd`
- **Revision ID:** `00bb6c356bdd_phase6_weather_pipeline_and_forecasts.py`
- **Down Revision:** `5cfa804483b8`

### Table: `weather_observations`
Key columns:
- `id` (UUID, Primary Key)
- `road_segment_id` (UUID, Foreign Key -> `road_segments.id`, nullable)
- `latitude` (Float, nullable, indexed)
- `longitude` (Float, nullable, indexed)
- `provider` (String, default `'open_meteo'`)
- `data_type` (String, `'CURRENT'`, `'OBSERVATION'`, `'FORECAST'`, `'DAILY_SUMMARY'`)
- `observed_at` (DateTime with timezone, indexed)
- `issue_time` (DateTime with timezone, nullable)
- `forecast_valid_at` (DateTime with timezone, nullable, indexed)
- Measurements: `temperature_c`, `rainfall_mm`, `precipitation_mm`, `rain_mm`, `showers_mm`, `snowfall_cm`, `precipitation_probability_pct`, `wind_speed_kmh`, `wind_direction_deg`, `wind_gusts_kmh`, `relative_humidity_pct`, `dew_point_c`, `apparent_temperature_c`, `pressure_msl_hpa`, `surface_pressure_hpa`, `visibility_m`, `cloud_cover_pct`, `et0_evapotranspiration_mm`, `soil_moisture_m3m3`, `weather_code`
- Composite index: `ix_weather_observations_lookup` (`provider`, `data_type`, `forecast_valid_at`)

---

## 7. API Reference & Examples

### 1. Refresh Weather Data
`POST /api/v1/weather/refresh`
- **Roles:** `dispatcher`, `admin`, `service_worker`
- **Query Parameters:** `forecast_days` (default 3, range 1-7)
- **Response:**
  ```json
  {
    "status": "success",
    "points_queried": 9,
    "points_updated": 9,
    "observations_persisted": 270,
    "errors": [],
    "updated_at": "2026-10-14T18:23:00Z"
  }
  ```

### 2. Query Latest Observations
`GET /api/v1/weather/latest`
- **Query Parameters:**
  - `limit`: default 50, max 500
  - `road_segment_id`: optional UUID
  - `data_type`: `'CURRENT'`, `'FORECAST'`, `'OBSERVATION'`
  - `min_lat`, `max_lat`, `min_lon`, `max_lon`: optional spatial bounding box
- **Response:**
  ```json
  [
    {
      "id": "270ad10a-6663-4ba9-9df5-64eb9a0225d7",
      "road_segment_id": null,
      "latitude": 26.1445,
      "longitude": 91.7362,
      "provider": "open_meteo",
      "data_type": "CURRENT",
      "temperature_c": 26.2,
      "rainfall_mm": 0.0,
      "precipitation_mm": 0.0,
      "rain_mm": 0.0,
      "showers_mm": 0.0,
      "precipitation_probability_pct": 10.0,
      "relative_humidity_pct": 74.0,
      "dew_point_c": 21.2,
      "apparent_temperature_c": 28.5,
      "pressure_msl_hpa": 1012.3,
      "surface_pressure_hpa": 1006.1,
      "wind_speed_kmh": 6.8,
      "wind_direction_deg": 120.0,
      "wind_gusts_kmh": 12.5,
      "visibility_m": 10000.0,
      "cloud_cover_pct": 20.0,
      "et0_evapotranspiration_mm": 0.15,
      "soil_moisture_m3m3": 0.28,
      "weather_code": 1,
      "observed_at": "2026-10-14T18:00:00Z",
      "issue_time": "2026-10-14T18:00:00Z",
      "forecast_valid_at": "2026-10-14T18:00:00Z"
    }
  ]
  ```

### 3. Query Hourly Forecasts
`GET /api/v1/weather/forecast`
- **Query Parameters:**
  - `latitude`, `longitude` OR `road_segment_id`
  - `hours`: default 24, range 1-168 (7 days)
- **Response:**
  ```json
  {
    "latitude": 26.1445,
    "longitude": 91.7362,
    "road_segment_id": null,
    "provider": "open_meteo",
    "issued_at": "2026-10-14T18:00:00Z",
    "forecast_hours": 24,
    "hourly": [
      {
        "valid_at": "2026-10-14T19:00:00Z",
        "temperature_c": 25.1,
        "precipitation_mm": 0.2,
        "rain_mm": 0.2,
        "showers_mm": 0.0,
        "snowfall_cm": 0.0,
        "precipitation_probability_pct": 20.0,
        "relative_humidity_pct": 78.0,
        "dew_point_c": 21.0,
        "apparent_temperature_c": 27.2,
        "pressure_msl_hpa": 1012.8,
        "surface_pressure_hpa": 1006.5,
        "wind_speed_kmh": 5.4,
        "wind_direction_deg": 130.0,
        "wind_gusts_kmh": 10.2,
        "visibility_m": 9000.0,
        "cloud_cover_pct": 35.0,
        "et0_evapotranspiration_mm": 0.05,
        "soil_moisture_m3m3": 0.28,
        "weather_code": 2
      }
    ],
    "daily_summaries": []
  }
  ```

### 4. Downstream ML Feature Vector Contract
`GET /api/v1/weather/features`
- **Query Parameters:**
  - `latitude`, `longitude` OR `road_segment_id`
  - `reference_time`: optional ISO timestamp (e.g. `2026-10-14T18:00:00Z`), default UTC now
- **Response:**
  ```json
  {
    "schema_version": "1.0",
    "provider": "open_meteo",
    "latitude": 26.1445,
    "longitude": 91.7362,
    "road_segment_id": null,
    "reference_time": "2026-10-14T18:00:00Z",
    "observation_time": "2026-10-14T18:00:00Z",
    "data_freshness_seconds": 120.0,
    "is_stale": false,
    "current_conditions": {
      "temperature_c": 26.2,
      "precipitation_mm": 0.0,
      "relative_humidity_pct": 74.0,
      "dew_point_c": 21.2,
      "apparent_temperature_c": 28.5,
      "pressure_msl_hpa": 1012.3,
      "surface_pressure_hpa": 1006.1,
      "wind_speed_kmh": 6.8,
      "wind_direction_deg": 120.0,
      "wind_gusts_kmh": 12.5,
      "visibility_m": 10000.0,
      "cloud_cover_pct": 20.0,
      "et0_evapotranspiration_mm": 0.15,
      "soil_moisture_m3m3": 0.28,
      "weather_code": 1
    },
    "rainfall_accumulations": {
      "precip_past_1h_mm": 0.0,
      "precip_past_3h_mm": 1.2,
      "precip_past_6h_mm": 3.4,
      "precip_past_24h_mm": 12.8,
      "precip_future_1h_mm": 0.2,
      "precip_future_3h_mm": 0.5,
      "precip_future_6h_mm": 1.8,
      "precip_future_24h_mm": 6.5
    },
    "completeness": {
      "past_1h": "COMPLETE",
      "past_3h": "COMPLETE",
      "past_6h": "COMPLETE",
      "past_24h": "COMPLETE",
      "future_1h": "COMPLETE",
      "future_3h": "COMPLETE",
      "future_6h": "COMPLETE",
      "future_24h": "COMPLETE"
    },
    "sample_counts": {
      "past_samples": 24,
      "future_samples": 24
    },
    "missing_fields": []
  }
  ```

### 5. Ingestion Health & Status
`GET /api/v1/weather/status`
- **Response:**
  ```json
  {
    "provider": "open_meteo",
    "status": "healthy",
    "configured_points": 9,
    "last_successful_refresh": "2026-10-14T18:23:00Z",
    "total_observations_in_db": 1420,
    "freshness_status": "fresh",
    "errors": []
  }
  ```

---

## 8. CLI Ingestion Script

An operational ingestion script is provided for cron or daemon execution:
```bash
# Refresh 3 days of forecast across all corridor waypoints
uv run python -m backend.scripts.ingest_weather --forecast-days 3
```

---

## 9. Implementation Status Summary

- [x] Complete Open-Meteo variables (rain, showers, precipitation, snowfall, humidity, dew point, apparent temp, pressures, wind, gusts, visibility, cloud cover, evapotranspiration, soil moisture).
- [x] Distinguish `CURRENT`, `OBSERVATION`, `FORECAST`, `DAILY_SUMMARY`.
- [x] Meteorological interval accumulation with distinct interval grouping.
- [x] Ingestion resilience with backoff and retry handling.
- [x] Downstream ML contract with completeness flags (`COMPLETE`, `PARTIAL`, `INSUFFICIENT_DATA`).
- [x] Backward compatibility preserved for all existing endpoints and 84 pre-existing tests.
- [x] 10 comprehensive tests added covering parsing, errors, idempotency, rolling windows, and ML features.
