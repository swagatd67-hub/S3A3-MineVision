from __future__ import annotations

from pathlib import Path

import torch
from torch import Tensor, nn
from torchvision.models import (
    ResNet18_Weights,
    resnet18,
)

NUM_CLASSES = 17


class ResNetBackbone(nn.Module):
    """ResNet-18 backbone with a custom dropout-linear classifier head."""

    def __init__(
        self,
        num_classes: int,
        pretrained: bool = True,
    ) -> None:
        super().__init__()
        weights = ResNet18_Weights.DEFAULT if pretrained else None
        base_resnet = resnet18(weights=weights)

        self.conv1 = base_resnet.conv1
        self.bn1 = base_resnet.bn1
        self.relu = base_resnet.relu
        self.maxpool = base_resnet.maxpool
        self.layer1 = base_resnet.layer1
        self.layer2 = base_resnet.layer2
        self.layer3 = base_resnet.layer3
        self.layer4 = base_resnet.layer4
        self.avgpool = base_resnet.avgpool

        feature_count = base_resnet.fc.in_features
        self.fc: nn.Module = nn.Sequential(
            nn.Dropout(p=0.2),
            nn.Linear(
                feature_count,
                num_classes,
            ),
        )

    def forward(self, x: Tensor) -> Tensor:
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        return self.fc(x)


class SewerDefectClassifier(nn.Module):
    """PipeVision 17-label Sewer-ML classifier."""

    def __init__(
        self,
        num_classes: int = NUM_CLASSES,
        pretrained: bool = True,
    ) -> None:
        super().__init__()
        self.backbone = ResNetBackbone(
            num_classes=num_classes,
            pretrained=pretrained,
        )

    def forward(
        self,
        images: Tensor,
    ) -> Tensor:
        return self.backbone(images)

    @staticmethod
    def probabilities(
        logits: Tensor,
    ) -> Tensor:
        return torch.sigmoid(logits)


def load_sewer_classifier(
    checkpoint_path: str | Path,
    device: str | torch.device | None = None,
) -> SewerDefectClassifier:
    """Safely load a trained SewerDefectClassifier from a checkpoint file."""
    path = Path(checkpoint_path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint file not found: {path}")

    if device is None:
        device_obj = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    elif isinstance(device, str):
        device_obj = torch.device(device)
    else:
        device_obj = device

    try:
        checkpoint = torch.load(path, map_location=device_obj)
    except Exception as exc:
        raise ValueError(f"Failed to load checkpoint file {path}: {exc}") from exc

    if not isinstance(checkpoint, dict):
        raise TypeError(f"Invalid checkpoint format in {path}: expected dict")

    if "model_state_dict" not in checkpoint:
        raise ValueError(f"Invalid checkpoint format in {path}: missing 'model_state_dict'")

    from backend.app.services.video.sewer_dataset import DEFECT_CLASSES

    checkpoint_classes = checkpoint.get("classes")
    if checkpoint_classes is not None and list(checkpoint_classes) != list(
        DEFECT_CLASSES
    ):
        raise ValueError(
            f"Checkpoint classes {checkpoint_classes} do not match expected DEFECT_CLASSES {DEFECT_CLASSES}"
        )

    model = SewerDefectClassifier(
        num_classes=len(DEFECT_CLASSES),
        pretrained=False,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device_obj)
    model.eval()

    return model
