# PipeVision â€” Hardware Handoff & Interface Specification (Phase 14)

> **Document Status**: Production Specification for Physical Robot Integration
> **Target Audience**: Mechatronics Engineeers, Embedded Developers, System Integrators
> **Physical Hardware Status**: TBD (Software/Hardware Interface Standardized)

---

## 1. Hardware Architecture & Interface Mapping

The PipeVision system enforces a hardware-agnostic adapter boundary. Future physical robot components interface with PipeVision domain models through standardized transport and gateway layers without altering backend orchestrators or analytical pipelines.

### 1.1 Logical Hardware Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                             PHYSICAL ROBOT HARDWARE                              â”‚
â”‚                                                                                  â”‚
â”‚  [Front Camera]    [IMU Sensor]    [Wheel Encoder]   [Pressure/Water Sensors]     â”‚
â”‚        â”‚                 â”‚                â”‚                    â”‚                 â”‚
â”‚        â–¼                 â–¼                â–¼                    â–¼                 â”‚
â”‚  (USB / RTSP)      (UART / I2C)       (UART / GPIO)        (I2C / ADC)           â”‚
â”‚        â”‚                 â”‚                â”‚                    â”‚                 â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”‚
â”‚  â”‚                     ONBOARD EDGE COMPUTER / MCU DRIVER                      â”‚ â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜ â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                                       â”‚
                    Physical Communication Link (Ethernet / Serial)
                                       â”‚
                                       â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                         PIPEVISION SOFTWARE ARCHITECTURE                         â”‚
â”‚                                                                                  â”‚
â”‚                        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                         â”‚
â”‚                        â”‚     RobotTransport (Base)     â”‚                         â”‚
â”‚                        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜                         â”‚
â”‚                                        â”‚                                         â”‚
â”‚                        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”                         â”‚
â”‚                        â”‚      RobotGatewayAdapter      â”‚                         â”‚
â”‚                        â””â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜                         â”‚
â”‚                                â”‚               â”‚                                 â”‚
â”‚          â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”   â”Œâ”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚
â”‚          â–¼                             â–¼   â–¼                                 â–¼   â”‚
â”‚  RobotTelemetry                    RobotPose                     CanonicalFrame  â”‚
â”‚  (Telemetry Manager)         (Robot Localizer)            (Inspection Gateway)  â”‚
â”‚          â”‚                             â”‚                                 â”‚       â”‚
â”‚          â–¼                             â–¼                                 â–¼       â”‚
â”‚  Mission Orchestrator           Digital Twin Snapshot              AI Pipeline   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### 1.2 Hardware Interface Mapping Table

| Hardware Role | Recommended Interface | Software Driver Layer | Software Adapter | PipeVision Contract |
| :--- | :--- | :--- | :--- | :--- |
| **Onboard Computer** | Ethernet (TCP/UDP) or Serial (UART/USB) | POSIX Socket / `pyserial` | `RobotTransport` / `RobotGatewayAdapter` | Gateway Connection State |
| **Motor/Control MCU** | Serial / USB UART (115200+ baud) | Microcontroller Firmware | `RobotController` | `robot/protocol/commands.json` |
| **Inspection Camera** | USB 3.0 / Ethernet (RTSP stream) | V4L2 / OpenCV / RTSP Client | `HardwareFramePacket` | `CanonicalInspectionFrame` |
| **IMU Sensor** | SPI / I2C / Serial UART | Embedded IMU Driver | Telemetry Parser (`parse_telemetry`) | `ImuData` (`RobotTelemetry.imu`) |
| **Distance / Odometry** | Quadrature Encoder / Laser Ranging | MCU Counter / Odometry Driver | Telemetry Parser (`parse_telemetry`) | `RobotTelemetry.distance_m` |
| **Pressure Sensors** | I2C / Analog (ADC) | MCU Sensor Driver | Telemetry Parser (`parse_telemetry`) | `PressureData` (`RobotTelemetry.pressure`) |
| **Water Quality Sensors**| I2C / SPI / Analog | MCU Sensor Driver | Telemetry Parser (`parse_telemetry`) | `WaterData` (`RobotTelemetry.water`) |
| **Motor Drivers** | PWM / CAN Bus | MCU PWM/CAN Driver | `RobotController` | Movement & Actuation Commands |
| **Power System** | Battery BMS (SMBus/I2C) | BMS Telemetry Driver | Telemetry Parser (`parse_telemetry`) | `RobotTelemetry.battery_percent` |

