"""Tests for the optional MPU6050 hardware abstraction."""

from __future__ import annotations

import pytest

from robot.imu.mpu6050 import FakeIMUReader, MPU6050Config, MPU6050Reader, RawIMUReading
from robot.telemetry.parser import parse_telemetry


class FakeSMBus:
    def __init__(self, values: dict[int, int]) -> None:
        self.values = values
        self.writes: list[tuple[int, int, int]] = []
        self.closed = False

    def write_byte_data(self, address: int, register: int, value: int) -> None:
        self.writes.append((address, register, value))

    def read_byte_data(self, address: int, register: int) -> int:
        return self.values.get(register, 0)

    def close(self) -> None:
        self.closed = True


def test_fake_reader_is_deterministic_and_closeable() -> None:
    sample = RawIMUReading(1.0, 2.0, 3.0, 0.1, 0.2, 0.3, 22.0)
    reader = FakeIMUReader(sample)
    assert reader.read() == sample
    assert reader.read_count == 1
    reader.close()
    with pytest.raises(RuntimeError):
        reader.read()


def test_mpu6050_reader_converts_registers_without_orientation_claim() -> None:
    bus = FakeSMBus({0x3B: 0x40, 0x3C: 0x00, 0x41: 0x00, 0x42: 0x00, 0x43: 0x00,
                     0x44: 0x00, 0x45: 0x00, 0x46: 0x00, 0x47: 0x00, 0x48: 0x00})
    reader = MPU6050Reader(MPU6050Config(i2c_bus=1, i2c_address=0x68), bus=bus)
    reading = reader.read()
    assert reading.ax_mps2 == pytest.approx(9.80665)
    assert reading.gx_rads == 0.0
    assert reading.temperature_c == pytest.approx(36.53)
    assert bus.writes == [(0x68, 0x6B, 0)]
    reader.close()
    assert bus.closed


def test_raw_reading_maps_to_existing_processed_telemetry_fields() -> None:
    raw = RawIMUReading(1, 2, 3, 4, 5, 6, 20).to_telemetry_dict()
    telemetry = parse_telemetry({"robot_id": "R1", "imu": raw})
    assert telemetry is not None
    assert telemetry.imu is not None
    assert telemetry.imu.ax == 1.0
    assert telemetry.imu.temperature_c == 20.0
