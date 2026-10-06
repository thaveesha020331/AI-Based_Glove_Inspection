from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from src.main import app


client = TestClient(app)


SPEC = {
    "expected_size": "M",
    "expected_colour": "Blue",
    "min_length_mm": 235,
    "max_length_mm": 245,
    "allowed_orientations": [
        "Left",
        "Right"
    ]
}


def glove(
    glove_id="G001",
    size="M",
    colour="Blue",
    length=240,
    orientation="Left",
    defect=False
):

    return {
        "glove_id": glove_id,
        "batch_id": "B001",

        "predictions": {
            "size": size,
            "colour": colour,
            "length_mm": length,
            "orientation": orientation
        },

        "specifications": SPEC,

        "defect_found": defect
    }


# Test 1 - Health check
def test_health():

    response = client.get("/health")

    assert response.status_code == 200

    assert (
        response.json()["status"]
        == "running"
    )


# Test 2 - Image upload
def test_image_upload():

    stream = BytesIO()

    Image.new(
        "RGB",
        (224, 224),
        color="white"
    ).save(
        stream,
        format="PNG"
    )

    response = client.post(
        "/api/component2/verify",

        data={
            "glove_id": "G001",
            "batch_id": "B001"
        },

        files={
            "file": (
                "test.png",
                stream.getvalue(),
                "image/png"
            )
        }
    )

    assert response.status_code == 200

    assert (
        response.json()["mode"]
        == "awaiting_trained_model"
    )

    assert response.json()["sorting_allowed"] is False


# Test 3 - Valid specifications
def test_specification_match():

    response = client.post(
        "/api/component2/simulate",
        json=glove()
    )

    assert response.status_code == 200

    assert (
        response.json()
        ["specification_check"]["all_match"]
        is True
    )


# Test 4 - Colour mismatch
def test_colour_mismatch():

    response = client.post(
        "/api/component2/simulate",
        json=glove(colour="White")
    )

    assert response.status_code == 200

    assert (
        response.json()
        ["specification_check"]["checks"]["colour_match"]
        is False
    )


# Test 5 - Grade A
def test_grade_a():

    response = client.post(
        "/api/component2/grade/simulate",
        json=glove()
    )

    assert response.status_code == 200

    assert response.json()["quality_grade"] == "A"

    assert response.json()["sorting_allowed"] is False


# Test 6 - Grade B
def test_grade_b():

    response = client.post(
        "/api/component2/grade/simulate",
        json=glove(length=246)
    )

    assert response.status_code == 200

    assert response.json()["quality_grade"] == "B"


# Test 7 - Grade C
def test_grade_c():

    response = client.post(
        "/api/component2/grade/simulate",
        json=glove(length=248)
    )

    assert response.status_code == 200

    assert response.json()["quality_grade"] == "C"


# Test 8 - Reject a detected defect
def test_reject_defect():

    response = client.post(
        "/api/component2/grade/simulate",
        json=glove(defect=True)
    )

    assert response.status_code == 200

    assert (
        response.json()["quality_grade"]
        == "Reject"
    )


# Test 9 - Missing defect result
def test_missing_defect():

    response = client.post(
        "/api/component2/grade/simulate",
        json=glove(defect=None)
    )

    assert response.status_code == 200

    assert response.json()["quality_grade"] is None

    assert (
        response.json()["quality_status"]
        == "REVIEW_REQUIRED"
    )


# Test 10 - Batch consistency
def test_batch_consistency():

    first = glove("G001")
    second = glove("G002", size="S")

    response = client.post(
        "/api/component2/batches/simulate",

        json={
            "batch_id": "B001",
            "specifications": SPEC,

            "gloves": [
                {
                    "glove_id": "G001",
                    "predictions": first["predictions"]
                },
                {
                    "glove_id": "G002",
                    "predictions": second["predictions"]
                }
            ]
        }
    )

    assert response.status_code == 200

    result = response.json()

    assert result["total_gloves"] == 2
    assert result["consistent_gloves"] == 1
    assert result["inconsistent_gloves"] == 1

    assert (
        result["batch_consistency_percentage"]
        == 50.0
    )


# Test 11 - Batch grading
def test_batch_grading():

    first = glove("G001")
    second = glove("G002", length=246)

    response = client.post(
        "/api/component2/batches/grade/simulate",

        json={
            "batch_id": "B001",
            "specifications": SPEC,

            "gloves": [
                {
                    "glove_id": "G001",
                    "predictions": first["predictions"],
                    "defect_found": False
                },
                {
                    "glove_id": "G002",
                    "predictions": second["predictions"],
                    "defect_found": False
                }
            ]
        }
    )

    assert response.status_code == 200

    counts = response.json()["grade_counts"]

    assert counts["A"] == 1
    assert counts["B"] == 1


# Test 12 - Duplicate Glove IDs
def test_duplicate_gloves():

    sample = glove("G001")

    response = client.post(
        "/api/component2/batches/simulate",

        json={
            "batch_id": "B001",
            "specifications": SPEC,

            "gloves": [
                {
                    "glove_id": "G001",
                    "predictions": sample["predictions"]
                },
                {
                    "glove_id": "g001",
                    "predictions": sample["predictions"]
                }
            ]
        }
    )

    assert response.status_code == 422
