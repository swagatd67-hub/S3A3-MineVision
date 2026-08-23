from __future__ import annotations

import csv
from pathlib import Path

import torch
from PIL import Image
from torch import Tensor
from torch.utils.data import Dataset
from torchvision import transforms

DEFECT_CLASSES = [
    "RB",
    "OB",
    "PF",
    "DE",
    "FS",
    "IS",
    "RO",
    "IN",
    "AF",
    "BE",
    "FO",
    "GR",
    "PH",
    "PB",
    "OS",
    "OP",
    "OK",
]


class SewerMLDataset(Dataset[tuple[Tensor, Tensor, str]]):
    """Sewer-ML multi-label dataset for PipeVision."""

    def __init__(
        self,
        image_dir: str | Path,
        csv_path: str | Path,
        filenames: list[str],
        image_size: int = 224,
        training: bool = True,
        transform: transforms.Compose | None = None,
    ) -> None:
        self.image_dir = Path(image_dir)
        self.csv_path = Path(csv_path)

        with self.csv_path.open(
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            rows = {row["Filename"]: row for row in csv.DictReader(handle)}

        self.records: list[dict[str, str]] = []

        for filename in filenames:
            row = rows.get(filename)
            image_path = self.image_dir / filename

            if row is not None and image_path.is_file():
                self.records.append(row)

        if not self.records:
            raise ValueError("No valid Sewer-ML image records were found.")

        if transform is not None:
            self.transform = transform
        else:
            transform_ops: list[object] = [
                transforms.Resize((image_size, image_size)),
            ]

            if training:
                transform_ops.extend(
                    [
                        transforms.RandomHorizontalFlip(
                            p=0.5,
                        ),
                        transforms.RandomRotation(
                            degrees=5,
                        ),
                    ]
                )

            transform_ops.extend(
                [
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=(0.485, 0.456, 0.406),
                        std=(0.229, 0.224, 0.225),
                    ),
                ]
            )

            self.transform = transforms.Compose(transform_ops)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(
        self,
        index: int,
    ) -> tuple[Tensor, Tensor, str]:
        row = self.records[index]
        filename = row["Filename"]

        image_path = self.image_dir / filename

        try:
            with Image.open(image_path) as raw_image:
                rgb_image = raw_image.convert("RGB")
                image_tensor = self.transform(rgb_image)
        except Exception as exc:
            raise RuntimeError(f"Failed to load image: {image_path}") from exc

        target = torch.tensor(
            [float(row[class_name]) for class_name in DEFECT_CLASSES],
            dtype=torch.float32,
        )

        return image_tensor, target, filename
