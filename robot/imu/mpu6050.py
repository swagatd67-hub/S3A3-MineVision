"""Hardware-abstracted MPU6050 reader.

The I2C dependency is imported only when ``MPU6050Reader`` is constructed.
``FakeIMUReader`` provides deterministic samples for simulator and CI use.
This module reports calibrated sensor axes only; it does not estimate
orientation because no calibration or sensor-fusion filter is implemented.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol


class IMUError(RuntimeError):
    """Base error raised by an IMU reader."""


@dataclass(frozen=True)
class MPU6050Config:
    """Deployment-provided MPU6050 bus configuration."""

    i2c_bus: int
    i2c_address: int
    accelerometer_scale_g: int = 2
    gyroscope_scale_dps: int = 250

    def __post_init__(self) -> None:
        if self.i2c_bus < 0:
            raise ValueError("i2c_bus must be non-negative.")
        if not 0x03 <= self.i2c_address <= 0x77:
            raise ValueError("i2c_address must be a valid 7-bit I2C address.")
        if self.accelerometer_scale_g not in (2, 4, 8, 16):
            raise ValueError("accelerometer_scale_g must be 2, 4, 8, or 16.")
        if self.gyroscope_scale_dps not in (250, 500, 1000, 2000):
            raise ValueError("gyroscope_scale_dps must be 250, 500, 1000, or 2000.")


@dataclass(frozen=True)
class RawIMUReading:
    """One raw physical sample, normalized to SI units but not filtered."""

    ax_mps2: float
    ay_mps2: float
    az_mps2: float
    gx_rads: float
    gy_rads: float
    gz_rads: float
    temperature_c: float | None = None

    def __post_init__(self) -> None:
        values = (self.ax_mps2, self.ay_mps2, self.az_mps2, self.gx_rads, self.gy_rads, self.gz_rads)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("IMU readings must be finite.")
        if self.temperature_c is not None and not math.isfinite(self.temperature_c):
            raise ValueError("IMU temperature must be finite when present.")

    def to_telemetry_dict(self) -> dict[str, float]:
        """Convert the raw sample to the existing telemetry field names."""
        data = {
            "ax": self.ax_mps2,
            "ay": self.ay_mps2,
            "az": self.az_mps2,
            "gx": self.gx_rads,
            "gy": self.gy_rads,
            "gz": self.gz_rads,
        }
        if self.temperature_c is not None:
            data["temperature_c"] = self.temperature_c
        return data


class IMUReader(Protocol):
    """Replaceable interface for physical and fake IMU implementations."""

    def read(self) -> RawIMUReading: ...
    def close(self) -> None: ...


class FakeIMUReader:
    """Deterministic fake reader that never accesses hardware."""

    def __init__(self, reading: RawIMUReading | None = None) -> None:
        self.reading = reading or RawIMUReading(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self.read_count = 0
        self.closed = False

    def read(self) -> RawIMUReading:
        if self.closed:
            raise IMUError("Cannot read a closed fake IMU.")
        self.read_count += 1
        return self.reading

    def close(self) -> None:
        self.closed = True


class MPU6050Reader:
    """Read MPU6050 registers through an injected or lazily-created I2C bus."""

    def __init__(self, config: MPU6050Config, bus: Any | None = None) -> None:
        self.config = config
        if bus is None:
            try:
                from smbus2 import SMBus
            except ImportError as exc:  # pragma: no cover - Raspberry Pi only
                raise IMUError(
                    "smbus2 is required only for live MPU6050 mode; use FakeIMUReader in CI."
                ) from exc
            bus = SMBus(config.i2c_bus)
        self._bus = bus
        self._closed = False
        self._write_register(0x6B, 0x00)  # wake from sleep

    def _write_register(self, register: int, value: int) -> None:
        self._bus.write_byte_data(self.config.i2c_address, register, value)

    def _read_word(self, register: int) -> int:
        high = self._bus.read_byte_data(self.config.i2c_address, register)
        low = self._bus.read_byte_data(self.config.i2c_address, register + 1)
        value = (high << 8) | low
        return value - 65536 if value & 0x8000 else value

    def read(self) -> RawIMUReading:
        if self._closed:
            raise IMUError("Cannot read a closed MPU6050.")
        accel_lsb_per_g = {2: 16384.0, 4: 8192.0, 8: 4096.0, 16: 2048.0}[self.config.accelerometer_scale_g]
        gyro_lsb_per_dps = {250: 131.0, 500: 65.5, 1000: 32.8, 2000: 16.4}[self.config.gyroscope_scale_dps]
        acceleration = [self._read_word(register) / accel_lsb_per_g * 9.80665 for register in (0x3B, 0x3D, 0x3F)]
        temperature = self._read_word(0x41) / 340.0 + 36.53
        gyro = [math.radians(self._read_word(register) / gyro_lsb_per_dps) for register in (0x43, 0x45, 0x47)]
        return RawIMUReading(*acceleration, *gyro, temperature_c=temperature)

    def close(self) -> None:
        if not self._closed:
            close = getattr(self._bus, "close", None)
            if close is not None:
                close()
            self._closed = True
