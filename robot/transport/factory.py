"""Hardware Abstraction Layer (HAL) transport factory.

Centralises all transport-selection logic so that the rest of the system
can remain transport-agnostic.  The backend ``RobotManager`` delegates to
:func:`create_transport` rather than containing its own ``if/elif`` chains.

Transport selection order
-------------------------
1. ``transport_type`` argument (explicit, highest priority)
2. ``ROBOT_TRANSPORT_TYPE`` environment variable (via ``get_settings``)
3. Default: ``"simulator"``

Supported transport type strings
---------------------------------
- ``"simulator"``        → :class:`~robot.transport.simulator.SimulatorTransport`
- ``"rpi"`` / ``"raspberry_pi"`` / ``"raspberrypi"``
                         → :class:`~robot.transport.raspberry_pi.RaspberryPiHardwareTransport`
- ``"ethernet"`` / ``"tcp"`` / ``"udp"``
                         → :class:`~robot.transport.ethernet.EthernetTransport`
- ``"serial"``           → :class:`~robot.transport.serial.SerialTransport`
"""

from __future__ import annotations

import logging

from robot.transport.base import RobotTransport, TransportError

logger = logging.getLogger(__name__)

# Canonical aliases for each physical transport
_RPI_ALIASES = frozenset({"rpi", "raspberry_pi", "raspberrypi"})
_ETHERNET_ALIASES = frozenset({"ethernet", "tcp", "udp"})
_SERIAL_ALIASES = frozenset({"serial"})
_SIMULATOR_ALIASES = frozenset({"simulator", "sim"})

SUPPORTED_TRANSPORT_TYPES: frozenset[str] = (
    _RPI_ALIASES | _ETHERNET_ALIASES | _SERIAL_ALIASES | _SIMULATOR_ALIASES
)


class TransportFactoryError(TransportError):
    """Raised when the transport factory cannot create a requested transport."""


