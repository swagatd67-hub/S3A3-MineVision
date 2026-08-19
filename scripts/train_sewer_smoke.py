from __future__ import annotations

import glob
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, random_split

from backend.app.services.video.sewer_dataset import (
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

    filenames = [
        Path(path).name
        for path in glob.glob(
            str(IMAGE_DIR / "*.png")
        )
    ]

    print("Images:", len(filenames))

    dataset = SewerMLDataset(
        image_dir=IMAGE_DIR,
        csv_path=CSV_PATH,
        filenames=filenames,
        image_size=224,
        training=True,
    )

    train_size = max(
        1,
        int(len(dataset) * 0.8),
    )

    val_size = len(dataset) - train_size

    train_dataset, val_dataset = random_split(
        dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )

    print("Train:", len(train_dataset))
    print("Validation:", len(val_dataset))

    train_loader = DataLoader(
        train_dataset,
        batch_size=8,
        shuffle=True,
        num_workers=0,
        pin_memory=device.type == "cuda",
    )

    model = SewerDefectClassifier(
        pretrained=True,
    ).to(device)

    criterion = nn.BCEWithLogitsLoss()

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=1e-4,
        weight_decay=1e-4,
    )

    model.train()

    images, targets, names = next(
        iter(train_loader)
    )

    images = images.to(
        device,
        non_blocking=True,
    )

    targets = targets.to(
        device,
        non_blocking=True,
    )

    optimizer.zero_grad(
        set_to_none=True,
    )

    logits = model(images)

    loss = criterion(
        logits,
        targets,
    )

    loss.backward()
    optimizer.step()

    if device.type == "cuda":
        torch.cuda.synchronize()

    probabilities = torch.sigmoid(
        logits.detach()
    )

    print(
        "Batch:",
        tuple(images.shape),
    )

    print(
        "Targets:",
        tuple(targets.shape),
    )

    print(
        "Logits:",
        tuple(logits.shape),
    )

    print(
        "Probabilities:",
        tuple(probabilities.shape),
    )

    print(
        "Loss:",
        float(loss.detach().cpu()),
    )

    print(
        "GPU training smoke test: PASS"
    )

    # Keep the variable referenced so the split itself is verified.
    del val_dataset


if __name__ == "__main__":
    main()