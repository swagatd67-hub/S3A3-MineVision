from __future__ import annotations

import sys

import cv2

from backend.app.services.video.source import VideoSource


def main() -> None:
    source_arg = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "video/samples/test_pipe.mp4"
    )

    source = VideoSource(source_arg)

    print(f"Source: {source.source}")
    print(f"Resolution: {source.width}x{source.height}")
    print(f"FPS: {source.fps:.2f}")

    frame_count = 0

    try:
        for packet in source.frames():
            cv2.imshow("PipeVision - Day 4", packet.frame)

            frame_count += 1

            print(
                f"frame={packet.frame_index} "
                f"timestamp={packet.timestamp_s:.3f}s"
            )

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

    finally:
        source.close()
        cv2.destroyAllWindows()

    print(f"Processed {frame_count} frames")


if __name__ == "__main__":
    main()