*Note: Component part numbers not yet finalized by the mechatronics team remain marked as **TBD / hardware-dependent**.*

---

## 2. Data Contracts & Mapping

PipeVision mandates strict adherence to existing domain data structures. No duplicate models or secondary schemas are to be created for physical hardware bring-up.

### 2.1 Authoritative Contracts

1. **Telemetry**: `robot.telemetry.models.RobotTelemetry`
2. **IMU**: `robot.telemetry.models.ImuData`
3. **Localization / Pose**: `robot.localization.models.RobotPose`
4. **Camera Inspection Frame**: `backend.app.services.inspection.models.CanonicalInspectionFrame`
5. **Commands Protocol**: `robot/protocol/commands.json`

---

## 3. Communication Protocol & Transport Options

The physical robot must connect to PipeVision via an implementation of `RobotTransport`.

### 3.1 Transport Options
- **`EthernetTransport`**: Recommended for high-bandwidth inspection setups (RTSP video + TCP/UDP JSON telemetry).
- **`SerialTransport`**: Suitable for tethered UART/USB connections (JSON packets over serial line).
- **`SimulatorTransport`**: Software reference transport used for testing, CI, and hardware emulation.

### 3.2 Transport Interface Contract

Every hardware transport implementation must adhere to the abstract `RobotTransport` interface:
```python
class RobotTransport(ABC):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    @property
    def is_connected(self) -> bool: ...
    def send(self, message: dict[str, Any] | str) -> None: ...
    def receive(self, timeout: float | None = None) -> dict[str, Any] | str | None: ...
```

---

## 4. Camera Interface Specification

The inspection camera captures pipe interior visual media and forwards raw bytes to `RobotGatewayAdapter.ingest_camera_frame()`.

### 4.1 Required Frame Contract

Every frame packet captured by hardware must provide:
- **`robot_id`** (`str`): Unique robot identifier.
- **`mission_id`** (`str`): Active mission identifier.
- **`camera_id`** (`str`): Camera source identifier (e.g., `"cam-front-01"`).
- **`frame_id`** (`str`): Unique or deterministically derived frame identifier.
- **`frame_index`** (`int`): Monotonically increasing 0-based frame counter.
- **`timestamp`** (`datetime`): UTC ISO 8601 capture timestamp.
- **`source`** (`str`): Set explicitly to `"live"`.
- **`image_bytes`** (`bytes`): Valid image payload (JPEG or PNG format).

### 4.2 Optional Metadata
- **`distance_m`** (`float | None`): Pipe inspection distance in meters. If unavailable, set to `None`.
- **`pose`** (`RobotPose | None`): 6-DOF/3-DOF localized pose. If unavailable, set to `None`.

### 4.3 Technical Requirements
- **Image Format**: JPEG or PNG compressed bytes.
- **Expected Resolution**: Min `640x480`, Recommended `1920x1080` (Full HD).
- **Target Frame Rate**: 10 to 30 FPS depending on robot travel speed.
- **Dropped-Frame Behavior**: If frame capture drops due to network jitter, `frame_index` increments based on captured frame sequence; missing frames do NOT crash ingestion.

---

## 5. IMU & Telemetry Interface Specification

### 5.1 IMU Fields (`ImuData`)

| Field | Description | Units | Required |
| :--- | :--- | :--- | :--- |
| `ax` | Linear acceleration along X-axis | $\text{m/s}^2$ | Yes |
| `ay` | Linear acceleration along Y-axis | $\text{m/s}^2$ | Yes |
| `az` | Linear acceleration along Z-axis | $\text{m/s}^2$ | Yes |
| `gx` | Angular velocity around X-axis (pitch rate) | $\text{rad/s}$ | Yes |
| `gy` | Angular velocity around Y-axis (roll rate) | $\text{rad/s}$ | Yes |
| `gz` | Angular velocity around Z-axis (yaw rate) | $\text{rad/s}$ | Yes |

