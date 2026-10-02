from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    model_validator
)


Orientation = Literal["Left", "Right"]


class PredictedAttributes(BaseModel):
    size: str = Field(min_length=1)
    colour: str = Field(min_length=1)
    length_mm: float = Field(gt=0)
    orientation: Orientation


class ProductionSpecifications(BaseModel):
    expected_size: str = Field(min_length=1)
    expected_colour: str = Field(min_length=1)

    min_length_mm: float = Field(gt=0)
    max_length_mm: float = Field(gt=0)

    allowed_orientations: list[Orientation] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_length(self):
        if self.min_length_mm > self.max_length_mm:
            raise ValueError(
                "Minimum length cannot exceed maximum"
            )
        return self


class SimulationRequest(BaseModel):
    glove_id: str = Field(min_length=1)
    batch_id: str = Field(min_length=1)

    predictions: PredictedAttributes
    specifications: ProductionSpecifications

    defect_found: bool | None = None


class BatchGloveRecord(BaseModel):
    glove_id: str = Field(min_length=1)
    predictions: PredictedAttributes
    defect_found: bool | None = None


class BatchAnalysisRequest(BaseModel):
    batch_id: str = Field(min_length=1)

    specifications: ProductionSpecifications

    gloves: list[BatchGloveRecord] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_gloves(self):
        ids = [
            glove.glove_id.strip().casefold()
            for glove in self.gloves
        ]

        if any(not glove_id for glove_id in ids):
            raise ValueError(
                "Glove IDs cannot be blank"
            )

        if len(ids) != len(set(ids)):
            raise ValueError(
                "Duplicate glove IDs are not allowed"
            )

        return self
