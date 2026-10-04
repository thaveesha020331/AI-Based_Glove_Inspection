from .schemas import (
    BatchGloveRecord,
    ProductionSpecifications
)

from .quality import check_specifications


def analyze_glove(
    glove: BatchGloveRecord,
    specifications: ProductionSpecifications
) -> dict:
    """
    Evaluate one glove against expected batch
    size and colour requirements.

    Also preserve the full four-attribute
    specification check.
    """

    verification = check_specifications(
        glove.predictions,
        specifications
    )

    checks = verification["checks"]

    # Batch consistency currently focuses on
    # size and colour.
    batch_mismatches = [
        attribute
        for attribute in ("size", "colour")
        if not checks[f"{attribute}_match"]
    ]

    return {
        "glove_id": glove.glove_id,

        "predictions": glove.predictions.model_dump(),

        "batch_consistent": (
            len(batch_mismatches) == 0
        ),

        "batch_mismatches": batch_mismatches,

        "specifications_match": (
            verification["all_match"]
        ),

        "specification_mismatches": [
            name.removesuffix("_match")
            for name in verification["mismatch_reasons"]
        ],

        "defect_found": glove.defect_found
    }
