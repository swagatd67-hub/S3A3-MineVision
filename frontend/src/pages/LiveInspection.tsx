import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { CameraFeed } from '../components/CameraFeed';
import { ControlConsole } from '../components/ControlConsole';
import { StatusPanel } from '../components/StatusPanel';
import { CO2SensorPanel } from '../components/CO2SensorPanel';
import { MPU6050Panel } from '../components/MPU6050Panel';
import { TopNavBar } from '../components/TopNavBar';
import { SideNavBar, type ActiveNavTab } from '../components/SideNavBar';
import { SnapshotDrawer } from '../components/SnapshotDrawer';
import { SettingsModal } from '../components/SettingsModal';
import { NetworkMappingView } from '../components/NetworkMappingView';
import { DefectAnalyzerView } from '../components/DefectAnalyzerView';
import { CalibrationView } from '../components/CalibrationView';
import { MissionLogsView } from '../components/MissionLogsView';
import { HelpView } from '../components/HelpView';
import { playSound } from '../utils/audio';

import { telemetryWsClient } from '../api/telemetryWs';
import type {
  RobotDriveState,
  DriveCommand,
  SensorData,
  IMUData,
  DefectDetection,
  SnapshotItem,
  CameraId,
} from '../types';
import type {
  TelemetryData,
  WebSocketConnectionStatus,
} from '../types/telemetry';

