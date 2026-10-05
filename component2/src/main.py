import io

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile
)

from PIL import (
    Image,
    UnidentifiedImageError
)

from .model_config import (
    IMAGE_WIDTH,
    IMAGE_HEIGHT
)

from .schemas import (
    SimulationRequest,
    BatchAnalysisRequest
)

from .predictor import (
    predict_from_preprocessed_image
)

from .quality import check_specifications
from .batch_manager import analyze_batch
from .quality_grading import grade_glove


app = FastAPI(
    title="Component 2 - Glove Quality Verification",
    version="0.1.0"
)

MAX_IMAGE_BYTES = 10 * 1024 * 1024


# API 1 - Health check
@app.get("/health")
def health():

    return {
        "component": "component2",
        "status": "running",
        "model_status": "untrained"
    }


# API 2 - Receive image from Component 1
@app.post("/api/component2/verify")
async def verify_glove(
    file: UploadFile = File(...),
    glove_id: str = Form(..., min_length=1),
    batch_id: str = Form(..., min_length=1),
    defect_found: bool | None = Form(None)
):

    # Read file with maximum size protection
    image_bytes = await file.read(
        MAX_IMAGE_BYTES + 1
    )

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Image is empty"
        )

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image exceeds 10 MB"
        )

    # Validate only; Component 1 owns preprocessing.
    try:
        with Image.open(
            io.BytesIO(image_bytes)
        ) as image:

            if image.format not in ("PNG", "JPEG"):
                raise HTTPException(
                    status_code=400,
                    detail="Only PNG/JPEG files supported"
                )

            width, height = image.size

            if image.mode != "RGB":
                raise HTTPException(
                    status_code=400,
                    detail="Expected RGB image"
                )

            if (width, height) != (
                IMAGE_WIDTH,
                IMAGE_HEIGHT
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Unexpected image dimensions"
                )

            image.verify()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid image file"
        )

    predictions = predict_from_preprocessed_image(
        image_bytes
    )

    # Real AI predictions are unavailable
    if predictions is None:
        return {
            "glove_id": glove_id,
            "batch_id": batch_id,

            "image_received": True,

            "defect_found": defect_found,

            "mode": "awaiting_trained_model",

            "predictions": None,

            "specification_check": None,

            "batch_consistency": "not_analyzed",

            "quality_grade": None,

            "sorting_allowed": False
        }

    raise HTTPException(
        status_code=501,
        detail="Trained-model integration is not ready"
    )


# API 3 - Specification simulation
@app.post("/api/component2/simulate")
def simulate_verification(
    request: SimulationRequest
):

    result = check_specifications(
        request.predictions,
        request.specifications
    )

    return {
        "glove_id": request.glove_id,
        "batch_id": request.batch_id,

        "mode": "manual_simulation_only",

        "specification_check": result,

        "sorting_allowed": False
    }


# API 4 - Batch consistency simulation
@app.post("/api/component2/batches/simulate")
def simulate_batch(
    request: BatchAnalysisRequest
):

    return analyze_batch(request)


# API 5 - Individual grading simulation
@app.post("/api/component2/grade/simulate")
def simulate_grade(
    request: SimulationRequest
):

    assessment = grade_glove(
        predictions=request.predictions,
        specifications=request.specifications,
        defect_found=request.defect_found
    )

    return {
        "glove_id": request.glove_id,
        "batch_id": request.batch_id,

        "predictions": (
            request.predictions.model_dump()
        ),

        **assessment
    }


# API 6 - Batch grading simulation
@app.post("/api/component2/batches/grade/simulate")
def simulate_batch_grades(
    request: BatchAnalysisRequest
):

    # Calculate size/colour batch consistency
    report = analyze_batch(request)

    grade_counts = {
        "A": 0,
        "B": 0,
        "C": 0,
        "Reject": 0,
        "Needs Review": 0
    }

    # Calculate demonstration grades
    for glove, result in zip(
        request.gloves,
        report["results"]
    ):

        assessment = grade_glove(
            predictions=glove.predictions,
            specifications=request.specifications,
            defect_found=glove.defect_found
        )

        result["quality_assessment"] = assessment

        grade = (
            assessment["quality_grade"]
            or "Needs Review"
        )

        grade_counts[grade] += 1

    report["grade_counts"] = grade_counts

    report["grading_mode"] = (
        "simulation_unapproved_policy"
    )

    report["policy_approved"] = False
    report["sorting_allowed"] = False

    return report
