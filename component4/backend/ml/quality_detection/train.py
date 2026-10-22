"""Convert COCO annotations and train Ultralytics YOLO on train/valid only."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


NAMES = {0: "Other defect", 1: "Pinhole", 2: "Tear"}
CATEGORY_MAP = {0: 0, 1: 1, 2: 2, 3: 0}


def convert_split(dataset: Path, split: str, labels_root: Path) -> None:
    data = json.loads((dataset / split / "_annotations.coco.json").read_text(encoding="utf-8"))
    labels = labels_root / split
    labels.mkdir(parents=True, exist_ok=True)
    images_root = labels_root.parent / "images" / split
    images_root.mkdir(parents=True, exist_ok=True)
    images = {item["id"]: item for item in data["images"]}
    grouped = {item["id"]: [] for item in data["images"]}
    for annotation in data["annotations"]:
        image = images[annotation["image_id"]]
        x, y, width, height = annotation["bbox"]
        grouped[image["id"]].append(
            f"{CATEGORY_MAP[annotation['category_id']]} {(x + width / 2) / image['width']:.8f} "
            f"{(y + height / 2) / image['height']:.8f} {width / image['width']:.8f} {height / image['height']:.8f}"
        )
    for image in data["images"]:
        shutil.copy2(dataset / split / image["file_name"], images_root / image["file_name"])
        (labels / f"{Path(image['file_name']).stem}.txt").write_text(
            "\n".join(grouped[image["id"]]), encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path(__file__).parents[3] / "dataset")
    parser.add_argument("--output", type=Path, default=Path(__file__).parents[1] / "yolo_dataset")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=30)
    args = parser.parse_args()
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "Ultralytics/PyTorch is required. Python 3.15 has no compatible "
            "PyTorch wheel in this environment; use Python 3.12-3.14 and install "
            "ml/quality_detection/requirements.txt."
        ) from exc
    for split in ("train", "valid", "test"):
        convert_split(args.dataset, split, args.output / "labels")
    yaml = args.output / "dataset.yaml"
    yaml.write_text(
        f"path: {args.output.resolve()}\ntrain: images/train\nval: images/valid\ntest: images/test\n"
        f"names: {json.dumps(NAMES)}\n",
        encoding="utf-8",
    )
    model = YOLO(args.model)
    model.train(data=str(yaml), epochs=args.epochs, imgsz=640, project=str(args.output / "runs"), name="glove_defects")
    evaluation = model.val(data=str(yaml), split="test")
    metrics = getattr(evaluation, "results_dict", {})
    serializable = {str(key): float(value) for key, value in metrics.items() if isinstance(value, (int, float))}
    destination = Path(__file__).parents[2] / "models" / "glove_defect_model.pt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    best = args.output / "runs" / "glove_defects" / "weights" / "best.pt"
    if best.is_file():
        shutil.copy2(best, destination)
    destination.with_suffix(".metrics.json").write_text(
        json.dumps({"dataset": str(args.dataset.resolve()), "epochs": args.epochs,
                    "classes": NAMES, "test_metrics": serializable}, indent=2),
        encoding="utf-8",
    )
    print(f"Training complete. Weights: {destination}")
    print(json.dumps(serializable, indent=2))


if __name__ == "__main__":
    main()