def create_transport(
    robot_id: str,
    mission_id: str | None = None,
    transport_type: str | None = None,
    *,
    # Simulator overrides
    sim_step_interval: float = 0.5,
    # RPi / Ethernet overrides
    host: str | None = None,
    port: int | None = None,
    dry_run: bool | None = None,
    hardware_enabled: bool | None = None,
    gpio_enabled: bool | None = None,
    servo_driver: object | None = None,
    servo_config: object | None = None,
    imu_enabled: bool | None = None,
    imu_reader: object | None = None,
    imu_config: object | None = None,
    pico_uart: object | None = None,
    # Serial overrides
    serial_port: str | None = None,
    baudrate: int | None = None,
) -> RobotTransport:
    """Create and return the appropriate :class:`~robot.transport.base.RobotTransport`.

    All optional keyword arguments override the corresponding settings values
    when provided, enabling clean dependency injection in tests.

    Parameters
    ----------
    robot_id:
        Identifier of the robot this transport will serve.
    mission_id:
        Active mission identifier (used by SimulatorTransport only).
    transport_type:
        Override transport type string.  When ``None`` the value from
        ``Settings.robot_transport_type`` is used.
    sim_step_interval:
        Simulator clock step in seconds (SimulatorTransport only).
    host:
        TCP hostname/IP for RPi and Ethernet transports.
    port:
        TCP port for RPi and Ethernet transports.
    dry_run:
        When ``True`` the RPi transport logs commands but never opens a
        real socket.  Defaults to ``Settings.robot_dry_run``.
    serial_port:
        Serial device path, e.g. ``"/dev/ttyUSB0"`` or ``"COM3"``.
    baudrate:
        Serial baud rate.

    Returns
    -------
    RobotTransport
        A concrete transport ready to be passed to
        :class:`~robot.gateway.adapter.RobotGatewayAdapter`.

    Raises
    ------
    TransportFactoryError
        When ``transport_type`` is not a recognised alias.
    """
    # Import here to avoid circular dependency at module-load time.
    # The backend config is an optional dependency for the robot package.
    try:
        from backend.app.config import get_settings
        settings = get_settings()
    except (ImportError, AttributeError):  # pragma: no cover – robot package used standalone
        settings = None

    # Resolve transport type
    ttype = (transport_type or (settings.robot_transport_type if settings else "simulator")).lower()

    if ttype not in SUPPORTED_TRANSPORT_TYPES:
        raise TransportFactoryError(
            f"Unknown transport type '{ttype}'. "
            f"Supported: {sorted(SUPPORTED_TRANSPORT_TYPES)}"
        )

    # ── RPi Hardware ────────────────────────────────────────────────────────
    if ttype in _RPI_ALIASES:
        _host = host or (settings.robot_host if settings else "192.168.1.100")
        _port = port or (settings.robot_port if settings else 5000)
        # dry_run kwarg wins; fallback to config; default True for safety
        _dry_run: bool
        if dry_run is not None:
            _dry_run = dry_run
        elif settings is not None and hasattr(settings, "robot_dry_run"):
            _dry_run = settings.robot_dry_run
        else:
            _dry_run = True
        _hardware_enabled = (
            hardware_enabled
            if hardware_enabled is not None
            else bool(getattr(settings, "robot_hardware_enabled", False))
        )

        from robot.transport.raspberry_pi import RaspberryPiHardwareTransport

        logger.info(
            "HAL factory: RaspberryPiHardwareTransport host=%s port=%d dry_run=%s robot_id=%s",
            _host,
            _port,
            _dry_run,
            robot_id,
        )
        resolved_servo_driver = servo_driver
        _gpio_enabled = (
            gpio_enabled
            if gpio_enabled is not None
            else bool(getattr(settings, "robot_gpio_enabled", False))
        )
        if resolved_servo_driver is None and _hardware_enabled and _gpio_enabled and not _dry_run:
            from robot.transport.servo import (
                GpioZeroServoDriver,
                servo_rig_config_from_json,
            )

            config = servo_config or servo_rig_config_from_json(
                getattr(settings, "robot_servo_config_json", None)
            )
            resolved_servo_driver = GpioZeroServoDriver(config)
        resolved_imu_reader = imu_reader
        _imu_enabled = (
            imu_enabled
            if imu_enabled is not None
            else bool(getattr(settings, "robot_mpu6050_enabled", False))
        )
        if resolved_imu_reader is None and _hardware_enabled and _imu_enabled and not _dry_run:
            from robot.imu.mpu6050 import IMUError, MPU6050Config, MPU6050Reader

            config = imu_config or MPU6050Config(
                i2c_bus=int(getattr(settings, "robot_mpu6050_i2c_bus", 1)),
                i2c_address=int(getattr(settings, "robot_mpu6050_i2c_address", 0x68)),
                accelerometer_scale_g=int(getattr(settings, "robot_mpu6050_accelerometer_scale_g", 2)),
                gyroscope_scale_dps=int(getattr(settings, "robot_mpu6050_gyroscope_scale_dps", 250)),
            )
            try:
                resolved_imu_reader = MPU6050Reader(config)
            except (IMUError, OSError) as err:
                # A missing/unpowered optional sensor must not prevent the
                # robot gateway from starting or serving other telemetry.
                logger.warning("MPU6050 unavailable; continuing without local IMU: %s", err)
        resolved_pico_uart = pico_uart
        if (
            resolved_pico_uart is None
            and _hardware_enabled
            and bool(getattr(settings, "robot_pico_uart_enabled", False))
            and not _dry_run
        ):
            from robot.transport.pico_uart import PicoUartConfig, SerialPicoUart

            pico_config = PicoUartConfig(
                port=str(getattr(settings, "robot_pico_uart_port", "")),
                baudrate=int(getattr(settings, "robot_pico_uart_baudrate", 115200)),
                timeout_s=float(getattr(settings, "robot_pico_uart_timeout_s", 1.0)),
            )
            resolved_pico_uart = SerialPicoUart(pico_config)
        return RaspberryPiHardwareTransport(
            host=_host,
            port=_port,
            dry_run=_dry_run,
            servo_driver=resolved_servo_driver,
            imu_reader=resolved_imu_reader,
            pico_uart=resolved_pico_uart,
        )

    # ── Ethernet / TCP / UDP ─────────────────────────────────────────────────
    if ttype in _ETHERNET_ALIASES:
        _host = host or (settings.robot_host if settings else "192.168.1.100")
        _port = port or (settings.robot_port if settings else 5000)
        protocol = "udp" if ttype == "udp" else "tcp"

        from robot.transport.ethernet import EthernetTransport

        logger.info(
            "HAL factory: EthernetTransport host=%s port=%d protocol=%s robot_id=%s",
            _host,
            _port,
            protocol,
            robot_id,
        )
        return EthernetTransport(host=_host, port=_port, protocol=protocol)

    # ── Serial ───────────────────────────────────────────────────────────────
    if ttype in _SERIAL_ALIASES:
        _serial_port = serial_port or (
            settings.robot_serial_port if settings else "/dev/ttyUSB0"
        )
        _baudrate = baudrate or (settings.robot_baudrate if settings else 115200)

        from robot.transport.serial import SerialTransport

        logger.info(
            "HAL factory: SerialTransport port=%s baudrate=%d robot_id=%s",
            _serial_port,
            _baudrate,
            robot_id,
        )
        return SerialTransport(port=_serial_port, baudrate=_baudrate)

    # ── Simulator (default) ──────────────────────────────────────────────────
    from robot.transport.simulator import SimulatorTransport

    logger.info("HAL factory: SimulatorTransport robot_id=%s", robot_id)
    return SimulatorTransport(
        robot_id=robot_id,
        mission_id=mission_id or "MISSION-ACTIVE",
        step_interval=sim_step_interval,
    )
