"""Simulated robot transport implementation."""

from __future__ import annotations

import io
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

from PIL import Image

if TYPE_CHECKING:
    from robot.gateway.models import HardwareFramePacket

from robot.transport.base import (
    InvalidMessageError,
    RobotTransport,
    TransportNotConnectedError,
    load_command_protocol,
    validate_command_dict,
)


@dataclass(frozen=True)
class SimulatorConfig:
    """Typed configuration parameters for deterministic robot simulator transport."""

    robot_id: str = "PV-SIM-001"
    mission_id: str = "SIM-MISSION-001"
    step_interval: float = 0.5
    linear_speed_m_s: float = 0.15
    camera_id: str = "cam-sim-01"
    simulated_camera_fps: float = 10.0
    enable_imu: bool = True
    enable_distance: bool = True
    enable_pressure: bool = True
    enable_water: bool = True
    enable_battery: bool = True


class SimulatorTransport(RobotTransport):
    """Deterministic simulated transport for testing and off-hardware development."""

    def __init__(
        self,
        robot_id: str = "PV-SIM-001",
        mission_id: str = "SIM-MISSION-001",
        step_interval: float = 0.5,
        config: SimulatorConfig | None = None,
        enable_imu: bool = True,
        enable_distance: bool = True,
        enable_pressure: bool = True,
        enable_water: bool = True,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = SimulatorConfig(
                robot_id=robot_id,
                mission_id=mission_id,
                step_interval=step_interval,
                enable_imu=enable_imu,
                enable_distance=enable_distance,
                enable_pressure=enable_pressure,
                enable_water=enable_water,
            )

        self.robot_id = self.config.robot_id
        self.mission_id = self.config.mission_id
        self.step_interval = self.config.step_interval

        self._connected = False
        self._t = 0.0
        self._outbound_commands: Queue[dict[str, Any] | str] = Queue()
        self._inbound_telemetry: Queue[dict[str, Any]] = Queue()
        self._protocol = load_command_protocol()
        self._current_state = "IDLE"
        self._linear_vel = 0.0
        self._angular_vel = 0.0

    def connect(self) -> None:
        """Connect simulator and initialize state."""
        self._connected = True
        self._t = 0.0
        self._current_state = "IDLE"
        self._linear_vel = 0.0
        self._angular_vel = 0.0
        while not self._outbound_commands.empty():
            try:
                self._outbound_commands.get_nowait()
            except Empty:
                break
        while not self._inbound_telemetry.empty():
            try:
                self._inbound_telemetry.get_nowait()
            except Empty:
                break

    def disconnect(self) -> None:
        """Disconnect simulator transport."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def send(self, message: dict[str, Any] | str) -> None:
        if not self._connected:
            raise TransportNotConnectedError(
                "Cannot send message: simulator transport is disconnected."
            )

        if isinstance(message, str):
            try:
                msg_dict = json.loads(message)
            except Exception as err:
                raise InvalidMessageError(f"Invalid JSON string: {err}") from err
        elif isinstance(message, dict):
            msg_dict = message
        else:
            raise InvalidMessageError(
                "Message must be a dictionary or a valid JSON string."
            )

        validate_command_dict(msg_dict, self._protocol)
        self._outbound_commands.put(msg_dict)

        cmd_name = msg_dict["name"]
        if cmd_name == "STOP":
            self._current_state = "IDLE"
            self._linear_vel = 0.0
            self._angular_vel = 0.0
        elif cmd_name == "EMERGENCY_STOP":
            self._current_state = "EMERGENCY_STOP"
            self._linear_vel = 0.0
            self._angular_vel = 0.0
        elif cmd_name == "MOVE":
            args = msg_dict.get("arguments", {})
            self._linear_vel = float(args.get("linear", 0.0))
            self._angular_vel = float(args.get("angular", 0.0))
            self._current_state = "INSPECTING" if self._linear_vel != 0 else "IDLE"

    def step(self) -> dict[str, Any]:
        """Step simulation clock forward and return generated telemetry packet."""
        if not self._connected:
            raise TransportNotConnectedError(
                "Cannot step simulation: transport is disconnected."
            )

        t = self._t
        distance = max(
            0.0,
            self.config.linear_speed_m_s * t + self._linear_vel * t,
        )
        body_diameter = 105.0 + 15.0 * math.sin(t / 5.0)

        packet: dict[str, Any] = {
            "robot_id": self.robot_id,
            "mission_id": self.mission_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": self._current_state,
        }

        if self.config.enable_battery:
            packet["battery_percent"] = max(0.0, 100.0 - t * 0.15)

        if self.config.enable_distance:
            packet["distance_m"] = round(distance, 3)

        packet["body_diameter_mm"] = round(body_diameter, 2)

        if self.config.enable_imu:
            packet["imu"] = {
                "ax": round(0.03 * math.sin(t), 4),
                "ay": round(0.02 * math.cos(t), 4),
                "az": 9.81,
                "gx": 0.02,
                "gy": 0.01,
                "gz": round(0.10 * math.sin(t / 2.0), 4),
            }

        if self.config.enable_pressure:
            packet["pressure"] = {
                "body_kpa": round(95.0 + 4.0 * math.sin(t / 4.0), 2),
                "front_anchor_kpa": 175.0,
                "rear_anchor_kpa": 170.0,
            }

        if self.config.enable_water:
            packet["water"] = {
                "temperature_c": round(25.0 + 0.5 * math.sin(t / 7.0), 2),
                "ph": round(6.9 + 0.08 * math.sin(t / 9.0), 2),
                "conductivity_ms_cm": round(1.6 + 0.15 * math.sin(t / 6.0), 2),
                "turbidity_ntu": round(30.0 + 5.0 * math.sin(t / 3.0), 2),
            }

        self._t += self.step_interval
        return packet

    def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None:
        if not self._connected:
            raise TransportNotConnectedError(
                "Cannot receive message: simulator transport is disconnected."
            )

        try:
            return self._inbound_telemetry.get(block=True, timeout=timeout)
        except Empty:
            return self.step()

    def generate_synthetic_frame(
        self,
        frame_index: int,
        distance_m: float | None = None,
        color: tuple[int, int, int] = (0, 128, 255),
    ) -> HardwareFramePacket:
        """Generate a deterministic synthetic JPEG frame packet for testing inspection ingestion."""
        from robot.gateway.models import HardwareFramePacket
        img = Image.new("RGB", (64, 64), color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        calc_distance = distance_m if distance_m is not None else round(0.15 * frame_index, 3)

        return HardwareFramePacket(
            camera_id=self.config.camera_id,
            image_bytes=buf.getvalue(),
            frame_index=frame_index,
            frame_id=f"sim-frame-{frame_index:06d}",
            timestamp=datetime.now(timezone.utc),
            distance_m=calc_distance if self.config.enable_distance else None,
            source="live",
        )
