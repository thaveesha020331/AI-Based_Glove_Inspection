import numpy as np
import pytest

from src.multitask_model import build_multitask_model
from src.gradcam import (
    compute_gradcam,
    save_gradcam_overlay
)

from src.model_config import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    IMAGE_CHANNELS
)


@pytest.fixture(scope="module")
def model():

    return build_multitask_model(
        pretrained=False
    )


@pytest.fixture(scope="module")
def example_image():

    rng = np.random.default_rng(42)

    return rng.integers(
        0,
        256,
        size=(
            IMAGE_HEIGHT,
            IMAGE_WIDTH,
            IMAGE_CHANNELS
        ),
        dtype=np.uint8
    )


# Test each classification head
@pytest.mark.parametrize(
    "task",
    ["size", "colour", "orientation"]
)
def test_gradcam_heads(
    model,
    example_image,
    task
):

    heatmap, details = compute_gradcam(
        model,
        example_image,
        task
    )

    assert heatmap.ndim == 2
    assert heatmap.size > 0

    assert np.isfinite(heatmap).all()

    assert heatmap.min() >= 0.0
    assert heatmap.max() <= 1.0 + 1e-6

    assert details["task"] == task
    assert "selected_class" in details


# Reject unsupported Grad-CAM task
def test_invalid_task(model, example_image):

    with pytest.raises(
        ValueError,
        match="Unsupported Grad-CAM task"
    ):

        compute_gradcam(
            model,
            example_image,
            "length"
        )


# Check visualization file creation
def test_save_overlay(
    model,
    example_image,
    tmp_path
):

    heatmap, _ = compute_gradcam(
        model,
        example_image,
        "size"
    )

    output = tmp_path / "demo_overlay.png"

    saved_path = save_gradcam_overlay(
        example_image,
        heatmap,
        output
    )

    assert output.exists()
    assert saved_path == str(output)
