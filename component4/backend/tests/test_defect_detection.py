from types import SimpleNamespace

from ml.defect_detection.predict import DefectDetector


class FakeTensor:
    def __init__(self, values):
        self.values = values

    def cpu(self):
        return self

    def tolist(self):
        return self.values


class FakeResult:
    names = {0: "defect-Detection", 1: "Pinhole", 2: "Tear"}
    boxes = SimpleNamespace(
        cls=FakeTensor([2, 1]),
        conf=FakeTensor([0.73, 0.91]),
        xyxy=FakeTensor([[1, 2, 30, 40], [5, 6, 50, 60]]),
    )

    def plot(self):
        return "annotated"


class FakeModel:
    def predict(self, **_kwargs):
        return [FakeResult()]


def test_detector_returns_highest_confidence_defect_first(tmp_path):
    detector = DefectDetector(tmp_path / "unused.pt")
    detector._model = FakeModel()

    result = detector.predict("frame", annotate=True)

    assert result["defective"] is True
    assert result["category"] == "Pinhole"
    assert result["confidence"] == 0.91
    assert [item["category"] for item in result["detections"]] == ["Pinhole", "Tear"]
    assert result["annotated_frame"] == "annotated"
