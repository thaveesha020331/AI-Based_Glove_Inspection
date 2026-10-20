"""Run inference with the exported MobileNetV2 TorchScript classifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms
from torchvision.transforms import InterpolationMode


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=Path("artifacts/final/mobilenet_v2_classifier.torchscript.pt"))
    parser.add_argument("--summary", type=Path, default=Path("artifacts/training_summary.json"))
    args = parser.parse_args()

    metadata = json.loads(args.summary.read_text(encoding="utf-8"))
    classes = metadata["classes"]
    image_size = metadata["best_hyperparameters"]["image_size"]
    preprocess = transforms.Compose(
        [
            transforms.Resize(int(image_size * 1.14), interpolation=InterpolationMode.BILINEAR),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    model = torch.jit.load(str(args.model), map_location="cpu").eval()
    with Image.open(args.image) as image, torch.inference_mode():
        logits = model(preprocess(image.convert("RGB")).unsqueeze(0))
        probabilities = torch.softmax(logits, dim=1)[0]
    result = {classes[index]: float(probability) for index, probability in enumerate(probabilities)}
    predicted = max(result, key=result.get)
    print(json.dumps({"prediction": predicted, "confidence": result[predicted], "probabilities": result}, indent=2))


if __name__ == "__main__":
    main()
