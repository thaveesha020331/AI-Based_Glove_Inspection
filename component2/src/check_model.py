import numpy as np
from tensorflow import keras

from .multitask_model import build_multitask_model

from .model_config import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    IMAGE_CHANNELS,
    SIZE_CLASSES,
    COLOUR_CLASSES,
    ORIENTATION_CLASSES,
    MODEL_DIR,
    UNTRAINED_MODEL_PATH
)


def main():

    print("Building Component 2 Multi-Task CNN...")

    model = build_multitask_model(
        pretrained=False
    )

    model.summary()

    # Dummy numerical input - not a glove image
    dummy_image = np.zeros(
        (
            1,
            IMAGE_HEIGHT,
            IMAGE_WIDTH,
            IMAGE_CHANNELS
        ),
        dtype=np.float32
    )

    # Forward pass
    outputs = model(
        dummy_image,
        training=False
    )

    expected_shapes = {
        "size": (1, len(SIZE_CLASSES)),
        "colour": (1, len(COLOUR_CLASSES)),
        "orientation": (
            1,
            len(ORIENTATION_CLASSES)
        ),
        "length": (1, 1)
    }

    for name, expected in expected_shapes.items():

        actual = tuple(
            outputs[name].shape
        )

        assert actual == expected, (
            f"{name}: expected {expected}, got {actual}"
        )

        print(f"{name} output shape: {actual}")

    # Classification probabilities must sum to one
    for task in [
        "size",
        "colour",
        "orientation"
    ]:

        probabilities = outputs[task].numpy()

        np.testing.assert_allclose(
            probabilities.sum(axis=1),
            [1.0],
            atol=1e-5
        )

    # Save untrained model
    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    model.save(
        UNTRAINED_MODEL_PATH
    )

    print("Model saved:", UNTRAINED_MODEL_PATH)

    # Verify loading
    loaded_model = keras.models.load_model(
        UNTRAINED_MODEL_PATH,
        compile=False
    )

    loaded_outputs = loaded_model(
        dummy_image,
        training=False
    )

    assert set(loaded_outputs.keys()) == set(
        expected_shapes.keys()
    )

    print("MODEL STRUCTURE TEST PASSED")
    print("IMPORTANT: CNN IS NOT TRAINED")


if __name__ == "__main__":
    main()