### 5.2 Sensor Data Handling & Normalization
- All timestamps must be UTC ISO 8601 formatted strings or UTC `datetime` objects.
- Optional sensors (`battery_percent`, `body_diameter_mm`, `pressure`, `water`) must remain `None` if hardware is not fitted with those sensors.
- **Zero Synthetic Data**: Fake or estimated values must NEVER be generated at the hardware adapter level.

---

## 6. Distance & Odometry Specification

### 6.1 Distance Ingestion
- **Metric Units**: Meters (`m`), rounded to 3 decimal places.
- **Monotonicity**: Distance should monotonically increase during forward pipe inspection.
- **Missing Distance**: If physical hardware lacks wheel encoders or distance sensors, set `distance_m = None`. PipeVision downstream services handle `distance_m = None` appropriately.

---

## 7. Localization Specification

PipeVision consumes localization updates via `RobotPose` and `RobotLocalizer`.

### 7.1 Localization Quality Enum (`LocalizationQuality`)
- **`TRACKING`**: Normal high-confidence state (active IMU/encoder fusion).
- **`DEGRADED`**: Reduced confidence (e.g., wheel slip or missing IMU updates).
- **`INVALID`**: Corrupted or out-of-bounds sensor readings.
- **`INITIALIZING` / `UNAVAILABLE`**: System starting up or odometry unequipped.

---

## 8. Command Path & Safety Architecture

Commands dispatched from PipeVision MUST execute via `RobotController` and strictly obey `robot/protocol/commands.json`.

### 8.1 Command Execution Flow

```
PipeVision Gateway Method
    â†“
RobotController.<method>()  [Enforces Safety & State Checks]
    â†“
Protocol Command Dict (JSON Schema Validated against commands.json)
    â†“
RobotTransport.send()
    â†“
Physical MCU Motor Driver
```

### 8.2 Supported Protocol Commands

| Gateway Method | Protocol Command Name | Arguments | Description |
| :--- | :--- | :--- | :--- |
| `move(linear, angular)` | `MOVE` | `{"linear": float, "angular": float}` | Actuate locomotion drives |
| `stop()` | `STOP` | `{}` | Halt linear and angular movement |
| `emergency_stop()` | `EMERGENCY_STOP` | `{}` | Instant safety lock, clear queue |
| `camera_pan(angle_deg)`| `CAMERA_PAN` | `{"angle_deg": float}` | Pan inspection camera servo |
| `clean_start(mode)` | `CLEAN_START` | `{"mode": string}` | Engage pipe cleaning attachment |
| `clean_stop()` | `CLEAN_STOP` | `{}` | Disengage pipe cleaning attachment |
| `inflate(target)` | `INFLATE` | `{"target_pressure_kpa": float}` | Inflate crawler anchoring bladders |
| `deflate()` | `DEFLATE` | `{}` | Deflate crawler anchoring bladders |
| `hold_pressure(target)`| `HOLD_PRESSURE` | `{"target_pressure_kpa": float}` | Maintain pressure setpoint |
| `sample_open()` | `SAMPLE_OPEN` | `{}` | Open water sampling valve |
| `sample_close()` | `SAMPLE_CLOSE` | `{}` | Close water sampling valve |

### 8.3 Emergency Stop Safety Boundary
`emergency_stop()` in `RobotController` sets state to `ControllerState.EMERGENCY_STOP` and transmits `EMERGENCY_STOP` to hardware immediately. It has **zero dependencies** on database sessions, AI networks, or cloud endpoints.

---

## 9. Timestamp Synchronization Strategy

1. **Timezone Policy**: All timestamps are strictly UTC (`timezone.utc`).
2. **Clock Source Hierarchy**:
   - Hardware capture timestamp from sensor/MCU RTC if synchronized via NTP/PTP.
   - Onboard Edge Computer host clock upon packet ingestion if MCU clock is un-synchronized.
3. **Prohibition**: Backend processing time must NEVER overwrite explicit hardware capture timestamps.

---

## 10. Connection Failure & Recovery Matrix

