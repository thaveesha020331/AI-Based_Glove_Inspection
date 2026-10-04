from .schemas import BatchAnalysisRequest
from .batch_consistency import analyze_glove


def analyze_batch(
    request: BatchAnalysisRequest
) -> dict:
    """
    Analyze all gloves submitted in one request.
    """

    results = [
        analyze_glove(
            glove,
            request.specifications
        )
        for glove in request.gloves
    ]

    total = len(results)

    consistent = sum(
        result["batch_consistent"]
        for result in results
    )

    size_mismatches = sum(
        "size" in result["batch_mismatches"]
        for result in results
    )

    colour_mismatches = sum(
        "colour" in result["batch_mismatches"]
        for result in results
    )

    specification_failures = sum(
        not result["specifications_match"]
        for result in results
    )

    warnings = []

    if size_mismatches:
        warnings.append(
            f"{size_mismatches} size mismatch(es)"
        )

    if colour_mismatches:
        warnings.append(
            f"{colour_mismatches} colour mismatch(es)"
        )

    return {
        "batch_id": request.batch_id,

        "mode": "manual_simulation_only",

        "assessment_scope": "submitted_gloves_only",

        "total_gloves": total,

        "consistent_gloves": consistent,

        "inconsistent_gloves": total - consistent,

        "batch_consistency_percentage": round(
            consistent / total * 100,
            2
        ),

        "size_mismatch_count": size_mismatches,

        "colour_mismatch_count": colour_mismatches,

        "specification_nonconforming_gloves":
            specification_failures,

        "batch_status": (
            "Consistent"
            if consistent == total
            else "Inconsistent"
        ),

        "warnings": warnings,

        "results": results,

        "sorting_allowed": False
    }
