from __future__ import annotations

import csv
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
from torch import nn
from contextlib import nullcontext
from typing import Any, cast
from torch.amp.grad_scaler import GradScaler
from torch.utils.data import DataLoader
from torchvision import transforms

from sklearn.metrics import f1_score, recall_score

from backend.app.services.video.sewer_dataset import (
    DEFECT_CLASSES,
    SewerMLDataset,
)
from backend.app.services.video.sewer_model import (
    SewerDefectClassifier,
)
from scripts.evaluate_sewer_experiment import save_experiment_evaluation
from scripts.summarize_sewer_experiments import build_summary
from scripts.verify_sewer_integrity import verify_integrity


IMAGE_DIR = Path("approved-data/sewer-ml/images/train00_subset")
CSV_PATH = Path("approved-data/sewer-ml/extracted/SewerML_Train.csv")
TRAIN_SPLIT = Path("approved-data/sewer-ml/splits/train.csv")
VAL_SPLIT = Path("approved-data/sewer-ml/splits/val.csv")
EXPERIMENTS_BASE_DIR = Path("experiments/sewer")


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def read_split(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row["Filename"] for row in csv.DictReader(handle)]


def compute_pos_weight(
    filenames: list[str],
    csv_path: Path,
    mode: str = "none",
    cap: float | None = None,
    device: torch.device = torch.device("cpu"),
) -> tuple[torch.Tensor, dict[str, float]]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = {row["Filename"]: row for row in csv.DictReader(handle)}

    weights: list[float] = []
    weight_dict: dict[str, float] = {}

    total_samples = len(filenames)

    for class_name in DEFECT_CLASSES:
        positives = sum(1 for fn in filenames if rows[fn][class_name] == "1")
        negatives = total_samples - positives

        if mode == "none" or positives == 0:
            weight = 1.0
        elif mode in ("full", "capped_full"):
            weight = negatives / positives
        elif mode in ("sqrt", "capped_sqrt"):
            weight = (negatives / positives) ** 0.5
        else:
            weight = 1.0

        if cap is not None:
            weight = min(weight, cap)

        weights.append(weight)
        weight_dict[class_name] = round(weight, 4)

    tensor_weights = torch.tensor(weights, dtype=torch.float32, device=device)
    return tensor_weights, weight_dict


def get_transforms(aug_setting: str, image_size: int = 224) -> tuple[transforms.Compose, transforms.Compose]:
    if aug_setting == "stronger":
        train_transform = transforms.Compose([
            transforms.RandomResizedCrop(image_size, scale=(0.85, 1.0)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=10),
            transforms.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ])
    else:  # "baseline" or standard
        train_transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=5),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ])

    val_transform = transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])

    return train_transform, val_transform


