import json

import numpy as np
from PIL import Image
from tensorflow import keras

from .gradcam import (
    compute_gradcam,
    save_gradcam_overlay
)

from .model_config import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    IMAGE_CHANNELS,
    RUNS_DIR,
    UNTRAINED_MODEL_PATH
)


def main():

    if not UNTRAINED_MODEL_PATH.exists():
        raise FileNotFoundError(
            "Untrained model not found. "
            "Run python -m src.check_model first."
        )

    # Load saved CNN
    model = keras.models.load_model(
        UNTRAINED_MODEL_PATH,
        compile=False
    )

    # Generate a synthetic technical test image
    image = np.full(
        (
            IMAGE_HEIGHT,
            IMAGE_WIDTH,
            IMAGE_CHANNELS
        ),
        235,
        dtype=np.uint8
    )

    image[40:180, 70:155] = [
        30,
        110,
        215
    ]

    # Result folder
    output_dir = RUNS_DIR / "gradcam"

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    Image.fromarray(image).save(
        output_dir / "demo_input.png"
    )

    results = []

    # Grad-CAM for three classification heads
    for task in [
        "size",
        "colour",
        "orientation"
    ]:

        heatmap, details = compute_gradcam(
            model,
            image,
            task
        )

        output_path = (
            output_dir
            / f"{task}_UNTRAINED_DEMO.png"
        )

        saved_path = save_gradcam_overlay(
            image,
            heatmap,
            output_path
        )

        results.append({
            **details,
            "overlay_path": saved_path
        })

        print(
            f"{task}: "
            f"{details['selected_class']}"
        )

        print("Saved:", saved_path)

    # Save demonstration metadata
    metadata = {
        "model_status": "UNTRAINED",
        "mode": "technical_demonstration_only",
        "valid_research_explanation": False,
        "results": results
    }

    with (
        output_dir / "demo_metadata.json"
    ).open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=2
        )

    print("GRAD-CAM DEMONSTRATION COMPLETED")
    print("These results are from an untrained model.")


if __name__ == "__main__":
    main()
