from __future__ import annotations

import csv
import glob
from pathlib import Path

import torch
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader

from backend.app.services.video.sewer_dataset import (
    DEFECT_CLASSES,
    SewerMLDataset,
)
from backend.app.services.video.sewer_model import (
    SewerDefectClassifier,
)


IMAGE_DIR = Path(
    "approved-data/sewer-ml/images/train00_subset"
)

CSV_PATH = Path(
    "approved-data/sewer-ml/extracted/SewerML_Train.csv"
)

VAL_SPLIT = Path(
    "approved-data/sewer-ml/splits/val.csv"
)

CHECKPOINT = Path(
    "artifacts/sewer_model_v2/best.pt"
)


def fbeta_score(
    y_true: torch.Tensor,
    y_pred: torch.Tensor,
    beta: float = 2.0,
) -> float:
    beta_squared = beta ** 2

    true_positive = (
        (y_true == 1) & (y_pred == 1)
    ).sum().item()

    false_positive = (
        (y_true == 0) & (y_pred == 1)
    ).sum().item()

    false_negative = (
        (y_true == 1) & (y_pred == 0)
    ).sum().item()

    precision_denominator = (
        true_positive + false_positive
    )

    recall_denominator = (
        true_positive + false_negative
    )

    precision = (
        true_positive / precision_denominator
        if precision_denominator > 0
        else 0.0
    )

    recall = (
        true_positive / recall_denominator
        if recall_denominator > 0
        else 0.0
    )

    denominator = (
        beta_squared * precision + recall
    )

    if denominator == 0:
        return 0.0

    return (
        (1 + beta_squared)
        * precision
        * recall
        / denominator
    )


def main() -> None:
    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print("Device:", device)

    if device.type == "cuda":
        print(
            "GPU:",
            torch.cuda.get_device_name(0),
        )

    # Read the exact validation split used by Model V2.
    with VAL_SPLIT.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        val_filenames = [
            row["Filename"]
            for row in csv.DictReader(handle)
        ]

    # Make sure those files actually exist.
    available_files = {
        Path(path).name
        for path in glob.glob(
            str(IMAGE_DIR / "*.png")
        )
    }

    missing = [
        filename
        for filename in val_filenames
        if filename not in available_files
    ]

    if missing:
        raise RuntimeError(
            f"{len(missing)} validation images are missing. "
            f"Examples: {missing[:10]}"
        )

    val_dataset = SewerMLDataset(
        image_dir=IMAGE_DIR,
        csv_path=CSV_PATH,
        filenames=val_filenames,
        image_size=224,
        training=False,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=8,
        shuffle=False,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )

    print(
        "Validation samples:",
        len(val_dataset),
    )

    model = SewerDefectClassifier(
        pretrained=False,
    )

    checkpoint = torch.load(
        CHECKPOINT,
        map_location=device,
        weights_only=False,
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model.to(device)
    model.eval()

    all_targets: list[torch.Tensor] = []
    all_probabilities: list[torch.Tensor] = []

    with torch.no_grad():
        for images, targets, _ in val_loader:
            images = images.to(
                device,
                non_blocking=True,
            )

            logits = model(images)

            probabilities = torch.sigmoid(
                logits
            )

            all_targets.append(
                targets.cpu()
            )

            all_probabilities.append(
                probabilities.cpu()
            )

    y_true = torch.cat(
        all_targets,
        dim=0,
    )

    y_prob = torch.cat(
        all_probabilities,
        dim=0,
    )

    threshold = 0.5

    y_pred = (
        y_prob >= threshold
    ).int()

    print(
        f"Threshold: {threshold}"
    )

    print()
    print(
        f"{'CLASS':<6}"
        f"{'SUPPORT':>10}"
        f"{'PRECISION':>12}"
        f"{'RECALL':>10}"
        f"{'F1':>10}"
        f"{'F2':>10}"
    )

    print("-" * 58)

    for index, class_name in enumerate(
        DEFECT_CLASSES
    ):
        true_class = y_true[:, index]
        pred_class = y_pred[:, index]

        support = int(
            true_class.sum().item()
        )

        precision = precision_score(
            true_class.numpy(),
            pred_class.numpy(),
            zero_division=0,
        )

        recall = recall_score(
            true_class.numpy(),
            pred_class.numpy(),
            zero_division=0,
        )

        f1 = f1_score(
            true_class.numpy(),
            pred_class.numpy(),
            zero_division=0,
        )

        f2 = fbeta_score(
            true_class,
            pred_class,
            beta=2.0,
        )

        print(
            f"{class_name:<6}"
            f"{support:>10}"
            f"{precision:>12.3f}"
            f"{recall:>10.3f}"
            f"{f1:>10.3f}"
            f"{f2:>10.3f}"
        )

    macro_f1 = f1_score(
        y_true.numpy(),
        y_pred.numpy(),
        average="macro",
        zero_division=0,
    )

    macro_recall = recall_score(
        y_true.numpy(),
        y_pred.numpy(),
        average="macro",
        zero_division=0,
    )

    print()
    print(
        f"Macro F1: {macro_f1:.3f}"
    )

    print(
        f"Macro Recall: {macro_recall:.3f}"
    )


if __name__ == "__main__":
    main()