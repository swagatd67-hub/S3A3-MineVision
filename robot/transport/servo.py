"""Safe, dependency-light servo hardware abstraction for Raspberry Pi robots.

The GPIO library is intentionally imported only by :class:`GpioZeroServoDriver`.
Simulator and CI code can therefore use ``MemoryServoDriver`` (or a test double)
without installing Raspberry Pi packages.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Protocol


class ServoError(ValueError):
    """Base error for invalid or unsafe servo operations."""


class ServoLimitError(ServoError):
    """Raised when a requested angle is outside a configured servo limit."""


@dataclass(frozen=True)
class ServoConfig:
    """Configuration for one servo channel.

    ``gpio_pin`` is optional so a complete configuration can be used in a
    simulator. A live GPIO driver refuses configurations without a pin.
    """

    name: str
    gpio_pin: int | None = None
    neutral_deg: float | None = None
    min_deg: float | None = None
    max_deg: float | None = None
    command_scale: float | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ServoError("Servo name must not be empty.")
        if self.gpio_pin is not None and self.gpio_pin < 0:
            raise ServoError(f"GPIO pin for {self.name} must be non-negative.")
        calibration = (self.neutral_deg, self.min_deg, self.max_deg)
        if any(value is not None and not math.isfinite(value) for value in calibration):
            raise ServoError(f"Servo limits for {self.name} must be finite.")
        if self.command_scale is not None and (
            not math.isfinite(self.command_scale) or self.command_scale <= 0
        ):
            raise ServoError(f"Servo command_scale for {self.name} must be positive and finite.")
        if self.min_deg is not None and self.max_deg is not None and self.min_deg > self.max_deg:
            raise ServoError(f"Servo minimum exceeds maximum for {self.name}.")
        if (
            self.neutral_deg is not None
            and self.min_deg is not None
            and self.max_deg is not None
            and not self.min_deg <= self.neutral_deg <= self.max_deg
        ):
            raise ServoError(f"Servo neutral is outside limits for {self.name}.")


@dataclass(frozen=True)
class ServoRigConfig:
    """The six-servo layout used by Phase 20B."""

    channels: dict[str, ServoConfig] = field(default_factory=lambda: {
        **{f"locomotion_{index}": ServoConfig(f"locomotion_{index}") for index in range(1, 5)},
        "camera_pan": ServoConfig("camera_pan"),
        "camera_tilt": ServoConfig("camera_tilt"),
    })

    def __post_init__(self) -> None:
        required = {"locomotion_1", "locomotion_2", "locomotion_3", "locomotion_4", "camera_pan", "camera_tilt"}
        missing = required - self.channels.keys()
        if missing:
            raise ServoError(f"Missing servo channels: {sorted(missing)}")


def servo_rig_config_from_json(raw: str | None) -> ServoRigConfig:
    """Build a rig from JSON, retaining safe defaults for omitted fields."""
    if not raw:
        return ServoRigConfig()
    try:
        values = json.loads(raw)
        if not isinstance(values, dict):
            raise TypeError("top-level value must be an object")
        channels: dict[str, ServoConfig] = {}
        for name, defaults in ServoRigConfig().channels.items():
            override = values.get(name, {})
            if not isinstance(override, dict):
                raise TypeError(f"configuration for '{name}' must be an object")
            channels[name] = ServoConfig(
                name=name,
                gpio_pin=override.get("gpio_pin", defaults.gpio_pin),
                neutral_deg=_optional_float(override.get("neutral_deg", defaults.neutral_deg)),
                min_deg=_optional_float(override.get("min_deg", defaults.min_deg)),
                max_deg=_optional_float(override.get("max_deg", defaults.max_deg)),
                command_scale=_optional_float(override.get("command_scale", defaults.command_scale)),
            )
        return ServoRigConfig(channels=channels)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ServoError(f"Invalid ROBOT_SERVO_CONFIG_JSON: {exc}") from exc


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


class ServoDriver(Protocol):
    """Minimal interface used by the transport; straightforward to mock."""

    def set_angle(self, channel: str, angle_deg: float) -> None: ...
    def set_command_angle(self, channel: str, angle_deg: float) -> None: ...
    def neutral_all(self) -> None: ...
    def close(self) -> None: ...


class MemoryServoDriver:
    """Deterministic in-memory driver for simulator and CI tests."""

    def __init__(self, config: ServoRigConfig | None = None) -> None:
        self.config = config or ServoRigConfig()
        self.positions = {
            name: channel.neutral_deg
            for name, channel in self.config.channels.items()
            if channel.neutral_deg is not None
        }
        self.closed = False

    def set_angle(self, channel: str, angle_deg: float) -> None:
        if channel not in self.config.channels:
            raise ServoError(f"Unknown servo channel '{channel}'.")
        if not math.isfinite(angle_deg):
            raise ServoLimitError("Servo angle must be finite.")
        limits = self.config.channels[channel]
        if limits.min_deg is None or limits.max_deg is None:
            raise ServoError(f"Servo '{channel}' has no configured angle limits.")
        if not limits.min_deg <= angle_deg <= limits.max_deg:
            raise ServoLimitError(
                f"Servo '{channel}' angle {angle_deg} is outside configured limits "
                f"[{limits.min_deg}, {limits.max_deg}]."
            )
        self.positions[channel] = angle_deg

    def set_command_angle(self, channel: str, angle_deg: float) -> None:
        """Apply configured scaling around neutral before enforcing limits."""
        config = self.config.channels.get(channel)
        if config is None or config.neutral_deg is None:
            raise ServoError(f"Servo '{channel}' has no configured neutral position.")
        scale = config.command_scale
        scaled = angle_deg if scale is None else config.neutral_deg + (angle_deg - config.neutral_deg) * scale
        self.set_angle(channel, scaled)

    def neutral_all(self) -> None:
        for channel, config in self.config.channels.items():
            if config.neutral_deg is None:
                raise ServoError(f"Servo '{channel}' has no configured neutral position.")
            self.set_angle(channel, config.neutral_deg)

    def close(self) -> None:
        self.closed = True


class GpioZeroServoDriver(MemoryServoDriver):
    """gpiozero-backed driver, loaded only when explicitly constructed."""

    def __init__(self, config: ServoRigConfig) -> None:
        super().__init__(config)
        # Refuse to construct any GPIO object until every channel has a
        # complete, deployment-provided wiring and calibration definition.
        # This prevents a live pin from being activated with library defaults.
        for name, channel in config.channels.items():
            if channel.gpio_pin is None:
                raise ServoError(f"GPIO pin must be configured for live servo '{name}'.")
            if (
                channel.neutral_deg is None
                or channel.min_deg is None
                or channel.max_deg is None
            ):
                raise ServoError(
                    f"Live servo '{name}' requires configured neutral_deg, min_deg, and max_deg."
                )
        try:
            from gpiozero import AngularServo
        except ImportError as exc:  # pragma: no cover - Raspberry Pi only
            raise ServoError(
                "gpiozero is required only for live GPIO mode; use dry-run or a mock driver in CI."
            ) from exc

        self._servos = {}
        for name, channel in config.channels.items():
            self._servos[name] = AngularServo(
                channel.gpio_pin,
                min_angle=channel.min_deg,
                max_angle=channel.max_deg,
                initial_value=None,
            )

    def set_angle(self, channel: str, angle_deg: float) -> None:
        super().set_angle(channel, angle_deg)
        self._servos[channel].angle = angle_deg

    def close(self) -> None:
        for servo in self._servos.values():
            servo.detach()
        super().close()
