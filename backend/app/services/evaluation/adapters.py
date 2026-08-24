"""Dataset and Annotation Adapters for PipeVision Accuracy Evaluation.

Provides clean interfaces for parsing repository dataset annotations (such as Sewer-ML CSV splits)
and generic ground-truth records into PipeVision typed ground-truth contracts.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from backend.app.services.evaluation.models import (
    GroundTruthDefect,
    GroundTruthFrame,
    GroundTruthMission,
)
from backend.app.services.video.sewer_dataset import DEFECT_CLASSES


class SewerMLAnnotationAdapter:
    """Adapter for parsing Sewer-ML multi-label CSV split annotations into GroundTruthFrame domain models."""

    def __init__(self, csv_path: str | Path) -> None:
        self.csv_path = Path(csv_path)
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Sewer-ML annotation file not found: {self.csv_path}")

    def load_frames(self, limit: int | None = None) -> list[GroundTruthFrame]:
        """Load ground-truth frames from Sewer-ML CSV split file."""
        frames: list[GroundTruthFrame] = []

        with self.csv_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for idx, row in enumerate(reader):
                if limit is not None and idx >= limit:
                    break

                filename = row.get("Filename", f"frame_{idx:06d}.png")
                frame_id = Path(filename).stem

                presence: dict[str, bool] = {}
                defects: list[GroundTruthDefect] = []

                for cls in DEFECT_CLASSES:
                    val = row.get(cls, "0")
                    is_present = val.strip() == "1"
                    presence[cls] = is_present
                    if is_present:
                        defects.append(
                            GroundTruthDefect(
                                class_code=cls,
                                box=None,  # Bounding boxes not provided in standard Sewer-ML CSV
                                confidence_independent=True,
                            )
                        )

                frames.append(
                    GroundTruthFrame(
                        frame_id=frame_id,
                        filename=filename,
                        frame_index=idx,
                        defects=defects,
                        presence=presence,
                        source=f"Sewer-ML ({self.csv_path.name})",
                    )
                )

        return frames

    def load_mission(self, mission_id: str = "SEWER-ML-VAL", limit: int | None = None) -> GroundTruthMission:
        """Load an entire evaluation sequence as a GroundTruthMission."""
        frames = self.load_frames(limit=limit)
        return GroundTruthMission(
            mission_id=mission_id,
            frames=frames,
            source=f"Sewer-ML ({self.csv_path.name})",
        )


class GenericAnnotationAdapter:
    """Adapter for parsing generic dictionary or JSON ground-truth definitions."""

    @staticmethod
    def from_dict(data: dict[str, Any]) -> GroundTruthFrame:
        """Convert standard dict into GroundTruthFrame."""
        defects_raw = data.get("defects", [])
        defects: list[GroundTruthDefect] = []
        for d in defects_raw:
            if isinstance(d, dict):
                defects.append(
                    GroundTruthDefect(
                        class_code=d["class_code"],
                        confidence_independent=d.get("confidence_independent", True),
                        severity=d.get("severity"),
                    )
                )
            elif isinstance(d, str):
                defects.append(GroundTruthDefect(class_code=d))

        presence = data.get("presence", {})
        if not presence and defects:
            for def_item in defects:
                presence[def_item.class_code] = True

        return GroundTruthFrame(
            frame_id=data["frame_id"],
            filename=data.get("filename"),
            frame_index=data.get("frame_index"),
            defects=defects,
            presence=presence,
            true_distance_m=data.get("true_distance_m"),
            true_timestamp=data.get("true_timestamp"),
            true_pipe_diameter_mm=data.get("true_pipe_diameter_mm"),
            true_deformation_percent=data.get("true_deformation_percent"),
            source=data.get("source", "generic_dictionary"),
        )
