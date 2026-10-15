"""
Download the RDD2022 dataset images from the CRDDC'2022 competition.
The actual images are hosted as zip files that need manual download.

This script creates a README with exact download instructions.
"""

README = """
# RDD2022 Dataset — Download Instructions

The GitHub repo (raw_rdd2022/) only has code, not the actual images.
The images need to be downloaded separately.

## Option 1: CRDDC'2022 Website (Recommended)
1. Go to: https://crddc2022.sekilab.global/data/
2. Register/Login
3. Download:
   - RDD2022_all_countries.zip (all countries, ~5GB)
   - OR just download India subset if available

## Option 2: Mendeley Data (Direct, No Login)
1. Go to: https://data.mendeley.com/datasets/5ty2wb6gvg/1
2. Click "Download" → Downloads as .zip (~4.5 GB)
3. This is the RDD2020 dataset (predecessor, also works great)

## Option 3: Kaggle (Easiest)
1. Go to: https://www.kaggle.com/datasets/arnavr10880/road-damage-detection-2022
2. Download the dataset
3. Extract to this folder

## After downloading:
Extract the zip and you'll see folders like:
  - India/
  - Japan/
  - Czech/
  - etc.

Each country folder has:
  - train/images/   → .jpg road photos
  - train/annotations/xmls/  → Pascal VOC .xml bounding box labels

Run the converter script:
  python3 ../../ml/training/convert_rdd2022_to_yolo.py
"""

import os
output_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "road_damage"
)
with open(os.path.join(output_dir, "DOWNLOAD_INSTRUCTIONS.md"), "w") as f:
    f.write(README)
print("✅ Created DOWNLOAD_INSTRUCTIONS.md in data/road_damage/")
print()
print("The 47K images are too large to auto-download.")
print("Please follow the instructions in the file above.")
print()
print("Quickest option: Kaggle")
print("  https://www.kaggle.com/datasets/arnavr10880/road-damage-detection-2022")
