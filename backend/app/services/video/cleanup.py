"""Production media cleanup utility for temporary file and artifact retention."""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_expired_temporary_files(
    directory: str | Path,
    max_age_seconds: float = 86400.0,  # 24 hours default
    dry_run: bool = False,
) -> list[str]:
    """Scan temporary directory and remove expired files older than max_age_seconds."""
    dir_path = Path(directory).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        return []

    now = time.time()
    removed_files: list[str] = []

    for item in dir_path.glob("**/*"):
        if item.is_file():
            try:
                mtime = item.stat().st_mtime
                if (now - mtime) > max_age_seconds:
                    path_str = str(item)
                    if not dry_run:
                        item.unlink()
                        logger.info("Removed expired temporary file: %s", path_str)
                    removed_files.append(path_str)
            except OSError as exc:
                logger.warning("Failed to check/remove temporary file %s: %s", item, exc)

    return removed_files
