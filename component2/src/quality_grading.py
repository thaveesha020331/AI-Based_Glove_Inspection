import json
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    model_validator
)

from .model_config import CONFIG_DIR
from .quality import check_specifications

from .schemas import (
    PredictedAttributes,
    ProductionSpecifications
)


class GradingPolicy(BaseModel):
    policy_name: str = Field(min_length=1)

    b_max_length_deviation_mm: float = Field(gt=0)
    c_max_length_deviation_mm: float = Field(gt=0)

    approved_for_production: Literal[False]

    @model_validator(mode="after")
    def validate_margins(self):
        if (
            self.b_max_length_deviation_mm
            >= self.c_max_length_deviation_mm
        ):
            raise ValueError(
                "Grade C margin must exceed Grade B"
            )

        return self


def load_policy() -> GradingPolicy:
    path = CONFIG_DIR / "grading_policy.json"

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:
        data = json.load(file)

    return GradingPolicy.model_validate(data)


def grade_glove(
    predictions: PredictedAttributes,
    specifications: ProductionSpecifications,
    defect_found: bool | None
) -> dict:
    """
    Assign a demonstration quality grade.

    This function is NOT approved for
    production sorting.
    """

    policy = load_policy()

    verification = check_specifications(
        predictions,
        specifications
    )

    checks = verification["checks"]

    # Distance outside permitted length limits
    length_deviation = max(
        specifications.min_length_mm
        - predictions.length_mm,

        predictions.length_mm
        - specifications.max_length_mm,

        0.0
    )

    # 1. Missing defect information
    if defect_found is None:

        grade = None
        status = "REVIEW_REQUIRED"

        reasons = [
            "Component 1 defect result is missing"
        ]

    # 2. Defect detected
    elif defect_found:

        grade = "Reject"
        status = "REJECTED"

        reasons = [
            "Component 1 reported a defect"
        ]

    # 3. Important attribute mismatches
    elif (
        not checks["size_match"]
        or not checks["colour_match"]
        or not checks["orientation_match"]
    ):

        grade = "Reject"
        status = "REJECTED"

        reasons = [
            key.removesuffix("_match")
            + " does not match specifications"

            for key in (
                "size_match",
                "colour_match",
                "orientation_match"
            )

            if not checks[key]
        ]

    # 4. All four attributes match
    elif checks["length_match"]:

        grade = "A"
        status = "CONFORMING"

        reasons = [
            "All attributes match, no defect reported"
        ]

    # 5. Small length deviation
    elif (
        length_deviation
        <= policy.b_max_length_deviation_mm
    ):

        grade = "B"
        status = "OUT_OF_SPECIFICATION"

        reasons = [
            "Length is outside limits within demo B margin"
        ]

    # 6. Larger length deviation
    elif (
        length_deviation
        <= policy.c_max_length_deviation_mm
    ):

        grade = "C"
        status = "OUT_OF_SPECIFICATION"

        reasons = [
            "Length is outside limits within demo C margin"
        ]

    # 7. Excessive length deviation
    else:

        grade = "Reject"
        status = "REJECTED"

        reasons = [
            "Length exceeds demo rejection margin"
        ]

    return {
        "mode": "simulation_unapproved_policy",

        "policy_name": policy.policy_name,

        "policy_approved": False,

        "quality_grade": grade,

        "quality_status": status,

        "length_deviation_mm": round(
            length_deviation,
            3
        ),

        "specification_check": verification,

        "reasons": reasons,

        "sorting_allowed": False
    }
