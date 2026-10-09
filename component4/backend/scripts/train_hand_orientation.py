"""Train the separate supporting left/right glove orientation classifier."""

import os

from app.services.hand_orientation import HandOrientationService


if __name__ == "__main__":
    dataset = os.getenv("HAND_IMAGE_DATASET_DIR", "data/raw/hand_images")
    artifacts = os.getenv("HAND_ORIENTATION_MODEL_DIR", "../../models")
    result = HandOrientationService(artifacts).train(dataset)
    print(result)
