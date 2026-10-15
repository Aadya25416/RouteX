"""
Convert RDD2022 Pascal VOC XML annotations to YOLO format.
Run AFTER downloading the RDD2022 dataset images.

Usage:
    python3 ml/training/convert_rdd2022_to_yolo.py
"""

import os
import xml.etree.ElementTree as ET
import random
import shutil
from pathlib import Path

# === CONFIG ===
# Where you extracted the RDD2022 zip
RDD_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "road_damage", "raw_rdd2022"
)
# Where YOLO-formatted data goes
YOLO_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "road_damage"
)

TRAIN_SPLIT = 0.8  # 80% train, 20% val

# RDD2022 class → YOLO class mapping
# Classes 0-3 from RDD2022, classes 4-5 will be added from satellite data later
CLASS_MAP = {
    "D00": 1,  # longitudinal_crack
    "D10": 2,  # transverse_crack
    "D20": 3,  # alligator_crack
    "D40": 0,  # pothole (most important, gets class 0)
}

CLASS_NAMES = {
    0: "pothole",
    1: "longitudinal_crack",
    2: "transverse_crack",
    3: "alligator_crack",
    4: "landslide_debris",       # Added from satellite/ISRO data
    5: "flood_waterlogging",     # Added from satellite/ISRO data
}


def convert_voc_to_yolo(xml_path: str, img_width: int, img_height: int) -> list[str]:
    """Convert a single VOC XML annotation to YOLO format lines."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    yolo_lines = []

    for obj in root.findall("object"):
        class_name = obj.find("name").text
        if class_name not in CLASS_MAP:
            continue
        class_id = CLASS_MAP[class_name]

        bbox = obj.find("bndbox")
        xmin = float(bbox.find("xmin").text)
        ymin = float(bbox.find("ymin").text)
        xmax = float(bbox.find("xmax").text)
        ymax = float(bbox.find("ymax").text)

        # Clamp to image bounds
        xmin = max(0, min(xmin, img_width))
        xmax = max(0, min(xmax, img_width))
        ymin = max(0, min(ymin, img_height))
        ymax = max(0, min(ymax, img_height))

        # Skip degenerate boxes
        if xmax <= xmin or ymax <= ymin:
            continue

        # Convert to YOLO format (normalized center + size)
        cx = ((xmin + xmax) / 2) / img_width
        cy = ((ymin + ymax) / 2) / img_height
        w = (xmax - xmin) / img_width
        h = (ymax - ymin) / img_height

        yolo_lines.append(f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    return yolo_lines


def get_image_size_from_xml(xml_path: str) -> tuple[int, int]:
    """Extract image size from VOC XML."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    size = root.find("size")
    if size is not None:
        w = int(size.find("width").text)
        h = int(size.find("height").text)
        return w, h
    return 640, 480  # default fallback


def main():
    print("=" * 60)
    print("  RDD2022 → YOLO Format Converter")
    print("=" * 60)

    # Find all XML annotation files
    xml_files = []
    img_files = {}

    for root_dir, dirs, files in os.walk(RDD_ROOT):
        for f in files:
            if f.endswith(".xml"):
                xml_path = os.path.join(root_dir, f)
                # Find corresponding image
                img_name = f.replace(".xml", ".jpg")
                img_candidates = [
                    os.path.join(root_dir, img_name),
                    os.path.join(root_dir, "..", "images", img_name),
                    os.path.join(root_dir, "..", img_name),
                ]
                for img_path in img_candidates:
                    if os.path.exists(img_path):
                        xml_files.append(xml_path)
                        img_files[xml_path] = os.path.abspath(img_path)
                        break

    if not xml_files:
        print("❌ No XML annotation files found!")
        print(f"   Searched in: {RDD_ROOT}")
        print()
        print("   Have you downloaded the RDD2022 dataset yet?")
        print("   See: data/road_damage/DOWNLOAD_INSTRUCTIONS.md")
        return

    print(f"Found {len(xml_files)} annotated images")

    # Shuffle and split
    random.seed(42)
    random.shuffle(xml_files)
    split_idx = int(len(xml_files) * TRAIN_SPLIT)
    train_xmls = xml_files[:split_idx]
    val_xmls = xml_files[split_idx:]

    print(f"Train: {len(train_xmls)} images")
    print(f"Val:   {len(val_xmls)} images")
    print()

    # Create output directories
    for split in ["train", "val"]:
        os.makedirs(os.path.join(YOLO_ROOT, "images", split), exist_ok=True)
        os.makedirs(os.path.join(YOLO_ROOT, "labels", split), exist_ok=True)

    # Convert
    stats = {"total_images": 0, "total_boxes": 0, "skipped": 0}

    for split_name, split_xmls in [("train", train_xmls), ("val", val_xmls)]:
        for xml_path in split_xmls:
            img_path = img_files.get(xml_path)
            if not img_path:
                stats["skipped"] += 1
                continue

            # Get image size
            w, h = get_image_size_from_xml(xml_path)

            # Convert annotations
            yolo_lines = convert_voc_to_yolo(xml_path, w, h)
            if not yolo_lines:
                stats["skipped"] += 1
                continue

            # Copy image
            img_name = os.path.basename(img_path)
            # Make unique name to avoid collisions between countries
            parent = os.path.basename(os.path.dirname(os.path.dirname(xml_path)))
            unique_name = f"{parent}_{img_name}"
            dst_img = os.path.join(YOLO_ROOT, "images", split_name, unique_name)
            shutil.copy2(img_path, dst_img)

            # Write label
            label_name = unique_name.replace(".jpg", ".txt").replace(".png", ".txt")
            dst_label = os.path.join(YOLO_ROOT, "labels", split_name, label_name)
            with open(dst_label, "w") as f:
                f.write("\n".join(yolo_lines))

            stats["total_images"] += 1
            stats["total_boxes"] += len(yolo_lines)

    print(f"✅ Converted {stats['total_images']} images, {stats['total_boxes']} bounding boxes")
    print(f"   Skipped {stats['skipped']} images (no valid annotations)")

    # Create dataset YAML config
    yaml_path = os.path.join(YOLO_ROOT, "road_damage.yaml")
    yaml_content = f"""# NER-LINK Road Damage Detection Dataset
# Auto-generated by convert_rdd2022_to_yolo.py

path: {YOLO_ROOT}
train: images/train
val: images/val

# Number of classes
nc: 6

# Class names
names:
  0: pothole
  1: longitudinal_crack
  2: transverse_crack
  3: alligator_crack
  4: landslide_debris
  5: flood_waterlogging
"""
    with open(yaml_path, "w") as f:
        f.write(yaml_content)

    print(f"✅ Created dataset config: {yaml_path}")
    print()
    print("Next step: Train YOLO26")
    print("  from ultralytics import YOLO")
    print('  model = YOLO("yolo26n.pt")')
    print(f'  model.train(data="{yaml_path}", epochs=100, imgsz=640)')


if __name__ == "__main__":
    main()
