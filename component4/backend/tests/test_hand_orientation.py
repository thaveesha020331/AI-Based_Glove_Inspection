from pathlib import Path

import numpy as np
from PIL import Image

from app.services.hand_orientation import HandOrientationService, discover_dataset


def make_dataset(root: Path) -> Path:
    for label, offset in (("left", 20), ("right", 220)):
        folder = root / label
        folder.mkdir(parents=True)
        for index in range(12):
            array = np.full((48, 48), offset + index, dtype=np.uint8)
            Image.fromarray(array).save(folder / f"WIN_20261018_12_{index:02d}_00.jpg")
    return root


def test_discover_dataset_reports_classes_and_dimensions(tmp_path):
    audit = discover_dataset(make_dataset(tmp_path / "images"))
    assert audit["image_count"] == 24
    assert audit["class_distribution"] == {"left": 12, "right": 12}
    assert audit["corrupt_count"] == 0
    assert audit["dimensions"] == {"48x48": 24}


def test_orientation_training_and_prediction(tmp_path):
    dataset = make_dataset(tmp_path / "images")
    service = HandOrientationService(tmp_path / "models")
    result = service.train(dataset)
    assert result["state"] == "ready"
    assert result["evaluation"]["test"]["sample_size"] > 0
    prediction = service.predict(dataset / "left" / "WIN_20261018_12_00_00.jpg")
    assert prediction["state"] == "ready"
    assert prediction["label"] in {"left", "right"}
    assert service.predict(tmp_path / "not-an-image.txt")["state"] == "invalid_input"