| Failure Mode | Detection | State Transition | Safe Action | Recovery Attempt | Mission Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Physical Link Loss** | Socket disconnect / Serial EOF | `CONNECTED` â†’ `DISCONNECTED` | Issue hardware STOP (MCU watchdog) | Re-open transport socket every 2.0s | Pause Mission |
| **Telemetry Timeout** | No telemetry for > `telemetry_timeout_s` | `STREAMING` â†’ `DISCONNECTED` | Set `failure_reason = TELEMETRY_TIMEOUT` | Trigger transport ping/reconnect | Pause Mission |
| **Frame Stream Timeout**| No camera frame for > `frame_timeout_s` | Diagnostic Flag Set | Mark frame stream stale | Reset camera V4L2/RTSP stream | Continue telemetry |
| **Malformed Packet** | JSON parse or validation error | Increment `error_count` | Drop bad packet, log raw string | Request packet retransmission | Continue Mission |
| **Mission Mismatch** | Received `mission_id` != Expected | `failure_reason = MISSION_MISMATCH` | Reject packet ingestion | Alert operator | Pause Ingestion |

---

## 11. Electrical & Interface Checklist for Assembly Team

- [ ] **Onboard Computer Power**: Stabilized DC-DC converter supply (voltage TBD based on SBC selection).
- [ ] **MCU Logic Levels**: 3.3V / 5V TTL logic level shifters on UART lines if connecting to 3.3V Raspberry Pi / Jetson GPIOs.
- [ ] **Camera Interface**: Dedicated USB 3.0 controller or 1Gbps Ethernet interface to avoid frame dropping.
- [ ] **IMU Bus**: Shielded twisted-pair wiring for SPI/I2C/UART IMU signals to reduce motor noise interference.
- [ ] **Emergency Hardware Cutoff**: Hardware relay cut-off switch wired in series with motor power rails alongside software `EMERGENCY_STOP`.
- [ ] **MCU Watchdog Timer**: MCU firmware MUST implement a 500ms safety watchdog timer that halts motors if no `MOVE` or heartbeat command is received.

---

## 12. Hardware Compatibility Validation Matrix

| Component | Software Status | Emulation Status | Physical Hardware | Validation Method |
| :--- | :--- | :--- | :--- | :--- |
| **Transport Layer** | READY IN SOFTWARE | SIMULATED (`SimulatorTransport`) | HARDWARE TBD | Automated Gateway Tests |
| **Command Protocol** | READY IN SOFTWARE | SIMULATED (`commands.json` schema) | HARDWARE TBD | Protocol Validation Suite |
| **Telemetry Pipeline**| READY IN SOFTWARE | SIMULATED (`parse_telemetry`) | HARDWARE TBD | Telemetry Parser Unit Tests |
| **Inspection Camera**| READY IN SOFTWARE | SIMULATED (`HardwareFramePacket`) | HARDWARE TBD | Ingestion Gateway Tests |
| **IMU Module** | READY IN SOFTWARE | SIMULATED (`ImuData`) | HARDWARE TBD | Localizer & Telemetry Tests |
| **Odometry / Encoder**| READY IN SOFTWARE | SIMULATED (`distance_m`) | HARDWARE TBD | Pose & Mapping Integration |
| **Motor Drivers** | READY IN SOFTWARE | SIMULATED (`RobotController`) | HARDWARE TBD | Safety & State Tests |
| **Edge Computer** | READY IN SOFTWARE | SIMULATED (Local Host OS) | HARDWARE TBD | Full Stack Regression |

---

## 13. Physical Robot Bring-up Checklist (Phase 15 Readiness)

When physical hardware is assembled, follow this procedure:
1. Connect physical transport (Serial or Ethernet cable).
2. Instantiate `RobotTransport` (e.g. `SerialTransport(port="/dev/ttyUSB0", baudrate=115200)`).
3. Instantiate `RobotGatewayAdapter(transport=physical_transport, robot_id="...", mission_id="...")`.
4. Call `gateway.connect()`. Verify connection state becomes `CONNECTED`.
5. Execute `gateway.move(0.1, 0.0)` for 1 second, followed by `gateway.stop()`. Verify physical wheel rotation.
6. Trigger `gateway.emergency_stop()`. Verify immediate motor power cutoff.
7. Start camera stream and feed `HardwareFramePacket` to `gateway.ingest_camera_frame()`.
8. Verify telemetry and frame ingestion in `MissionOrchestrator` and `DigitalTwinSynchronizer`.
