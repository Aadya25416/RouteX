"""
Download NASA Global Landslide Catalog data for NER India.
This provides historical landslide locations for XGBoost training.

Source: NASA Global Landslide Catalog (GLC)
API: https://gpm.nasa.gov/landslides/
No API key needed.
"""

import json
import os
import csv
import urllib.request
import time

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "risk_features", "raw", "landslides"
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# NER bounding box: Lat 21-30°N, Lon 88-98°E
NER_BBOX = {
    "min_lat": 21.0,
    "max_lat": 30.0,
    "min_lon": 88.0,
    "max_lon": 98.0,
}

print("=" * 60)
print("  NER-LINK: NASA Landslide Catalog Downloader")
print("=" * 60)
print()

# Method 1: Try NASA GLC API
# The GLC is available as a CSV from data.nasa.gov
GLC_URL = "https://data.nasa.gov/api/views/dd9e-wu2v/rows.csv?accessType=DOWNLOAD"

output_file_full = os.path.join(OUTPUT_DIR, "nasa_glc_full.csv")
output_file_ner = os.path.join(OUTPUT_DIR, "nasa_glc_ner.csv")

print("📥 Downloading NASA Global Landslide Catalog...")
print(f"   URL: {GLC_URL}")
print(f"   This is a large file (~15MB), please wait...")
print()

try:
    req = urllib.request.Request(GLC_URL, headers={"User-Agent": "NER-LINK/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        data = response.read().decode("utf-8", errors="replace")

    # Save full catalog
    with open(output_file_full, "w") as f:
        f.write(data)
    print(f"✅ Full catalog saved: {output_file_full}")
    print(f"   Size: {os.path.getsize(output_file_full) / (1024*1024):.1f} MB")

    # Filter for NER region
    reader = csv.DictReader(data.splitlines())
    ner_events = []
    total_events = 0

    for row in reader:
        total_events += 1
        try:
            lat = float(row.get("latitude", 0))
            lon = float(row.get("longitude", 0))
        except (ValueError, TypeError):
            continue

        if (NER_BBOX["min_lat"] <= lat <= NER_BBOX["max_lat"] and
            NER_BBOX["min_lon"] <= lon <= NER_BBOX["max_lon"]):
            ner_events.append({
                "event_id": row.get("event_id", ""),
                "event_date": row.get("event_date", ""),
                "event_title": row.get("event_title", ""),
                "latitude": lat,
                "longitude": lon,
                "country_name": row.get("country_name", ""),
                "admin_division_name": row.get("admin_division_name", ""),
                "landslide_category": row.get("landslide_category", ""),
                "landslide_trigger": row.get("landslide_trigger", ""),
                "landslide_size": row.get("landslide_size", ""),
                "fatality_count": row.get("fatality_count", ""),
                "injury_count": row.get("injury_count", ""),
                "source_name": row.get("source_name", ""),
            })

    # Save NER filtered events
    if ner_events:
        with open(output_file_ner, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ner_events[0].keys())
            writer.writeheader()
            writer.writerows(ner_events)

    print()
    print(f"📊 Results:")
    print(f"   Total global events: {total_events}")
    print(f"   NER region events:   {len(ner_events)}")
    print(f"   NER data saved to:   {output_file_ner}")

    # Quick stats
    if ner_events:
        categories = {}
        triggers = {}
        for e in ner_events:
            cat = e["landslide_category"] or "unknown"
            trig = e["landslide_trigger"] or "unknown"
            categories[cat] = categories.get(cat, 0) + 1
            triggers[trig] = triggers.get(trig, 0) + 1

        print()
        print("   Categories:")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:5]:
            print(f"     {cat}: {count}")
        print()
        print("   Triggers:")
        for trig, count in sorted(triggers.items(), key=lambda x: -x[1])[:5]:
            print(f"     {trig}: {count}")

except Exception as e:
    print(f"❌ Download failed: {e}")
    print()
    print("Alternative: Download manually from:")
    print("  https://data.nasa.gov/Earth-Science/Global-Landslide-Catalog/dd9e-wu2v")
    print("  → Click 'Export' → CSV")
    print(f"  → Save to: {OUTPUT_DIR}/")

print()
print("=" * 60)
print("  Done!")
print("=" * 60)
