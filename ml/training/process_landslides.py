"""
Process NASA Global Landslide Catalog from downloaded zip.
Extracts full catalog and filters events specifically for the North Eastern Region (NER) of India.
"""

import os
import csv
import zipfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LANDSLIDE_DIR = os.path.join(PROJECT_ROOT, "data", "risk_features", "raw", "landslides")
os.makedirs(LANDSLIDE_DIR, exist_ok=True)

DOWNLOADS_ZIP = os.path.expanduser("~/Downloads/landslide.zip")
OUTPUT_FULL_CSV = os.path.join(LANDSLIDE_DIR, "nasa_glc_full.csv")
OUTPUT_NER_CSV = os.path.join(LANDSLIDE_DIR, "nasa_glc_ner.csv")

# NER Bounding Box: 21.0 - 30.0 N, 88.0 - 98.0 E
NER_BBOX = {
    "min_lat": 21.0,
    "max_lat": 30.0,
    "min_lon": 88.0,
    "max_lon": 98.0,
}

def process_landslide_catalog():
    if not os.path.exists(DOWNLOADS_ZIP):
        raise FileNotFoundError(f"Download zip not found at {DOWNLOADS_ZIP}")

    print("=" * 60)
    print("  Processing NASA Landslide Catalog for NER India")
    print("=" * 60)

    with zipfile.ZipFile(DOWNLOADS_ZIP, "r") as z:
        # Find csv inside zip
        csv_name = None
        for name in z.namelist():
            if name.endswith(".csv"):
                csv_name = name
                break
        
        if not csv_name:
            raise ValueError("No CSV file found in landslide.zip")

        print(f"📦 Extracting {csv_name} from {DOWNLOADS_ZIP}...")
        with z.open(csv_name) as f_in, open(OUTPUT_FULL_CSV, "wb") as f_out:
            while True:
                chunk = f_in.read(1024 * 1024)
                if not chunk:
                    break
                f_out.write(chunk)

    print(f"✅ Full catalog written to: {OUTPUT_FULL_CSV}")

    # Now filter for NER
    ner_events = []
    total_count = 0

    with open(OUTPUT_FULL_CSV, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_count += 1
            try:
                lat_str = row.get("latitude") or row.get("Latitude") or "0"
                lon_str = row.get("longitude") or row.get("Longitude") or "0"
                lat = float(lat_str)
                lon = float(lon_str)
            except (ValueError, TypeError):
                continue

            if (NER_BBOX["min_lat"] <= lat <= NER_BBOX["max_lat"] and
                NER_BBOX["min_lon"] <= lon <= NER_BBOX["max_lon"]):
                
                ner_events.append({
                    "event_id": row.get("id") or row.get("event_id", ""),
                    "event_date": row.get("date") or row.get("event_date", ""),
                    "latitude": lat,
                    "longitude": lon,
                    "country_name": row.get("country_name", ""),
                    "state_province": row.get("state/province") or row.get("admin_division_name", ""),
                    "city_town": row.get("city/town", ""),
                    "hazard_type": row.get("hazard_type", "Landslide"),
                    "landslide_type": row.get("landslide_type") or row.get("landslide_category", ""),
                    "landslide_size": row.get("landslide_size", ""),
                    "trigger": row.get("trigger") or row.get("landslide_trigger", ""),
                    "fatalities": row.get("fatalities") or row.get("fatality_count", "0"),
                    "injuries": row.get("injuries") or row.get("injury_count", "0"),
                    "location_description": row.get("location_description") or row.get("event_title", ""),
                    "source_name": row.get("source_name", "")
                })

    print(f"📊 Total records examined: {total_count}")
    print(f"📍 NER region events matched: {len(ner_events)}")

    if ner_events:
        with open(OUTPUT_NER_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ner_events[0].keys())
            writer.writeheader()
            writer.writerows(ner_events)
        print(f"✅ NER filtered catalog written to: {OUTPUT_NER_CSV}")
    else:
        print("⚠️ Warning: No NER events found matching the bounding box.")

if __name__ == "__main__":
    process_landslide_catalog()
