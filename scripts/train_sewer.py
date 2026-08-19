from __future__ import annotations

import csv
import json
from pathlib import Path

import torch
from sklearn.metrics import f1_score, recall_score
from torch import nn
from torch.amp import GradScaler, autocast
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

TRAIN_SPLIT = Path(
    "approved-data/sewer-ml/splits/train.csv"
)

VAL_SPLIT = Path(
    "approved-data/sewer-ml/splits/val.csv"
)

CHECKPOINT_DIR = Path(
    "artifacts/sewer_model_v3"
)


def read_split(path: Path) -> list[str]:
    with path.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return [
            row["Filename"]
            for row in csv.DictReader(handle)
        ]


def compute_pos_weight(
    filenames: list[str],
    csv_path: Path,
    device: torch.device,
    max_weight: float = 3.0,
) -> torch.Tensor:
    with csv_path.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        rows = {
            row["Filename"]: row
            for row in csv.DictReader(handle)
        }

    weights: list[float] = []

    for class_name in DEFECT_CLASSES:
        positives = sum(
            rows[filename][class_name] == "1"
            for filename in filenames
        )

        negatives = len(filenames) - positives

        if positives == 0:
            weight = 1.0
        else:
            raw_weight = negatives / positives
            weight = raw_weight ** 0.5

        weight = min(weight, max_weight)

        weights.append(weight)

    return torch.tensor(
        weights,
        dtype=torch.float32,
        device=device,
    )


def multilabel_metrics(
    targets: torch.Tensor,
    probabilities: torch.Tensor,
    threshold: float = 0.5,
) -> tuple[float, float]:
    predictions = (
        probabilities >= threshold
    ).int()

    macro_f1 = f1_score(
        targets.numpy(),
        predictions.numpy(),
        average="macro",
        zero_division=0,
    )

    macro_recall = recall_score(
        targets.numpy(),
        predictions.numpy(),
        average="macro",
        zero_division=0,
    )

    return macro_f1, macro_recall


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

    train_filenames = read_split(
        TRAIN_SPLIT
    )

    val_filenames = read_split(
        VAL_SPLIT
    )

    print(
        "Train manifest:",
        len(train_filenames),
    )

    print(
        "Validation manifest:",
        len(val_filenames),
    )

    train_dataset = SewerMLDataset(
        image_dir=IMAGE_DIR,
        csv_path=CSV_PATH,
        filenames=train_filenames,
        image_size=224,
        training=True,
    )

    val_dataset = SewerMLDataset(
        image_dir=IMAGE_DIR,
        csv_path=CSV_PATH,
        filenames=val_filenames,
        image_size=224,
        training=False,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=8,
        shuffle=True,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=8,
        shuffle=False,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )

    pos_weight = compute_pos_weight(
        train_filenames,
        CSV_PATH,
        device,
        max_weight=3.0,
    )

    print()
    print("Class weights:")

    for class_name, weight in zip(
        DEFECT_CLASSES,
        pos_weight.tolist(),
    ):
        print(
            f"  {class_name}: {weight:.3f}"
        )

    model = SewerDefectClassifier(
        pretrained=True,
    ).to(device)

    criterion = nn.BCEWithLogitsLoss(
        pos_weight=pos_weight
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=5e-5,
        weight_decay=1e-4,
    )

    scaler = GradScaler(
        device="cuda",
        enabled=device.type == "cuda",
    )

    CHECKPOINT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    epochs = 12
    patience = 3

    best_macro_f1 = -1.0
    best_val_loss = float("inf")
    epochs_without_improvement = 0

    history: list[dict[str, float]] = []

    for epoch in range(1, epochs + 1):
        model.train()

        total_train_loss = 0.0
        train_batches = 0

        for images, targets, _ in train_loader:
            images = images.to(
                device,
                non_blocking=True,
            )

            targets = targets.to(
                device,
                non_blocking=True,
            )

            optimizer.zero_grad(
                set_to_none=True
            )

            with autocast(
                device_type=device.type,
                enabled=device.type == "cuda",
            ):
                logits = model(images)

                loss = criterion(
                    logits,
                    targets,
                )

            scaler.scale(loss).backward()

            scaler.unscale_(optimizer)

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=1.0,
            )

            scaler.step(optimizer)
            scaler.update()

            total_train_loss += (
                loss.detach().item()
            )

            train_batches += 1

        train_loss = (
            total_train_loss
            / max(1, train_batches)
        )

        model.eval()

        total_val_loss = 0.0
        val_batches = 0

        all_targets: list[torch.Tensor] = []
        all_probabilities: list[torch.Tensor] = []

        with torch.no_grad():
            for images, targets, _ in val_loader:
                images = images.to(
                    device,
                    non_blocking=True,
                )

                targets_device = targets.to(
                    device,
                    non_blocking=True,
                )

                with autocast(
                    device_type=device.type,
                    enabled=device.type == "cuda",
                ):
                    logits = model(images)

                    loss = criterion(
                        logits,
                        targets_device,
                    )

                probabilities = torch.sigmoid(
                    logits
                )

                total_val_loss += (
                    loss.detach().item()
                )

                val_batches += 1

                all_targets.append(
                    targets.cpu()
                )

                all_probabilities.append(
                    probabilities.cpu()
                )

        val_loss = (
            total_val_loss
            / max(1, val_batches)
        )

        y_true = torch.cat(
            all_targets,
            dim=0,
        )

        y_prob = torch.cat(
            all_probabilities,
            dim=0,
        )

        macro_f1, macro_recall = (
            multilabel_metrics(
                y_true,
                y_prob,
                threshold=0.5,
            )
        )

        record = {
            "epoch": float(epoch),
            "train_loss": train_loss,
            "val_loss": val_loss,
            "macro_f1": macro_f1,
            "macro_recall": macro_recall,
        }

        history.append(record)

        print(
            f"Epoch {epoch}/{epochs} "
            f"train_loss={train_loss:.5f} "
            f"val_loss={val_loss:.5f} "
            f"macro_f1={macro_f1:.4f} "
            f"macro_recall={macro_recall:.4f}"
        )

        checkpoint = {
            "epoch": epoch,
            "model_state_dict": (
                model.state_dict()
            ),
            "optimizer_state_dict": (
                optimizer.state_dict()
            ),
            "val_loss": val_loss,
            "macro_f1": macro_f1,
            "macro_recall": macro_recall,
            "classes": DEFECT_CLASSES,
            "train_manifest": str(
                TRAIN_SPLIT
            ),
            "val_manifest": str(
                VAL_SPLIT
            ),
            "pos_weight": (
                pos_weight.detach().cpu()
            ),
        }

        torch.save(
            checkpoint,
            CHECKPOINT_DIR / "last.pt",
        )

        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            best_val_loss = val_loss
            epochs_without_improvement = 0

            torch.save(
                checkpoint,
                CHECKPOINT_DIR / "best.pt",
            )

            print(
                "  saved best macro-F1 checkpoint"
            )
        else:
            epochs_without_improvement += 1

        if epochs_without_improvement >= patience:
            print(
                f"Early stopping after "
                f"{epoch} epochs."
            )
            break

    (CHECKPOINT_DIR / "history.json").write_text(
        json.dumps(
            history,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("Training complete.")
    print(
        "Best macro F1:",
        best_macro_f1,
    )
    print(
        "Validation loss at best macro F1:",
        best_val_loss,
    )
    print(
        "Artifacts:",
        CHECKPOINT_DIR,
    )


if __name__ == "__main__":
    main()