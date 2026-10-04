from .schemas import (
    PredictedAttributes,
    ProductionSpecifications
)


def check_specifications(
    predictions: PredictedAttributes,
    specifications: ProductionSpecifications
) -> dict:
    """
    Compare four glove attributes against
    manufacturing specifications.
    """

    checks = {
        "size_match": (
            predictions.size.strip().casefold()
            == specifications.expected_size.strip().casefold()
        ),

        "colour_match": (
            predictions.colour.strip().casefold()
            == specifications.expected_colour.strip().casefold()
        ),

        "length_match": (
            specifications.min_length_mm
            <= predictions.length_mm
            <= specifications.max_length_mm
        ),

        "orientation_match": (
            predictions.orientation
            in specifications.allowed_orientations
        )
    }

    mismatches = [
        key
        for key, matched in checks.items()
        if not matched
    ]

    return {
        "checks": checks,
        "all_match": all(checks.values()),
        "mismatch_reasons": mismatches
    }
