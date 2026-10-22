"""Validate the extracted dataset without modifying any original files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def validate(root: Path) -> dict:
    result = {"root": str(root), "splits": {}, "category_mapping": {
        "0": "Other defect (generic source label)",
        "1": "Pinhole", "2": "Tear",
        "3": "Other defect (duplicate generic source label)",
    }}
    for split in ("train", "valid", "test"):
        folder = root / split
        annotation_file = folder / "_annotations.coco.json"
        data = json.loads(annotation_file.read_text(encoding="utf-8"))
        by_id = {image["id"]: image for image in data["images"]}
        missing, invalid = [], []
        for image in data["images"]:
            path = folder / image["file_name"]
            if not path.is_file():
                missing.append(image["file_name"])
                continue
            with Image.open(path) as opened:
                if opened.size != (image["width"], image["height"]):
                    invalid.append(f"{image['file_name']}: dimensions differ")
        for annotation in data["annotations"]:
            x, y, width, height = annotation["bbox"]
            image = by_id.get(annotation["image_id"])
            if not image or width <= 0 or height <= 0 or x < 0 or y < 0 or x + width > image["width"] or y + height > image["height"]:
                invalid.append(f"annotation {annotation['id']}: invalid bbox")
        result["splits"][split] = {
            "images": len(data["images"]), "annotations": len(data["annotations"]),
            "missing_images": missing, "invalid_records": invalid,
            "categories": data["categories"],
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).parents[3] / "dataset")
    args = parser.parse_args()
    print(json.dumps(validate(args.dataset), indent=2))
