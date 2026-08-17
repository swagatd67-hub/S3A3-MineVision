from __future__ import annotations

import sys

import cv2

from backend.app.services.video.preprocessing import preprocess_frame, quality_summary


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: python -m scripts.preprocess_frame <input_image> <output_image>"
        )

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    image = cv2.imread(input_path)
    if image is None:
        raise RuntimeError(f"Unable to read image: {input_path}")

    result = preprocess_frame(image)

    if not cv2.imwrite(output_path, result.image):
        raise RuntimeError(f"Unable to write image: {output_path}")

    print(f"Saved: {output_path}")
    print(quality_summary(result))


if __name__ == "__main__":
    main()
