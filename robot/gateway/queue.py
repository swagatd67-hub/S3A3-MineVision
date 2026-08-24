"""Bounded Frame Queue & Backpressure Buffer for Robot Gateway."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DropPolicy(str, Enum):
    """Backpressure overflow drop policy when frame buffer is full."""

    DROP_OLDEST = "DROP_OLDEST"
    DROP_NEWEST = "DROP_NEWEST"
    REJECT = "REJECT"


@dataclass
class QueueMetrics:
    """Diagnostic metrics snapshot for bounded queue monitoring."""

    max_size: int
    current_depth: int
    total_enqueued: int
    total_dequeued: int
    total_dropped: int
    drop_policy: str
    dropped_frames_log: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_size": self.max_size,
            "current_depth": self.current_depth,
            "total_enqueued": self.total_enqueued,
            "total_dequeued": self.total_dequeued,
            "total_dropped": self.total_dropped,
            "drop_policy": self.drop_policy,
            "dropped_frames_log": self.dropped_frames_log[-10:],
        }


class BoundedFrameQueue(Generic[T]):
    """Thread-safe bounded queue with explicit backpressure policies and dropped frame diagnostics."""

    def __init__(
        self,
        max_size: int = 50,
        policy: DropPolicy = DropPolicy.DROP_OLDEST,
    ) -> None:
        if max_size <= 0:
            raise ValueError("Queue max_size must be greater than zero.")
        self.max_size = max_size
        self.policy = policy
        self._queue: deque[T] = deque()
        self._lock = Lock()

        self._total_enqueued = 0
        self._total_dequeued = 0
        self._total_dropped = 0
        self._dropped_log: list[dict[str, Any]] = []

    @property
    def current_depth(self) -> int:
        with self._lock:
            return len(self._queue)

    def put(self, item: T, frame_index: int | None = None, frame_id: str | None = None) -> bool:
        """Enqueue item under defined drop policy. Returns True if accepted, False if dropped/rejected."""
        with self._lock:
            if len(self._queue) >= self.max_size:
                self._total_dropped += 1
                drop_info = {
                    "frame_index": frame_index,
                    "frame_id": frame_id,
                    "reason": "QUEUE_OVERFLOW",
                    "policy": self.policy.value,
                }
                self._dropped_log.append(drop_info)
                logger.warning("BoundedFrameQueue full (%d/%d). Drop policy %s triggered for frame %s", len(self._queue), self.max_size, self.policy.value, frame_index)

                if self.policy == DropPolicy.DROP_OLDEST:
                    dropped_item = self._queue.popleft()
                    dropped_idx = getattr(dropped_item, "frame_index", dropped_item if isinstance(dropped_item, int) else frame_index)
                    dropped_id = getattr(dropped_item, "frame_id", frame_id)
                    drop_info["dropped_item_index"] = dropped_idx
                    drop_info["dropped_item_id"] = dropped_id
                    self._queue.append(item)
                    self._total_enqueued += 1
                    return True
                elif self.policy == DropPolicy.DROP_NEWEST:
                    # Drop incoming item
                    return False
                elif self.policy == DropPolicy.REJECT:
                    raise OverflowError(f"Frame queue capacity ({self.max_size}) exceeded.")

            self._queue.append(item)
            self._total_enqueued += 1
            return True

    def get(self) -> T | None:
        """Dequeue next frame item, or return None if queue is empty."""
        with self._lock:
            if not self._queue:
                return None
            item = self._queue.popleft()
            self._total_dequeued += 1
            return item

    def clear(self) -> None:
        """Clear queue contents."""
        with self._lock:
            self._queue.clear()

    def get_metrics(self) -> QueueMetrics:
        """Return diagnostic metrics snapshot."""
        with self._lock:
            return QueueMetrics(
                max_size=self.max_size,
                current_depth=len(self._queue),
                total_enqueued=self._total_enqueued,
                total_dequeued=self._total_dequeued,
                total_dropped=self._total_dropped,
                drop_policy=self.policy.value,
                dropped_frames_log=list(self._dropped_log),
            )