export default function LiveInspection() {
  const { missionId = 'M-104' } = useParams<{ missionId?: string }>();

  // Navigation tab state
  const [activeTab, setActiveTab] = useState<ActiveNavTab>('telemetry');

  // Modals / Drawers
  const [isSnapshotDrawerOpen, setIsSnapshotDrawerOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  // System controls & state
  const [activeCamera, setActiveCamera] = useState<CameraId>('cam-01');
  const [isRecording, setIsRecording] = useState(true);
  const [recordSeconds, setRecordSeconds] = useState(148);
  const [isSoundMuted, setIsSoundMuted] = useState(false);
  const [, setLightIntensity] = useState(85);

  // WebSocket Connection State & Telemetry
  const [wsStatus, setWsStatus] = useState<WebSocketConnectionStatus>('DISCONNECTED');
  const [activeRobotId, setActiveRobotId] = useState<string>('ROV-01');

  // Pressure & Water Quality Real Telemetry State
  const [pressureData, setPressureData] = useState({
    body_kpa: 101.3,
    front_anchor_kpa: 180.0,
    rear_anchor_kpa: 175.0,
  });

  const [waterData, setWaterData] = useState({
    temperature_c: 22.5,
    ph: 7.2,
    conductivity_ms_cm: 1.4,
    turbidity_ntu: 15.0,
  });

  // Robot State
  const [robotState, setRobotState] = useState<RobotDriveState>({
    command: 'IDLE',
    direction: 'IDLE',
    speed: 0,
    maxSpeed: 100,
    gear: 'CRUISE',
    lightsOn: true,
    isReady: true,
    tetherLengthM: 142.8,
    distanceTraveledM: 142.8,
    batteryPercent: 78,
    isArmed: true,
    emergencyStop: false,
  });

  // Sensor Data (CO2 Local Simulated)
  const [sensorData] = useState<SensorData>(() => ({
    co2Ppm: 420,
    co2BaselinePpm: 400,
    status: 'NORMAL',
    timestampMs: Date.now(),
    historyPpm: [410, 412, 415, 418, 419, 422, 420],
  }));

  // IMU Data
  const [imuData, setImuData] = useState<IMUData>({
    accel: { x: 0.02, y: -0.01, z: 0.98 },
    accelX: 0.02,
    accelY: -0.01,
    accelZ: 0.98,
    gyro: { x: 0.1, y: 0.2, z: -0.1 },
    gyroX: 0.1,
    gyroY: 0.2,
    gyroZ: -0.1,
    pitchDeg: 1.2,
    rollDeg: -0.4,
    yawDeg: 87.5,
    orientation: {
      pitch: 1.2,
      roll: -0.4,
      yaw: 87.5,
    },
    historyAccel: [
      { x: 0.01, y: 0, z: 0.99 },
      { x: 0.02, y: -0.01, z: 0.98 },
      { x: 0.03, y: 0.01, z: 0.97 },
    ],
  });

  // Defect Detections
  const [defects] = useState<DefectDetection[]>([
    {
      id: 'DEF-001',
      type: 'Crack - Longitudinal',
      severity: 'HIGH',
      confidence: 0.94,
      distanceM: 124.5,
      clockPosition: '12:00',
      bounding: { x: 35, y: 25, width: 30, height: 40 },
    },
    {
      id: 'DEF-002',
      type: 'Joint Displacement',
      severity: 'MEDIUM',
      confidence: 0.88,
      distanceM: 138.2,
      clockPosition: '03:00',
      bounding: { x: 60, y: 55, width: 25, height: 25 },
    },
  ]);

  // Snapshots
  const [snapshots, setSnapshots] = useState<SnapshotItem[]>([
    {
      id: 'SNAP-001',
      imageUrl: 'https://images.unsplash.com/photo-1541888946425-d0fbb186a5b7?auto=format&fit=crop&w=800&q=80',
      timestamp: '14:25:40',
      cameraName: 'CAM 01 (FRONT)',
      distanceM: 142.8,
      defectCount: 2,
    },
  ]);

  // Buffer and throttled rendering refs
  const latestTelemetryPacketRef = useRef<TelemetryData | null>(null);
  const lastTimestampMsRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);

  // WebSocket lifecycle & event listener binding
  useEffect(() => {
    lastTimestampMsRef.current = 0;
    latestTelemetryPacketRef.current = null;

    const unsubStatus = telemetryWsClient.onStatusChange((status) => {
      setWsStatus(status);
    });

    const unsubTelemetry = telemetryWsClient.onTelemetry((event) => {
      const packet = event.data;
      if (!packet) return;

      // Mission filtering: only accept if mission_id matches active route mission
      if (packet.mission_id && packet.mission_id !== missionId) {
        return;
      }

      // Stale packet check: ignore out-of-order/older packets
      const packetTimeMs = packet.timestamp ? Date.parse(packet.timestamp) : Date.now();
      if (packetTimeMs < lastTimestampMsRef.current) {
        return;
      }
      lastTimestampMsRef.current = packetTimeMs;

      latestTelemetryPacketRef.current = packet;
    });

    const unsubAnalytics = telemetryWsClient.onAnalytics((event) => {
      if (event.mission_id && event.mission_id !== missionId) return;
      // Analytics update received safely
    });

    telemetryWsClient.connect();

    // Throttled frame loop (~20 FPS / 50ms) to prevent React state render storms
    let lastRenderTime = 0;
    const updateLoop = (now: number) => {
      if (now - lastRenderTime >= 50) {
        if (latestTelemetryPacketRef.current) {
          const data = latestTelemetryPacketRef.current;
          latestTelemetryPacketRef.current = null;

          if (data.robot_id) {
            setActiveRobotId(data.robot_id);
          }

          setRobotState((prev) => {
            const updated = { ...prev };
            if (typeof data.battery_percent === 'number') {
              updated.batteryPercent = data.battery_percent;
            }
            if (typeof data.distance_m === 'number') {
              updated.distanceTraveledM = data.distance_m;
            }
            if (data.state) {
              updated.isReady =
                data.state === 'INSPECTING' || data.state === 'IDLE' || data.state === 'READY';
            }
            return updated;
          });

          if (data.imu) {
            const { ax, ay, az, gx, gy, gz } = data.imu;
            const pitchRad = Math.atan2(ax, Math.sqrt(ay * ay + az * az));
            const rollRad = Math.atan2(ay, az);
            const pitchDeg = pitchRad * (180 / Math.PI);
            const rollDeg = rollRad * (180 / Math.PI);

            setImuData((prev) => ({
              ...prev,
              accel: { x: ax, y: ay, z: az },
              accelX: ax,
              accelY: ay,
              accelZ: az,
              gyro: { x: gx, y: gy, z: gz },
              gyroX: gx,
              gyroY: gy,
              gyroZ: gz,
              pitchDeg,
              rollDeg,
              // Yaw is NOT derived from accelerometer; preserving existing yaw value
              orientation: {
                pitch: pitchDeg,
                roll: rollDeg,
                yaw: prev.yawDeg,
              },
            }));
          }

          if (data.pressure) {
            setPressureData({
              body_kpa: data.pressure.body_kpa ?? 101.3,
              front_anchor_kpa: data.pressure.front_anchor_kpa ?? 180.0,
              rear_anchor_kpa: data.pressure.rear_anchor_kpa ?? 175.0,
            });
          }

          if (data.water) {
            setWaterData({
              temperature_c: data.water.temperature_c ?? 22.5,
              ph: data.water.ph ?? 7.2,
              conductivity_ms_cm: data.water.conductivity_ms_cm ?? 1.4,
              turbidity_ntu: data.water.turbidity_ntu ?? 15.0,
            });
          }
        }
        lastRenderTime = now;
      }
      rafIdRef.current = requestAnimationFrame(updateLoop);
    };

    rafIdRef.current = requestAnimationFrame(updateLoop);

    return () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
      unsubStatus();
      unsubTelemetry();
      unsubAnalytics();
      telemetryWsClient.disconnect();
    };
  }, [missionId]);

  // Recording Timer
  useEffect(() => {
    let timer: number;
    if (isRecording) {
      timer = window.setInterval(() => {
        setRecordSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isRecording]);

  // Handlers
  const handleDriveCommand = useCallback(
    (command: DriveCommand) => {
      setRobotState((prev) => {
        const speed = command === 'IDLE' ? 0 : prev.gear === 'CRAWL' ? 30 : prev.gear === 'CRUISE' ? 65 : 100;
        return { ...prev, command, direction: command, speed };
      });
      if (!isSoundMuted) playSound('click');
    },
    [isSoundMuted]
  );

  const handleToggleLights = useCallback(() => {
    setRobotState((prev) => ({ ...prev, lightsOn: !prev.lightsOn }));
    if (!isSoundMuted) playSound('click');
  }, [isSoundMuted]);

  const handleToggleRecording = useCallback(() => {
    setIsRecording((prev) => !prev);
    if (!isSoundMuted) playSound('click');
  }, [isSoundMuted]);

  const handleTakeSnapshot = useCallback(() => {
    const newSnap: SnapshotItem = {
      id: `SNAP-00${snapshots.length + 1}`,
      imageUrl: 'https://images.unsplash.com/photo-1541888946425-d0fbb186a5b7?auto=format&fit=crop&w=800&q=80',
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
      cameraName: activeCamera.toUpperCase(),
      distanceM: robotState.distanceTraveledM,
      defectCount: defects.length,
    };
    setSnapshots((prev) => [newSnap, ...prev]);
    if (!isSoundMuted) playSound('snapshot');
  }, [snapshots.length, activeCamera, robotState.distanceTraveledM, defects.length, isSoundMuted]);

  const handleDeleteSnapshot = useCallback((id: string) => {
    setSnapshots((prev) => prev.filter((s) => s.id !== id));
  }, []);

  // Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;

      switch (e.key.toLowerCase()) {
        case 'w':
        case 'arrowup':
          handleDriveCommand('FORWARD');
          break;
        case 's':
        case 'arrowdown':
          handleDriveCommand('BACKWARD');
          break;
        case 'a':
        case 'arrowleft':
          handleDriveCommand('LEFT');
          break;
        case 'd':
        case 'arrowright':
          handleDriveCommand('RIGHT');
          break;
        case ' ':
          e.preventDefault();
          handleDriveCommand('IDLE');
          break;
        case 'l':
          handleToggleLights();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleDriveCommand, handleToggleLights]);

  return (
    <div className="min-h-screen bg-[#0d0e0f] text-white flex flex-col font-['Inter'] selection:bg-[#a3e635] selection:text-black">
      {/* Top Bar */}
      <TopNavBar
        robotState={robotState}
        onToggleSound={() => setIsSoundMuted((prev) => !prev)}
        soundEnabled={!isSoundMuted}
        onOpenSettings={() => setIsSettingsModalOpen(true)}
        onOpenGallery={() => setIsSnapshotDrawerOpen(true)}
        snapshotCount={snapshots.length}
      />

      {/* Main Layout Container */}
      <div className="flex flex-1 pt-16 relative">
        {/* Left Sidebar */}
        <SideNavBar
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          robotMode="DeepScan Mode"
        />

        {/* Content Container Offset by Sidebar Width */}
        <main className="flex-1 pl-20 lg:pl-72 p-4 sm:p-6 overflow-y-auto flex flex-col gap-6">
          {/* Telemetry View */}
          {activeTab === 'telemetry' && (
            <div className="flex flex-col gap-6 w-full animate-fade-in">
              {/* Header Bar with Real WebSocket Telemetry Connection Status */}
              <div className="flex flex-wrap items-center justify-between gap-4 bg-[#141619] p-4 rounded-xl border border-white/10 shadow-lg">
                <div className="flex items-center gap-3">
                  <span
                    className={`w-2.5 h-2.5 rounded-full ${
                      wsStatus === 'CONNECTED'
                        ? 'bg-[#a3e635] animate-pulse shadow-[0_0_8px_#a3e635]'
                        : wsStatus === 'CONNECTING' || wsStatus === 'RECONNECTING'
                        ? 'bg-[#ffb4ab] animate-ping'
                        : 'bg-[#ff5449]'
                    }`}
                  />
                  <div>
                    <h2 className="font-['Poppins'] text-lg font-bold tracking-wide uppercase text-white">
                      {activeRobotId} Tactical Inspection Cockpit
                    </h2>
                    <p className="font-['Space_Mono'] text-[10px] text-[#649c96]">
                      Mission: <span className="text-[#5de6ff] font-bold">{missionId}</span> • WS Telemetry:{' '}
                      <span
                        className={`font-bold uppercase ${
                          wsStatus === 'CONNECTED'
                            ? 'text-[#a3e635]'
                            : wsStatus === 'CONNECTING' || wsStatus === 'RECONNECTING'
                            ? 'text-[#ffb4ab]'
                            : 'text-[#ff5449]'
                        }`}
                      >
                        {wsStatus}
                      </span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setActiveTab('defect-analyzer')}
                    className="px-3 py-1.5 rounded-lg bg-[#ff5449]/10 border border-[#ff5449]/30 text-[#ffb4ab] text-xs font-['Space_Mono'] flex items-center gap-2 hover:bg-[#ff5449]/20 transition-all cursor-pointer"
                  >
                    <span>AI Defects ({defects.length})</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('calibration')}
                    className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white/80 text-xs font-['Space_Mono'] hover:bg-white/10 transition-all cursor-pointer"
                  >
                    <span>Diagnostics</span>
                  </button>

                  <button
                    onClick={() => setActiveTab('mission-logs')}
                    className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-white/80 text-xs font-['Space_Mono'] hover:bg-white/10 transition-all cursor-pointer"
                  >
                    <span>Logs</span>
                  </button>

                  <button
                    onClick={() => setIsSnapshotDrawerOpen(true)}
                    className="px-3 py-1.5 rounded-lg bg-[#a3e635]/10 border border-[#a3e635]/30 text-[#ccff80] text-xs font-['Space_Mono'] flex items-center gap-2 hover:bg-[#a3e635]/20 transition-all cursor-pointer"
                  >
                    <span>Snapshots ({snapshots.length})</span>
                  </button>
                </div>
              </div>

              {/* Main Grid: Left Video & Controls / Right Sensors */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Left Column (2 Cols wide) */}
                <div className="lg:col-span-2 flex flex-col gap-6">
                  {/* Camera Feed Component */}
                  <CameraFeed
                    robotState={robotState}
                    activeCamera={activeCamera}
                    onChangeCamera={setActiveCamera}
                    isRecording={isRecording}
                    onToggleRecord={handleToggleRecording}
                    recordSeconds={recordSeconds}
                    onTakeSnapshot={handleTakeSnapshot}
                    defects={defects}
                    onDrive={handleDriveCommand}
                    onStop={() => handleDriveCommand('IDLE')}
                    onToggleLights={handleToggleLights}
                  />

                  {/* Robot Control Console Component */}
                  <ControlConsole
                    robotState={robotState}
                    onDrive={handleDriveCommand}
                    onStop={() => handleDriveCommand('IDLE')}
                    onChangeThrottle={(speed) => setRobotState((prev) => ({ ...prev, speed }))}
                    onChangeGear={(gear) => setRobotState((prev) => ({ ...prev, gear }))}
                  />
                </div>

                {/* Right Column (1 Col wide) */}
                <div className="flex flex-col gap-6">
                  {/* Status Panel Component */}
                  <StatusPanel
                    robotState={robotState}
                    onToggleLights={handleToggleLights}
                    onChangeLightIntensity={setLightIntensity}
                  />

                  {/* Real Water Quality & Pressure Telemetry Panel */}
                  <div className="bg-[#141619] rounded-xl p-4 sm:p-5 flex flex-col gap-3 border border-white/10 shadow-lg">
                    <div className="flex items-center justify-between border-b border-white/10 pb-2">
                      <span className="font-['Space_Mono'] text-xs font-bold text-[#5de6ff] tracking-widest uppercase">
                        REAL TELEMETRY SENSORS
                      </span>
                      <span className="text-[10px] font-['Space_Mono'] text-[#a3e635] font-bold">
                        WS LIVE
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 font-['Space_Mono'] text-xs">
                      <div className="bg-black/40 p-2 rounded border border-white/5 flex flex-col">
                        <span className="text-[10px] text-[#649c96]">Water Temp</span>
                        <span className="text-white font-bold">{waterData.temperature_c.toFixed(1)} °C</span>
                      </div>
                      <div className="bg-black/40 p-2 rounded border border-white/5 flex flex-col">
                        <span className="text-[10px] text-[#649c96]">pH Level</span>
                        <span className="text-white font-bold">{waterData.ph.toFixed(2)}</span>
                      </div>
                      <div className="bg-black/40 p-2 rounded border border-white/5 flex flex-col">
                        <span className="text-[10px] text-[#649c96]">Conductivity</span>
                        <span className="text-white font-bold">{waterData.conductivity_ms_cm.toFixed(1)} mS/cm</span>
                      </div>
                      <div className="bg-black/40 p-2 rounded border border-white/5 flex flex-col">
                        <span className="text-[10px] text-[#649c96]">Turbidity</span>
                        <span className="text-white font-bold">{waterData.turbidity_ntu.toFixed(1)} NTU</span>
                      </div>
                    </div>

                    <div className="mt-1 pt-2 border-t border-white/10 grid grid-cols-3 gap-2 text-center font-['Space_Mono'] text-[11px]">
                      <div className="bg-black/30 p-1.5 rounded">
                        <span className="text-[9px] text-[#649c96] block">Body Pressure</span>
                        <span className="text-[#a3e635] font-bold">{pressureData.body_kpa.toFixed(0)} kPa</span>
                      </div>
                      <div className="bg-black/30 p-1.5 rounded">
                        <span className="text-[9px] text-[#649c96] block">Front Anchor</span>
                        <span className="text-[#5de6ff] font-bold">{pressureData.front_anchor_kpa.toFixed(0)} kPa</span>
                      </div>
                      <div className="bg-black/30 p-1.5 rounded">
                        <span className="text-[9px] text-[#649c96] block">Rear Anchor</span>
                        <span className="text-[#ffb4ab] font-bold">{pressureData.rear_anchor_kpa.toFixed(0)} kPa</span>
                      </div>
                    </div>
                  </div>

                  {/* Gas Sensor Panel Component (CO2 Local Demo Sensor) */}
                  <div>
                    <div className="text-[10px] font-['Space_Mono'] text-[#649c96] mb-1 px-1 flex justify-between items-center">
                      <span>GAS MONITORING</span>
                      <span className="text-amber-400/80 font-bold">(LOCAL DEMO SENSOR)</span>
                    </div>
                    <CO2SensorPanel gasData={sensorData} />
                  </div>

                  {/* IMU Sensor Panel Component */}
                  <MPU6050Panel imuData={imuData} />
                </div>
              </div>
            </div>
          )}

          {/* Network Mapping View */}
          {activeTab === 'network-mapping' && (
            <NetworkMappingView robotState={robotState} />
          )}

          {/* Defect Analyzer View */}
          {activeTab === 'defect-analyzer' && (
            <DefectAnalyzerView
              defects={defects}
              onReturnToTelemetry={() => setActiveTab('telemetry')}
            />
          )}

          {/* Calibration View */}
          {activeTab === 'calibration' && (
            <CalibrationView
              onReturnToTelemetry={() => setActiveTab('telemetry')}
              onCalibrateImu={() => {}}
            />
          )}

          {/* Mission Logs View */}
          {activeTab === 'mission-logs' && (
            <MissionLogsView onReturnToTelemetry={() => setActiveTab('telemetry')} />
          )}

          {/* Help & Shortcuts View */}
          {activeTab === 'help' && (
            <HelpView onReturnToTelemetry={() => setActiveTab('telemetry')} />
          )}
        </main>
      </div>

      {/* Snapshot Drawer Component */}
      <SnapshotDrawer
        isOpen={isSnapshotDrawerOpen}
        onClose={() => setIsSnapshotDrawerOpen(false)}
        snapshots={snapshots}
        onDeleteSnapshot={handleDeleteSnapshot}
      />

      {/* Settings Modal Component */}
      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        onCalibrateImu={() => {}}
      />
    </div>
  );
}