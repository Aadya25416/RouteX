"""
Download historical weather data for all 8 NER state capitals from Open-Meteo.
Free API, no key needed.
Saves JSON files to data/risk_features/raw/weather/
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import time

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "risk_features", "raw", "weather"
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

NER_CITIES = {
    "guwahati":   {"lat": 26.14, "lon": 91.74,  "state": "Assam"},
    "shillong":   {"lat": 25.57, "lon": 91.88,  "state": "Meghalaya"},
    "imphal":     {"lat": 24.82, "lon": 93.95,  "state": "Manipur"},
    "itanagar":   {"lat": 27.08, "lon": 93.61,  "state": "Arunachal Pradesh"},
    "agartala":   {"lat": 23.83, "lon": 91.28,  "state": "Tripura"},
    "aizawl":     {"lat": 23.73, "lon": 92.72,  "state": "Mizoram"},
    "kohima":     {"lat": 25.67, "lon": 94.12,  "state": "Nagaland"},
    "gangtok":    {"lat": 27.33, "lon": 88.62,  "state": "Sikkim"},
}

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY_VARS = "precipitation_sum,rain_sum,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,weathercode"

print("=" * 60)
print("  NER-LINK: Open-Meteo Weather Data Downloader")
print("=" * 60)
print(f"Output directory: {OUTPUT_DIR}")
print(f"Cities: {len(NER_CITIES)}")
print(f"Date range: 2020-01-01 to 2025-12-31")
print()

success_count = 0
fail_count = 0

for city, info in NER_CITIES.items():
    print(f"📥 Downloading weather for {city.title()} ({info['state']})...")

    params = urllib.parse.urlencode({
        "latitude": info["lat"],
        "longitude": info["lon"],
        "start_date": "2020-01-01",
        "end_date": "2025-12-31",
        "daily": DAILY_VARS,
        "timezone": "Asia/Kolkata",
    })

    url = f"{BASE_URL}?{params}"
    output_file = os.path.join(OUTPUT_DIR, f"{city}_weather.json")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NER-LINK/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

        # Add metadata
        data["_metadata"] = {
            "city": city,
            "state": info["state"],
            "latitude": info["lat"],
            "longitude": info["lon"],
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        # Count days
        num_days = len(data.get("daily", {}).get("time", []))
        file_size = os.path.getsize(output_file) / 1024
        print(f"   ✅ Saved: {output_file}")
        print(f"      {num_days} days of data, {file_size:.1f} KB")
        success_count += 1

    except Exception as e:
        print(f"   ❌ Failed: {e}")
        fail_count += 1

    # Be polite to the free API
    time.sleep(1)

print()
print("=" * 60)
print(f"  Done! ✅ {success_count} succeeded, ❌ {fail_count} failed")
print("=" * 60)
