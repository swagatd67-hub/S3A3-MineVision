from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import torch

from backend.app.services.video.sewer_classifier import (
    DEFAULT_CHECKPOINT_PATH,
    DEFAULT_THRESHOLDS_PATH,
    ClassDecision,
    SewerMLInferenceEngine,
    SewerMLResult,
)
from backend.app.services.video.sewer_dataset import DEFECT_CLASSES
from backend.app.services.video.sewer_model import (
    SewerDefectClassifier,
    load_sewer_classifier,
)


@pytest.fixture
def dummy_checkpoint_and_thresholds(tmp_path: Path) -> tuple[Path, Path]:
    model = SewerDefectClassifier(num_classes=17, pretrained=False)
    checkpoint_path = tmp_path / "dummy_checkpoint.pt"
    thresholds_path = tmp_path / "dummy_thresholds.json"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "classes": DEFECT_CLASSES,
        },
        checkpoint_path,
    )

    thresholds_data = {cls_code: 0.4 for cls_code in DEFECT_CLASSES}
    thresholds_data["IS"] = 0.3
    thresholds_path.write_text(json.dumps(thresholds_data), encoding="utf-8")

    return checkpoint_path, thresholds_path


def test_synthetic_bgr_image_inference(
    dummy_checkpoint_and_thresholds: tuple[Path, Path],
) -> None:
    checkpoint_path, thresholds_path = dummy_checkpoint_and_thresholds
    engine = SewerMLInferenceEngine(
        checkpoint_path=checkpoint_path,
        thresholds_path=thresholds_path,
        device="cpu",
    )

    synthetic_image = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.predict(synthetic_image)

    assert isinstance(result, SewerMLResult)
    assert len(result.decisions) == 17
    assert result.inference_ms > 0
    assert result.model_version == "sewer-ml-e009"


def test_decision_data_structure_and_probability_range(
    dummy_checkpoint_and_thresholds: tuple[Path, Path],
) -> None:
    checkpoint_path, thresholds_path = dummy_checkpoint_and_thresholds
    engine = SewerMLInferenceEngine(
        checkpoint_path=checkpoint_path,
        thresholds_path=thresholds_path,
        device="cpu",
    )

    synthetic_image = np.full((224, 224, 3), fill_value=128, dtype=np.uint8)
    result = engine.predict(synthetic_image)

    class_codes = [d.class_code for d in result.decisions]
    assert class_codes == DEFECT_CLASSES

    for d in result.decisions:
        assert isinstance(d, ClassDecision)
        assert 0.0 <= d.probability <= 1.0
        assert 0.0 <= d.threshold <= 1.0
        assert d.detected == (d.probability >= d.threshold)

    result_dict = result.to_dict()
    assert "model_version" in result_dict
    assert "inference_ms" in result_dict
    assert "detected_classes" in result_dict
    assert "decisions" in result_dict
    assert len(result_dict["decisions"]) == 17


def test_detected_classes_consistency(
    dummy_checkpoint_and_thresholds: tuple[Path, Path],
) -> None:
    checkpoint_path, thresholds_path = dummy_checkpoint_and_thresholds
    engine = SewerMLInferenceEngine(
        checkpoint_path=checkpoint_path,
        thresholds_path=thresholds_path,
        device="cpu",
    )

    synthetic_image = np.random.randint(0, 256, (300, 300, 3), dtype=np.uint8)
    result = engine.predict(synthetic_image)

    expected_detected = [d.class_code for d in result.decisions if d.detected]
    assert result.detected_classes == expected_detected


def test_e009_model_and_thresholds_loading() -> None:
    if not DEFAULT_CHECKPOINT_PATH.exists() or not DEFAULT_THRESHOLDS_PATH.exists():
        pytest.skip("E009 checkpoint or thresholds file not present in local workspace")

    engine = SewerMLInferenceEngine(
        checkpoint_path=DEFAULT_CHECKPOINT_PATH,
        thresholds_path=DEFAULT_THRESHOLDS_PATH,
        device="cpu",
    )

    synthetic_image = np.zeros((480, 640, 3), dtype=np.uint8)
    result = engine.predict(synthetic_image)
    assert len(result.decisions) == 17


def test_cpu_safe_inference(
    dummy_checkpoint_and_thresholds: tuple[Path, Path],
) -> None:
    checkpoint_path, thresholds_path = dummy_checkpoint_and_thresholds
    engine = SewerMLInferenceEngine(
        checkpoint_path=checkpoint_path,
        thresholds_path=thresholds_path,
        device="cpu",
    )
    assert engine.device == torch.device("cpu")

    synthetic_image = np.zeros((100, 100, 3), dtype=np.uint8)
    result = engine.predict(synthetic_image)
    assert len(result.decisions) == 17


def test_invalid_image_inputs(
    dummy_checkpoint_and_thresholds: tuple[Path, Path],
) -> None:
    checkpoint_path, thresholds_path = dummy_checkpoint_and_thresholds
    engine = SewerMLInferenceEngine(
        checkpoint_path=checkpoint_path,
        thresholds_path=thresholds_path,
        device="cpu",
    )

    with pytest.raises(ValueError, match="non-empty numpy array"):
        engine.predict(np.array([]))

    with pytest.raises(ValueError, match="3-channel BGR image"):
        engine.predict(np.zeros((100, 100), dtype=np.uint8))


def test_missing_checkpoint_handling(tmp_path: Path) -> None:
    missing_path = tmp_path / "non_existent.pt"
    with pytest.raises(FileNotFoundError, match="Checkpoint file not found"):
        load_sewer_classifier(missing_path, device="cpu")


def test_malformed_checkpoint_handling(tmp_path: Path) -> None:
    invalid_pt = tmp_path / "invalid.pt"
    torch.save({"bad_key": 123}, invalid_pt)

    with pytest.raises(ValueError, match="missing 'model_state_dict'"):
        load_sewer_classifier(invalid_pt, device="cpu")


def test_mismatched_checkpoint_classes_handling(tmp_path: Path) -> None:
    model = SewerDefectClassifier(num_classes=17, pretrained=False)
    mismatched_pt = tmp_path / "mismatched.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "classes": ["CLASS_A", "CLASS_B"],
        },
        mismatched_pt,
    )

    with pytest.raises(ValueError, match="do not match expected DEFECT_CLASSES"):
        load_sewer_classifier(mismatched_pt, device="cpu")


def test_missing_and_malformed_thresholds_handling(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "dummy_checkpoint.pt"
    model = SewerDefectClassifier(num_classes=17, pretrained=False)
    torch.save({"model_state_dict": model.state_dict()}, checkpoint_path)

    missing_thresholds = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError, match="Thresholds file not found"):
        SewerMLInferenceEngine(
            checkpoint_path=checkpoint_path,
            thresholds_path=missing_thresholds,
            device="cpu",
        )

    malformed_json = tmp_path / "malformed.json"
    malformed_json.write_text("invalid json content", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to parse thresholds JSON"):
        SewerMLInferenceEngine(
            checkpoint_path=checkpoint_path,
            thresholds_path=malformed_json,
            device="cpu",
        )
