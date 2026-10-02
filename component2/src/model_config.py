import json
from pathlib import Path

# Component 2 root directory
BASE_DIR = Path(__file__).resolve().parents[1]

CONFIG_DIR = BASE_DIR / "configs"
DATASET_DIR = BASE_DIR / "datasets"
MODEL_DIR = BASE_DIR / "models"
RUNS_DIR = BASE_DIR / "runs"

# Load configuration
with (CONFIG_DIR / "model_config.json").open(
    "r",
    encoding="utf-8"
) as file:
    config = json.load(file)

IMAGE_HEIGHT = config["image_height"]
IMAGE_WIDTH = config["image_width"]
IMAGE_CHANNELS = config["image_channels"]

PIXEL_RANGE = config["pixel_range"]

SIZE_CLASSES = config["size_classes"]
COLOUR_CLASSES = config["colour_classes"]
ORIENTATION_CLASSES = config["orientation_classes"]

BACKBONE_ALPHA = config["backbone_alpha"]

if PIXEL_RANGE != "0_255":
    raise ValueError(
        "Current model expects RGB pixel values 0-255"
    )

UNTRAINED_MODEL_PATH = (
    MODEL_DIR / "multitask_untrained.keras"
)

TRAINED_MODEL_PATH = (
    MODEL_DIR / "best_multitask_model.keras"
)
