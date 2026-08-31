"""PipeVision Robot Gateway and Controller Manager."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from backend.app.schemas.robot import RobotCommandResponse
from robot.control.robot_controller import ControllerValidationError
from robot.gateway.adapter import RobotGatewayAdapter
from robot.transport.simulator import SimulatorTransport

logger = logging.getLogger(__name__)

SUPPORTED_COMMANDS = {
    "MOVE",
    "STOP",
    "EMERGENCY_STOP",
    "CAMERA_PAN",
    "CLEAN_START",
    "CLEAN_STOP",
    "SAMPLE_OPEN",
    "SAMPLE_CLOSE",
    "INFLATE",
    "DEFLATE",
    "HOLD_PRESSURE",
}


class RobotManager:
    """Manager managing robot gateway/controller connections and command routing."""

    def __init__(self) -> None:
        self._adapters: dict[str, RobotGatewayAdapter] = {}
        self._lock = Lock()

    def get_adapter(self, robot_id: str, mission_id: str | None = None) -> RobotGatewayAdapter:
        """Get or create connected RobotGatewayAdapter for a given robot_id."""
        with self._lock:
            adapter = self._adapters.get(robot_id)
            if adapter is None or not adapter.is_connected:
                logger.info("Initializing SimulatorTransport for robot_id=%s", robot_id)
                transport = SimulatorTransport(robot_id=robot_id, mission_id=mission_id or "MISSION-ACTIVE")
                adapter = RobotGatewayAdapter(
                    transport=transport,
                    robot_id=robot_id,
                    mission_id=mission_id,
                )
                adapter.connect(robot_id=robot_id, mission_id=mission_id)
                self._adapters[robot_id] = adapter
            elif mission_id and adapter.mission_id != mission_id:
                adapter.mission_id = mission_id

            return adapter

    def execute_command(
        self,
        robot_id: str,
        command_name: str,
        arguments: dict[str, Any] | None = None,
        mission_id: str | None = None,
    ) -> RobotCommandResponse:
        """Safely execute a typed command via RobotGatewayAdapter and RobotController."""
        cmd_upper = command_name.upper()
        if cmd_upper not in SUPPORTED_COMMANDS:
            raise ControllerValidationError(f"Unsupported command '{command_name}'. Supported: {sorted(SUPPORTED_COMMANDS)}")

        adapter = self.get_adapter(robot_id, mission_id=mission_id)
        args = arguments or {}

        if cmd_upper == "MOVE":
            linear = float(args.get("linear", 0.0))
            angular = float(args.get("angular", 0.0))
            adapter.move(linear, angular)

        elif cmd_upper == "STOP":
            adapter.stop()

        elif cmd_upper == "EMERGENCY_STOP":
            adapter.emergency_stop()

        elif cmd_upper == "CAMERA_PAN":
            angle_deg = float(args.get("angle_deg", 0.0))
            adapter.camera_pan(angle_deg)

        elif cmd_upper == "CLEAN_START":
            mode = str(args.get("mode", "DEFAULT"))
            adapter.clean_start(mode)

        elif cmd_upper == "CLEAN_STOP":
            adapter.clean_stop()

        elif cmd_upper == "SAMPLE_OPEN":
            adapter.sample_open()

        elif cmd_upper == "SAMPLE_CLOSE":
            adapter.sample_close()

        elif cmd_upper == "INFLATE":
            target_pressure = float(args.get("target_pressure_kpa", 150.0))
            adapter.inflate(target_pressure)

        elif cmd_upper == "DEFLATE":
            adapter.deflate()

        elif cmd_upper == "HOLD_PRESSURE":
            target_pressure = float(args.get("target_pressure_kpa", 150.0))
            adapter.hold_pressure(target_pressure)

        controller_state = adapter.controller.state.value if adapter.controller else "UNKNOWN"

        return RobotCommandResponse(
            robot_id=robot_id,
            command=cmd_upper,
            status="accepted",
            controller_state=controller_state,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def emergency_stop(self, robot_id: str, mission_id: str | None = None) -> RobotCommandResponse:
        """Trigger emergency stop idempotently for a given robot_id."""
        adapter = self.get_adapter(robot_id, mission_id=mission_id)
        adapter.emergency_stop()

        controller_state = adapter.controller.state.value if adapter.controller else "EMERGENCY_STOP"

        return RobotCommandResponse(
            robot_id=robot_id,
            command="EMERGENCY_STOP",
            status="accepted",
            controller_state=controller_state,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def disconnect_all(self) -> None:
        """Cleanly disconnect all active robot adapters."""
        with self._lock:
            for robot_id, adapter in list(self._adapters.items()):
                try:
                    adapter.disconnect()
                except (OSError, RuntimeError) as exc:
                    logger.warning("Error disconnecting adapter for %s: %s", robot_id, exc)
            self._adapters.clear()


robot_manager = RobotManager()