def run_experiment(config: dict[str, Any], force_rerun: bool = False) -> dict[str, Any]:
    exp_id = config["experiment_id"]
    exp_dir = EXPERIMENTS_BASE_DIR / exp_id

    if not force_rerun and exp_dir.exists() and (exp_dir / "metrics.json").exists():
        print(f"\n[SKIP] Experiment {exp_id} already completed at {exp_dir}")
        try:
            return json.loads((exp_dir / "metrics.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    exp_dir.mkdir(parents=True, exist_ok=True)
    log_file = exp_dir / "training.log"

    def log(msg: str) -> None:
        print(msg)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")

    log(f"\n========================================")
    log(f"STARTING EXPERIMENT: {exp_id}")
    log(f"========================================")

    seed = config.get("random_seed", 42)
    set_seed(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    amp_enabled = device.type == "cuda"
    log(f"Device: {device}")
    if device.type == "cuda":
        log(f"GPU: {torch.cuda.get_device_name(0)}")

    train_filenames = read_split(TRAIN_SPLIT)
    val_filenames = read_split(VAL_SPLIT)

    log(f"Train samples: {len(train_filenames)}, Val samples: {len(val_filenames)}")

    # Calculate class weights
    pos_weight_tensor, weight_dict = compute_pos_weight(
        train_filenames,
        CSV_PATH,
        mode=config.get("class_weight_mode", "none"),
        cap=config.get("class_weight_cap", None),
        device=device,
    )

    log(f"Class Weight Mode: {config.get('class_weight_mode')}, Cap: {config.get('class_weight_cap')}")
    log(f"Class Weights: {weight_dict}")

    # Build transforms
    train_transform, val_transform = get_transforms(
        config.get("augmentation_setting", "baseline"),
        image_size=config.get("image_size", 224),
    )

    train_dataset = SewerMLDataset(
        image_dir=IMAGE_DIR,
        csv_path=CSV_PATH,
        filenames=train_filenames,
        image_size=config.get("image_size", 224),
        training=True,
        transform=train_transform,
    )

    val_dataset = SewerMLDataset(
        image_dir=IMAGE_DIR,
        csv_path=CSV_PATH,
        filenames=val_filenames,
        image_size=config.get("image_size", 224),
        training=False,
        transform=val_transform,
    )

    # Initial batch size with fallback retry logic
    desired_batch_size = config.get("batch_size", 8)
    batch_size_candidates = [desired_batch_size]
    if desired_batch_size > 4:
        batch_size_candidates.append(4)
    if desired_batch_size > 2:
        batch_size_candidates.append(2)

    success = False
    actual_batch_size = desired_batch_size
    history: list[dict[str, Any]] = []

    # Sentinel values — overwritten inside the loop; placed here so the
    # type-checker sees them as always initialised.
    best_val_targets: np.ndarray | None = None
    best_val_probs: np.ndarray | None = None
    best_epoch: int = 0
    best_macro_f1: float = -1.0
    best_val_loss: float = float("inf")

    start_time = time.time()

    for batch_size in batch_size_candidates:
        actual_batch_size = batch_size
        config["actual_batch_size"] = actual_batch_size
        if batch_size != desired_batch_size:
            log(f"[CUDA OOM RECOVERY] Retrying experiment with batch size: {batch_size}")

        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0,
            pin_memory=device.type == "cuda",
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=device.type == "cuda",
        )

        model = SewerDefectClassifier(
            num_classes=len(DEFECT_CLASSES),
            pretrained=config.get("pretrained", True),
        ).to(device)

        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)

        base_lr = float(config.get("learning_rate", 1e-4))
        weight_decay = float(config.get("weight_decay", 1e-4))
        epochs = config.get("epochs", 12)
        patience = config.get("patience", 3)
        freeze_epochs = config.get("freeze_backbone_epochs", 0)

        # Handle E006 backbone freezing initially
        if freeze_epochs > 0:
            log(f"Freezing ResNet backbone feature extractor for initial {freeze_epochs} epochs.")
            for param in model.backbone.parameters():
                param.requires_grad = False
            for param in model.backbone.fc.parameters():
                param.requires_grad = True

        optimizer = torch.optim.AdamW(
            filter(lambda p: p.requires_grad, model.parameters()),
            lr=base_lr,
            weight_decay=weight_decay,
        )

        amp_enabled = device.type == "cuda"
        scaler = GradScaler(device="cuda", enabled=amp_enabled)

        best_macro_f1 = -1.0
        best_val_loss = float("inf")
        best_epoch = 0
        epochs_without_improvement = 0
        history = []

        best_val_targets: np.ndarray | None = None
        best_val_probs: np.ndarray | None = None

        oom_occurred = False

        try:
            for epoch in range(1, epochs + 1):
                # E006 backbone unfreeze logic
                if freeze_epochs > 0 and epoch == freeze_epochs + 1:
                    log(f"Unfreezing ResNet backbone at epoch {epoch}.")
                    for param in model.backbone.parameters():
                        param.requires_grad = True

                    unfreeze_lr = float(config.get("unfreeze_lr", base_lr * 0.2))
                    optimizer = torch.optim.AdamW(
                        model.parameters(),
                        lr=unfreeze_lr,
                        weight_decay=weight_decay,
                    )
                    log(f"Updated optimizer LR to {unfreeze_lr}")
                    epochs_without_improvement = 0

                model.train()
                total_train_loss = 0.0
                train_batches = 0

                for images, targets, _ in train_loader:
                    images = images.to(device, non_blocking=True)
                    targets = targets.to(device, non_blocking=True)

                    optimizer.zero_grad(set_to_none=True)

                    if amp_enabled:
                        amp_context = cast(
                            Any,
                            torch.autocast(
                                device_type="cuda",
                                enabled=True,
                            ),
                        )
                    else:
                        amp_context = nullcontext()

                    with amp_context:
                        logits = model(images)
                        loss = criterion(logits, targets)

                    scaled_loss = scaler.scale(loss)
                    cast(Any, scaled_loss).backward()
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    scaler.step(optimizer)
                    scaler.update()

                    total_train_loss += loss.detach().item()
                    train_batches += 1

                train_loss = total_train_loss / max(1, train_batches)

                # Validation pass
                model.eval()
                total_val_loss = 0.0
                val_batches = 0
                all_targets: list[torch.Tensor] = []
                all_probs: list[torch.Tensor] = []

                with torch.no_grad():
                    for images, targets, _ in val_loader:
                        images = images.to(device, non_blocking=True)
                        targets_device = targets.to(device, non_blocking=True)

                        if amp_enabled:
                            amp_context = cast(
                                Any,
                                torch.autocast(
                                    device_type="cuda",
                                    enabled=True,
                                ),
                            )
                        else:
                            amp_context = nullcontext()

                        with amp_context:
                            logits = model(images)
                            loss = criterion(logits, targets_device)
                        probabilities = torch.sigmoid(logits)

                        total_val_loss += loss.detach().item()
                        val_batches += 1

                        all_targets.append(targets.cpu())
                        all_probs.append(probabilities.cpu())

                val_loss = total_val_loss / max(1, val_batches)
                y_true = torch.cat(all_targets, dim=0).numpy()
                y_prob = torch.cat(all_probs, dim=0).numpy()

                y_pred = (y_prob >= 0.5).astype(int)
                macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
                macro_recall = float(recall_score(y_true, y_pred, average="macro", zero_division=0))

                record = {
                    "epoch": epoch,
                    "train_loss": train_loss,
                    "val_loss": val_loss,
                    "macro_f1": macro_f1,
                    "macro_recall": macro_recall,
                }
                history.append(record)

                log(
                    f"Epoch {epoch:2d}/{epochs:2d} | "
                    f"train_loss={train_loss:.5f} | "
                    f"val_loss={val_loss:.5f} | "
                    f"macro_f1={macro_f1:.4f} | "
                    f"macro_recall={macro_recall:.4f}"
                )

                checkpoint_data = {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_loss": val_loss,
                    "macro_f1": macro_f1,
                    "macro_recall": macro_recall,
                    "classes": DEFECT_CLASSES,
                    "config": config,
                }

                torch.save(checkpoint_data, exp_dir / "last.pt")

                if macro_f1 > best_macro_f1:
                    best_macro_f1 = macro_f1
                    best_val_loss = val_loss
                    best_epoch = epoch
                    epochs_without_improvement = 0
                    best_val_targets = y_true
                    best_val_probs = y_prob

                    torch.save(checkpoint_data, exp_dir / "best.pt")
                    log("  --> Saved new best checkpoint (Macro F1)")
                else:
                    epochs_without_improvement += 1

                if epochs_without_improvement >= patience:
                    log(f"Early stopping triggered after {epoch} epochs.")
                    break

            success = True
            break

        except RuntimeError as e:
            message = str(e).lower()
            if "out of memory" in message:
                log(f"[CUDA OOM DETECTED] {e}")
                del model, optimizer, scaler
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                oom_occurred = True
            else:
                log(f"[ERROR] Experiment failed with exception: {e}")
                config["status"] = "FAILED"
                config["error"] = str(e)
                (exp_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
                return {"status": "FAILED", "error": str(e)}

    training_time = round(time.time() - start_time, 2)

    if not success or best_val_targets is None or best_val_probs is None:
        log("[FAILED] All batch size attempts failed due to OOM or errors.")
        config["status"] = "FAILED"
        config["error"] = "All batch size attempts failed"
        (exp_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        return {"status": "FAILED", "error": "OOM"}

    # Narrow types: these are guaranteed set when success is True and
    # best_val_targets/best_val_probs are not None (checked above).
    assert best_val_targets is not None
    assert best_val_probs is not None
    assert best_epoch >= 1
    assert best_macro_f1 >= 0.0
    assert best_val_loss < float("inf")

    config["status"] = "COMPLETED"
    config["best_epoch"] = best_epoch
    config["best_macro_f1_global"] = best_macro_f1
    config["best_val_loss"] = best_val_loss
    config["training_time_seconds"] = training_time
    config["gpu_name"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    config["cuda_available"] = torch.cuda.is_available()

    (exp_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (exp_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")

    # Evaluate best validation predictions & save metrics
    metrics = save_experiment_evaluation(
        exp_dir,
        best_val_targets,
        best_val_probs,
        filenames=val_filenames,
        val_loss=best_val_loss,
    )

    log(f"Experiment {exp_id} complete in {training_time}s.")
    log(f"Global Macro F1: {metrics['global_threshold_0.5']['macro_f1']:.4f}")
    log(f"Tuned  Macro F1: {metrics['validation_derived_tuned_thresholds']['macro_f1']:.4f}")

    return metrics


def run_experiment_suite() -> None:
    # 1. Verify Dataset & Manifest Integrity before starting any experiment
    print("\n========================================")
    print("STEP 1: VERIFYING DATASET INTEGRITY")
    print("========================================")
    verify_integrity()

    EXPERIMENTS_BASE_DIR.mkdir(parents=True, exist_ok=True)

    completed_experiments: dict[str, dict[str, Any]] = {}

    # Define base experiments E001 - E004
    base_experiments: list[dict[str, Any]] = [
        {
            "experiment_id": "E001",
            "name": "E001 — CLEAN BASELINE",
            "backbone": "ResNet18",
            "pretrained": True,
            "class_weight_mode": "none",
            "class_weight_cap": None,
            "learning_rate": 1e-4,
            "weight_decay": 1e-4,
            "batch_size": 8,
            "image_size": 224,
            "augmentation_setting": "baseline",
            "epochs": 15,
            "patience": 3,
            "random_seed": 42,
            "threshold_mode": "global_0.5",
        },
        {
            "experiment_id": "E002",
            "name": "E002 — MILD CLASS WEIGHTING",
            "backbone": "ResNet18",
            "pretrained": True,
            "class_weight_mode": "capped_sqrt",
            "class_weight_cap": 3.0,
            "learning_rate": 5e-5,
            "weight_decay": 1e-4,
            "batch_size": 8,
            "image_size": 224,
            "augmentation_setting": "baseline",
            "epochs": 15,
            "patience": 3,
            "random_seed": 42,
            "threshold_mode": "global_0.5",
        },
        {
            "experiment_id": "E003",
            "name": "E003 — LOWER LR, NO WEIGHTING",
            "backbone": "ResNet18",
            "pretrained": True,
            "class_weight_mode": "none",
            "class_weight_cap": None,
            "learning_rate": 5e-5,
            "weight_decay": 1e-4,
            "batch_size": 8,
            "image_size": 224,
            "augmentation_setting": "baseline",
            "epochs": 15,
            "patience": 3,
            "random_seed": 42,
            "threshold_mode": "global_0.5",
        },
        {
            "experiment_id": "E004",
            "name": "E004 — VERY MILD WEIGHTING",
            "backbone": "ResNet18",
            "pretrained": True,
            "class_weight_mode": "capped_sqrt",
            "class_weight_cap": 2.0,
            "learning_rate": 5e-5,
            "weight_decay": 1e-4,
            "batch_size": 8,
            "image_size": 224,
            "augmentation_setting": "baseline",
            "epochs": 15,
            "patience": 3,
            "random_seed": 42,
            "threshold_mode": "global_0.5",
        },
    ]

    for exp_cfg in base_experiments:
        res = run_experiment(exp_cfg)
        exp_id = str(exp_cfg["experiment_id"])
        completed_experiments[exp_id] = res

    # Determine best configuration from E001–E004 based on global Macro F1
    best_base_id = "E001"
    best_base_f1 = -1.0
    for exp_id in ["E001", "E002", "E003", "E004"]:
        m = completed_experiments.get(exp_id, {})
        gl_f1 = m.get("global_threshold_0.5", {}).get("macro_f1", -1.0)
        if gl_f1 > best_base_f1:
            best_base_f1 = gl_f1
            best_base_id = exp_id

    print(f"\n>>> Best base configuration among E001-E004 is {best_base_id} (Global Macro F1: {best_base_f1:.4f})")

    # Retrieve full config of best base experiment
    best_base_config = json.loads((EXPERIMENTS_BASE_DIR / best_base_id / "config.json").read_text(encoding="utf-8"))

    # E005 — BEST BASE CONFIG + TUNED THRESHOLDS
    e005_config = dict(best_base_config)
    e005_config["experiment_id"] = "E005"
    e005_config["name"] = f"E005 — BEST BASE CONFIG ({best_base_id}) + TUNED THRESHOLDS"
    e005_config["threshold_mode"] = "validation_derived_tuned"
    completed_experiments["E005"] = run_experiment(e005_config)

    # E006 — BEST CONFIG + BACKBONE FREEZE
    e006_config = dict(best_base_config)
    e006_config["experiment_id"] = "E006"
    e006_config["name"] = f"E006 — BEST CONFIG ({best_base_id}) + BACKBONE FREEZE"
    e006_config["freeze_backbone_epochs"] = 3
    e006_config["unfreeze_lr"] = e006_config.get("learning_rate", 1e-4) * 0.2
    completed_experiments["E006"] = run_experiment(e006_config)

    # E007 — BEST CONFIG + STRONGER REASONABLE AUGMENTATION
    e007_config = dict(best_base_config)
    e007_config["experiment_id"] = "E007"
    e007_config["name"] = f"E007 — BEST CONFIG ({best_base_id}) + STRONGER AUGMENTATION"
    e007_config["augmentation_setting"] = "stronger"
    completed_experiments["E007"] = run_experiment(e007_config)

    print("\n========================================")
    print("ALL EXPERIMENTS E001 - E007 EXECUTED")
    print("========================================")

    # Build summary and print final terminal report
    _, report = build_summary()
    print("\n" + report)


if __name__ == "__main__":
    run_experiment_suite()
