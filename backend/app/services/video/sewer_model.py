from __future__ import annotations

import torch
from torch import Tensor, nn
from torchvision.models import (
    ResNet18_Weights,
    resnet18,
)

NUM_CLASSES = 17


class SewerDefectClassifier(nn.Module):
    """PipeVision 17-label Sewer-ML classifier."""

    def __init__(
        self,
        num_classes: int = NUM_CLASSES,
        pretrained: bool = True,
    ) -> None:
        super().__init__()

        weights = ResNet18_Weights.DEFAULT if pretrained else None

        backbone = resnet18(
            weights=weights,
        )

        feature_count = backbone.fc.in_features

        backbone.fc = nn.Sequential(
            nn.Dropout(p=0.2),
            nn.Linear(
                feature_count,
                num_classes,
            ),
        )

        self.backbone = backbone

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
