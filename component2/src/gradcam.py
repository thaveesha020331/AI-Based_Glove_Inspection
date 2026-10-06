from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image

from .model_config import (
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    IMAGE_CHANNELS,
    SIZE_CLASSES,
    COLOUR_CLASSES,
    ORIENTATION_CLASSES
)


TASK_CLASSES = {
    "size": SIZE_CLASSES,
    "colour": COLOUR_CLASSES,
    "orientation": ORIENTATION_CLASSES
}


def compute_gradcam(
    model,
    image_array,
    task
):
    """
    Generate Grad-CAM for one classification head.

    Image requirements:
        RGB
        Model's configured width and height
        Pixel values in the range 0-255
    """

    if task not in TASK_CLASSES:
        raise ValueError(
            f"Unsupported Grad-CAM task: {task}"
        )

    expected_shape = (
        IMAGE_HEIGHT,
        IMAGE_WIDTH,
        IMAGE_CHANNELS
    )

    if image_array.shape != expected_shape:
        raise ValueError(
            f"Expected image shape {expected_shape}, "
            f"received {image_array.shape}"
        )

    image_tensor = tf.convert_to_tensor(
        image_array[np.newaxis, ...],
        dtype=tf.float32
    )

    # Get the shared CNN feature maps
    feature_layer = model.get_layer(
        "gradcam_feature_map"
    )

    # Get the selected prediction output
    output_layer = model.get_layer(task)

    # Intermediate model for gradient calculation
    grad_model = tf.keras.Model(
        inputs=model.inputs,
        outputs=[
            feature_layer.output,
            output_layer.output
        ]
    )

    # Calculate gradients
    with tf.GradientTape() as tape:

        feature_maps, predictions = grad_model(
            image_tensor,
            training=False
        )

        class_index = int(
            tf.argmax(predictions[0]).numpy()
        )

        class_score = predictions[
            :,
            class_index
        ]

    gradients = tape.gradient(
        class_score,
        feature_maps
    )

    if gradients is None:
        raise RuntimeError(
            "Grad-CAM gradients could not be calculated"
        )

    # Average gradients across height and width
    weights = tf.reduce_mean(
        gradients,
        axis=(1, 2),
        keepdims=True
    )

    # Combine weighted feature maps
    heatmap = tf.reduce_sum(
        feature_maps * weights,
        axis=-1
    )[0]

    # Keep positive contributions
    heatmap = tf.nn.relu(heatmap)

    # Normalize to 0-1
    maximum = tf.reduce_max(heatmap)

    heatmap = heatmap / tf.maximum(
        maximum,
        tf.constant(1e-8, dtype=heatmap.dtype)
    )

    selected_class = TASK_CLASSES[
        task
    ][class_index]

    selected_score = float(
        predictions[
            0,
            class_index
        ].numpy()
    )

    details = {
        "task": task,
        "selected_class": selected_class,
        "raw_class_score": selected_score
    }

    return heatmap.numpy(), details


def save_gradcam_overlay(
    image_array,
    heatmap,
    output_path
):
    """
    Save a red/yellow Grad-CAM overlay.

    This resizes the visualization heatmap only.
    It does not preprocess the model input.
    """

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Resize Grad-CAM to the image dimensions
    resized = tf.image.resize(
        heatmap[
            np.newaxis, :, :, np.newaxis
        ],
        (IMAGE_HEIGHT, IMAGE_WIDTH)
    )[0, :, :, 0].numpy()

    resized = np.clip(
        resized,
        0.0,
        1.0
    )

    # Create red/yellow activation colours
    colours = np.zeros_like(
        image_array,
        dtype=np.float32
    )

    colours[..., 0] = 255.0
    colours[..., 1] = 255.0 * (1.0 - resized)

    alpha = 0.55 * resized[..., np.newaxis]

    overlay = (
        image_array.astype(np.float32)
        * (1.0 - alpha)
        + colours * alpha
    )

    overlay = np.clip(
        overlay,
        0,
        255
    ).astype(np.uint8)

    Image.fromarray(overlay).save(
        output_path
    )

    return str(output_path)
