from __future__ import annotations

import csv
import glob
from pathlib import Path

from backend.app.services.video.sewer_dataset import DEFECT_CLASSES


IMAGE_DIR = Path(
    "approved-data/sewer-ml/images/train00_subset"
)

CSV_PATH = Path(
    "approved-data/sewer-ml/extracted/SewerML_Train.csv"
)

OUTPUT_DIR = Path(
    "approved-data/sewer-ml/splits"
)

TRAIN_OUTPUT = OUTPUT_DIR / "train.csv"
VAL_OUTPUT = OUTPUT_DIR / "val.csv"

VAL_FRACTION = 0.20


def load_metadata() -> dict[str, dict[str, str]]:
    with CSV_PATH.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        return {
            row["Filename"]: row
            for row in csv.DictReader(handle)
        }


def get_available_filenames() -> list[str]:
    return sorted(
        Path(path).name
        for path in glob.glob(
            str(IMAGE_DIR / "*.png")
        )
    )


def label_vector(
    row: dict[str, str],
) -> list[int]:
    return [
        int(row[class_name])
        for class_name in DEFECT_CLASSES
    ]


def count_labels(
    filenames: list[str],
    metadata: dict[str, dict[str, str]],
) -> list[int]:
    counts = [0] * len(DEFECT_CLASSES)

    for filename in filenames:
        values = label_vector(metadata[filename])

        for index, value in enumerate(values):
            counts[index] += value

    return counts


def select_validation(
    filenames: list[str],
    metadata: dict[str, dict[str, str]],
    val_size: int,
) -> list[str]:
    total_counts = count_labels(
        filenames,
        metadata,
    )

    # Target positive counts in validation.
    # Classes with at least 2 examples get at least
    # one validation example.
    targets = []

    for count in total_counts:
        if count < 2:
            targets.append(0)
        else:
            targets.append(
                max(
                    1,
                    round(
                        count * VAL_FRACTION
                    ),
                )
            )

    remaining = set(filenames)
    selected: list[str] = []
    current = [0] * len(DEFECT_CLASSES)

    while remaining and len(selected) < val_size:
        best_filename = None
        best_gain = float("-inf")

        for filename in remaining:
            values = label_vector(
                metadata[filename]
            )

            gain = 0.0

            for index, value in enumerate(values):
                if value == 0:
                    continue

                deficit = (
                    targets[index]
                    - current[index]
                )

                if deficit > 0:
                    # Rare classes get stronger priority.
                    total_count = total_counts[index]

                    rarity_weight = (
                        1.0
                        / max(
                            1,
                            total_count,
                        )
                    )

                    gain += (
                        deficit
                        * rarity_weight
                    )

            # Reward multi-label samples because one
            # validation image can cover several classes.
            label_count = sum(values)
            if label_count > 1:
                gain += 0.0005 * label_count

            if gain > best_gain:
                best_gain = gain
                best_filename = filename

        if best_filename is None:
            break

        selected.append(best_filename)
        remaining.remove(best_filename)

        values = label_vector(
            metadata[best_filename]
        )

        for index, value in enumerate(values):
            current[index] += value

    # If there are still open validation slots,
    # fill them deterministically.
    if len(selected) < val_size:
        for filename in sorted(remaining):
            selected.append(filename)

            if len(selected) >= val_size:
                break

    return selected


def write_manifest(
    path: Path,
    filenames: list[str],
    metadata: dict[str, dict[str, str]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        fieldnames = [
            "Filename",
            *DEFECT_CLASSES,
        ]

        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for filename in filenames:
            row = metadata[filename]

            writer.writerow(
                {
                    "Filename": filename,
                    **{
                        class_name: row[class_name]
                        for class_name in DEFECT_CLASSES
                    },
                }
            )


def print_counts(
    title: str,
    filenames: list[str],
    metadata: dict[str, dict[str, str]],
) -> None:
    counts = count_labels(
        filenames,
        metadata,
    )

    print()
    print(title)

    for class_name, count in zip(
        DEFECT_CLASSES,
        counts,
    ):
        print(
            f"  {class_name}: {count}"
        )


def main() -> None:
    metadata = load_metadata()

    filenames = [
        filename
        for filename in get_available_filenames()
        if filename in metadata
    ]

    if len(filenames) < 10:
        raise RuntimeError(
            "Too few images available for a development split."
        )

    val_size = max(
        1,
        round(
            len(filenames) * VAL_FRACTION
        ),
    )

    train_size = (
        len(filenames) - val_size
    )

    validation = select_validation(
        filenames,
        metadata,
        val_size,
    )

    validation_set = set(validation)

    train = [
        filename
        for filename in filenames
        if filename not in validation_set
    ]

    write_manifest(
        TRAIN_OUTPUT,
        train,
        metadata,
    )

    write_manifest(
        VAL_OUTPUT,
        validation,
        metadata,
    )

    print(
        "Total images:",
        len(filenames),
    )

    print(
        "Train:",
        len(train),
    )

    print(
        "Validation:",
        len(validation),
    )

    print_counts(
        "TRAIN LABEL COUNTS",
        train,
        metadata,
    )

    print_counts(
        "VALIDATION LABEL COUNTS",
        validation,
        metadata,
    )

    missing_in_validation = []

    total_counts = count_labels(
        filenames,
        metadata,
    )

    val_counts = count_labels(
        validation,
        metadata,
    )

    for index, class_name in enumerate(
        DEFECT_CLASSES
    ):
        if (
            total_counts[index] >= 2
            and val_counts[index] == 0
        ):
            missing_in_validation.append(
                class_name
            )

    print()

    if missing_in_validation:
        print(
            "WARNING: classes with available "
            "positives but zero validation support:"
        )
        print(
            ", ".join(
                missing_in_validation
            )
        )
    else:
        print(
            "All classes with at least "
            "2 total positives have validation support."
        )

    print()
    print(
        "Train manifest:",
        TRAIN_OUTPUT,
    )

    print(
        "Validation manifest:",
        VAL_OUTPUT,
    )


if __name__ == "__main__":
    main()