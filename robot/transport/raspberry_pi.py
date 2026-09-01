"""Raspberry Pi 4 Physical Hardware Transport Implementation."""

from __future__ import annotations

import json
import logging
import select
import socket
from typing import Any

from robot.imu.mpu6050 import IMUReader, RawIMUReading
from robot.transport.base import (
    InvalidMessageError,
    RobotTransport,
    TransportConnectionError,
    TransportNotConnectedError,
    load_command_protocol,
    validate_command_dict,
)
from robot.transport.pico_uart import PicoUartLink
from robot.transport.servo import ServoDriver

logger = logging.getLogger(__name__)


class RaspberryPiHardwareTransport(RobotTransport):
    """Physical hardware transport for Raspberry Pi 4 onboard edge computer over Ethernet/TCP socket.

    Can operate in:
      - Live Mode: Connects to physical Raspberry Pi 4 TCP server on host:port.
      - Dry Run Mode: Safe fallback for off-robot dev/testing without physical hardware connected.
    """

    def __init__(
        self,
        host: str = "192.168.1.100",
        port: int = 5000,
        timeout: float = 1.0,
        dry_run: bool = False,
        servo_driver: ServoDriver | None = None,
        imu_reader: IMUReader | None = None,
        pico_uart: PicoUartLink | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.dry_run = dry_run
        self._socket: socket.socket | None = None
        self._connected = False
        self._sent_messages: list[dict[str, Any]] = []
        self._protocol_schema = load_command_protocol()
        # No GPIO driver is created implicitly. This keeps startup safe and
        # makes the physical layer replaceable with a test double.
        self.servo_driver = servo_driver
        self.imu_reader = imu_reader
        self.pico_uart = pico_uart

    def connect(self) -> None:
        """Establish transport connection to Raspberry Pi 4 onboard daemon."""
        if self._connected:
            return

        if self.dry_run:
            logger.info(
                "RaspberryPiHardwareTransport connected in DRY-RUN mode (%s:%d).",
                self.host,
                self.port,
            )
            self._connected = True
            self._connect_pico_uart()
            return

        sock: socket.socket | None = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            self._socket = sock
            self._connected = True
            self._connect_pico_uart()
            logger.info(
                "Successfully connected RaspberryPiHardwareTransport to %s:%d.",
                self.host,
                self.port,
            )
        except OSError as err:
            if sock is not None:
                sock.close()
            logger.warning(
                "Could not connect to Raspberry Pi 4 hardware at %s:%d (%s). Falling back to safe dry-run mode.",
                self.host,
                self.port,
                err,
            )
            self.dry_run = True
            self._connected = True

    def disconnect(self) -> None:
        """Disconnect transport cleanly."""
        if self.servo_driver is not None:
            try:
                # Explicit shutdown cleanup is the only automatic neutral move.
                self.servo_driver.neutral_all()
            except Exception as err:  # noqa: BLE001
                logger.warning("Could not neutralize servos during shutdown: %s", err)
            try:
                self.servo_driver.close()
            except Exception as err:  # noqa: BLE001
                logger.warning("Could not close servo driver: %s", err)
        if self.imu_reader is not None:
            try:
                self.imu_reader.close()
            except Exception as err:  # noqa: BLE001
                logger.warning("Could not close IMU reader: %s", err)
        if self.pico_uart is not None:
            try:
                self.pico_uart.disconnect()
            except Exception as err:  # noqa: BLE001
                logger.warning("Could not close Pico UART: %s", err)
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            finally:
                self._socket = None
        self._connected = False
        logger.info("RaspberryPiHardwareTransport disconnected.")

    def _connect_pico_uart(self) -> None:
        """Connect the optional future Pico link without affecting main startup."""
        if self.pico_uart is None:
            return
        try:
            self.pico_uart.connect()
        except Exception as err:  # noqa: BLE001
            logger.warning("Pico UART unavailable; continuing without Pico link: %s", err)

    @property
    def is_connected(self) -> bool:
        """True if transport is active (or safely connected in dry-run mode)."""
        return self._connected

    @property
    def sent_messages(self) -> list[dict[str, Any]]:
        """List of commands sent (useful for testing/diagnostics)."""
        return list(self._sent_messages)

    def send(self, message: dict[str, Any] | str) -> None:
        """Send a command packet to Raspberry Pi 4 hardware."""
        if not self.is_connected:
            raise TransportNotConnectedError(
                "Cannot send message: RaspberryPiHardwareTransport is disconnected."
            )

        if isinstance(message, str):
            try:
                msg_dict = json.loads(message)
            except json.JSONDecodeError as err:
                raise InvalidMessageError(f"Invalid JSON string: {err}") from err
            raw_text = message
        elif isinstance(message, dict):
            msg_dict = message
            raw_text = json.dumps(message)
        else:
            raise InvalidMessageError(
                "Message must be a dictionary or a valid JSON string."
            )

        validate_command_dict(msg_dict, self._protocol_schema)
        self._sent_messages.append(msg_dict)

        self._apply_servo_command(msg_dict)

        if self.dry_run or self._socket is None:
            logger.debug("[RPI HARDWARE DRY-RUN SEND] %s", raw_text)
            return

        try:
            payload = (raw_text.strip() + "\n").encode("utf-8")
            self._socket.sendall(payload)
        except OSError as err:
            raise TransportConnectionError(
                f"Raspberry Pi hardware send error: {err}"
            ) from err

    def _apply_servo_command(self, message: dict[str, Any]) -> None:
        """Apply only protocol commands with an unambiguous servo meaning.

        MOVE is deliberately not translated into four servo angles: no gait,
        direction, or calibration contract exists in the current protocol.
        It remains available to the existing Raspberry Pi command endpoint.
        """
        if self.servo_driver is None:
            return
        name = message["name"]
        if name in ("STOP", "EMERGENCY_STOP"):
            self.servo_driver.neutral_all()
        elif name == "CAMERA_PAN":
            arguments = message.get("arguments", {})
            set_command_angle = getattr(self.servo_driver, "set_command_angle", None)
            if set_command_angle is None:
                set_command_angle = self.servo_driver.set_angle
            set_command_angle("camera_pan", float(arguments["angle_deg"]))

    def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None:
        """Receive a telemetry packet from Raspberry Pi 4 hardware."""
        if not self.is_connected:
            raise TransportNotConnectedError(
                "Cannot receive message: RaspberryPiHardwareTransport is disconnected."
            )

        if self.dry_run or self._socket is None:
            return None

        read_timeout = timeout if timeout is not None else self.timeout

        try:
            ready, _, _ = select.select([self._socket], [], [], read_timeout)
            if not ready:
                return None

            data = self._socket.recv(4096)
            if not data:
                return None

            decoded = data.decode("utf-8").strip()
            if not decoded:
                return None

            try:
                payload = json.loads(decoded)
                if isinstance(payload, dict):
                    self._attach_imu(payload)
                return payload
            except json.JSONDecodeError:
                return decoded
        except OSError as err:
            raise TransportConnectionError(
                f"Raspberry Pi hardware receive error: {err}"
            ) from err

    def read_imu(self) -> RawIMUReading | None:
        """Read one raw IMU sample, if an IMU reader was configured."""
        if self.imu_reader is None:
            return None
        try:
            return self.imu_reader.read()
        except Exception as err:  # noqa: BLE001
            logger.warning("MPU6050 read unavailable: %s", err)
            return None

    def _attach_imu(self, payload: dict[str, Any]) -> None:
        """Attach a raw sample to an existing telemetry packet when available."""
        if self.imu_reader is None or "robot_id" not in payload:
            return
        sample = self.read_imu()
        if sample is not None:
            payload["imu"] = sample.to_telemetry_dict()
