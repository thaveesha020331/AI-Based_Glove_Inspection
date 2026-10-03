from tensorflow import keras
from tensorflow.keras import layers

from .model_config import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    IMAGE_CHANNELS,
    SIZE_CLASSES,
    COLOUR_CLASSES,
    ORIENTATION_CLASSES,
    BACKBONE_ALPHA
)


def build_multitask_model(pretrained=False):
    """
    Build Component 2's four-output CNN.

    pretrained=False:
        Random weights for architecture testing.

    pretrained=True:
        Initialize MobileNetV2 using ImageNet weights
        for later transfer learning.
    """

    # 1. Input supplied by Component 1
    inputs = keras.Input(
        shape=(
            IMAGE_HEIGHT,
            IMAGE_WIDTH,
            IMAGE_CHANNELS
        ),
        name="preprocessed_glove"
    )

    # 2. MobileNetV2 numerical scaling
    # Incoming RGB values must be in the range 0-255.
    x = layers.Rescaling(
        scale=1.0 / 127.5,
        offset=-1.0,
        name="mobilenet_scaling"
    )(inputs)

    # 3. Shared convolutional backbone
    backbone = keras.applications.MobileNetV2(
        input_shape=(
            IMAGE_HEIGHT,
            IMAGE_WIDTH,
            IMAGE_CHANNELS
        ),
        include_top=False,
        weights="imagenet" if pretrained else None,
        alpha=BACKBONE_ALPHA
    )

    # Freeze pretrained weights for the initial
    # transfer-learning phase.
    backbone.trainable = not pretrained

    features = backbone(
        x,
        training=False
    )

    # 4. Expose spatial features for Grad-CAM
    features = layers.Activation(
        "linear",
        name="gradcam_feature_map"
    )(features)

    # 5. Shared feature representation
    x = layers.GlobalAveragePooling2D(
        name="shared_pooling"
    )(features)

    x = layers.Dense(
        128,
        activation="relu",
        name="shared_dense"
    )(x)

    x = layers.Dropout(
        0.2,
        name="shared_dropout"
    )(x)

    # 6. Task 1 - Size classification
    size_output = layers.Dense(
        len(SIZE_CLASSES),
        activation="softmax",
        name="size"
    )(x)

    # 7. Task 2 - Colour classification
    colour_output = layers.Dense(
        len(COLOUR_CLASSES),
        activation="softmax",
        name="colour"
    )(x)

    # 8. Task 3 - Orientation classification
    orientation_output = layers.Dense(
        len(ORIENTATION_CLASSES),
        activation="softmax",
        name="orientation"
    )(x)

    # 9. Task 4 - Length regression
    # Future training will use standardized lengths.
    length_output = layers.Dense(
        1,
        activation="linear",
        name="length"
    )(x)

    # 10. Combine the four tasks
    model = keras.Model(
        inputs=inputs,
        outputs={
            "size": size_output,
            "colour": colour_output,
            "orientation": orientation_output,
            "length": length_output
        },
        name="component2_multitask_cnn"
    )

    # 11. Configure task-specific losses
    model.compile(
        optimizer=keras.optimizers.Adam(
            learning_rate=0.001
        ),
        loss={
            "size": (
                "sparse_categorical_crossentropy"
            ),
            "colour": (
                "sparse_categorical_crossentropy"
            ),
            "orientation": (
                "sparse_categorical_crossentropy"
            ),
            "length": keras.losses.Huber()
        },
        metrics={
            "size": [
                keras.metrics.SparseCategoricalAccuracy(
                    name="accuracy"
                )
            ],
            "colour": [
                keras.metrics.SparseCategoricalAccuracy(
                    name="accuracy"
                )
            ],
            "orientation": [
                keras.metrics.SparseCategoricalAccuracy(
                    name="accuracy"
                )
            ],
            "length": [
                keras.metrics.MeanAbsoluteError(
                    name="mae_scaled"
                )
            ]
        }
    )

    return model
