from .schemas import PredictedAttributes


def predict_from_preprocessed_image(
    image_bytes: bytes
) -> PredictedAttributes | None:
    """
    Component 2 prediction interface.

    Future workflow:
    1. Receive preprocessed image from Component 1.
    2. Load the trained Multi-Task CNN.
    3. Predict size, colour, length, orientation.
    4. Convert output indices to labels.
    5. Convert standardized length to millimetres.
    6. Return validated prediction data.

    The company dataset and trained model are
    not yet available.
    """

    return None
