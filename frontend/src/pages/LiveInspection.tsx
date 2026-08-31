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
import { getMission } from '../api/missions';
import { sendRobotCommand, sendEmergencyStop } from '../api/robot';
import {
  listFrames,
  createSnapshot,
  listSnapshots,
  deleteSnapshot,
  startRecording,
  stopRecording,
  getRecordingStatus,
} from '../api/video';
import type {
  RobotDriveState,
  DriveCommand,
  SensorData,
  IMUData,
  DefectDetection,
  CameraId,
} from '../types';
import type {
  SnapshotRecord,
  RecordingSession,
} from '../types/video';
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

  // System controls & camera state
  const [activeCamera, setActiveCamera] = useState<CameraId>('cam-01');
  const [isSoundMuted, setIsSoundMuted] = useState(false);
  const [, setLightIntensity] = useState(85);

  // Recording State (Backend Authoritative)
  const [recordingStatus, setRecordingStatus] = useState<
    'IDLE' | 'STARTING' | 'RECORDING' | 'STOPPING' | 'ERROR'
  >('IDLE');
  const [activeRecordingSession, setActiveRecordingSession] = useState<RecordingSession | null>(
    null
  );
  const [recordSeconds, setRecordSeconds] = useState(0);

  // Real Snapshot State
  const [snapshots, setSnapshots] = useState<SnapshotRecord[]>([]);
  const [snapshotsLoading, setSnapshotsLoading] = useState(false);
  const [snapshotsError, setSnapshotsError] = useState<string | null>(null);
  const [snapshotMessage, setSnapshotMessage] = useState<string | null>(null);

  // WebSocket Connection State & Telemetry
  const [wsStatus, setWsStatus] = useState<WebSocketConnectionStatus>('DISCONNECTED');
  const [activeRobotId, setActiveRobotId] = useState<string>('ROV-01');
  const [missionRobotId, setMissionRobotId] = useState<string>('ROV-01');

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

  // Active Key Ref for Deadman Keyup / Deduplication Safety
  const activeKeyRef = useRef<string | null>(null);

  // Determine Real Robot ID from Mission Backend
  useEffect(() => {
    let isMounted = true;
    getMission(missionId)
      .then((m) => {
        if (isMounted && m.robot_id) {
          setMissionRobotId(m.robot_id);
          setActiveRobotId(m.robot_id);
        }
      })
      .catch((err) => {
        console.warn(`Could not resolve robot_id for mission ${missionId}:`, err);
      });
    return () => {
      isMounted = false;
    };
  }, [missionId]);

  // Load Real Backend Snapshots
  const fetchSnapshotsList = useCallback(async () => {
    setSnapshotsLoading(true);
    setSnapshotsError(null);
    try {
      const res = await listSnapshots(missionId);
      setSnapshots(res.snapshots);
    } catch (err: unknown) {
      console.error(`Failed to load snapshots for mission ${missionId}:`, err);
      setSnapshotsError(`Snapshots could not be loaded for mission '${missionId}'.`);
    } finally {
      setSnapshotsLoading(false);
    }
  }, [missionId]);

  useEffect(() => {
    let isMounted = true;
    listSnapshots(missionId)
      .then((res) => {
        if (isMounted) {
          setSnapshots(res.snapshots);
          setSnapshotsError(null);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error(`Failed to load snapshots for mission ${missionId}:`, err);
          setSnapshotsError(`Snapshots could not be loaded for mission '${missionId}'.`);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [missionId]);

  // Load Initial Recording Status from Backend
  useEffect(() => {
    let isMounted = true;
    getRecordingStatus(missionId)
      .then((statusRes) => {
        if (!isMounted) return;
        if (statusRes.is_recording && statusRes.session) {
          setRecordingStatus('RECORDING');
          setActiveRecordingSession(statusRes.session);
          if (statusRes.session.start_time) {
            const startMs = Date.parse(statusRes.session.start_time);
            const elapsed = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
            setRecordSeconds(elapsed);
          }
        } else {
          setRecordingStatus('IDLE');
          setActiveRecordingSession(null);
          setRecordSeconds(0);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error(`Failed to fetch recording status for mission ${missionId}:`, err);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [missionId]);

  // Recording Timer
  useEffect(() => {
    let timer: number;
    if (recordingStatus === 'RECORDING') {
      timer = window.setInterval(() => {
        setRecordSeconds((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [recordingStatus]);

  // Real Recording Toggle Handler
  const handleToggleRecording = useCallback(async () => {
    if (recordingStatus === 'STARTING' || recordingStatus === 'STOPPING') return;

    if (!isSoundMuted) playSound('click');

    if (recordingStatus === 'RECORDING') {
      setRecordingStatus('STOPPING');
      try {
        const session = await stopRecording(
          missionId,
          activeRecordingSession?.recording_id
        );
        setActiveRecordingSession(session);
        setRecordingStatus('IDLE');
      } catch (err) {
        console.error(`Failed to stop recording for ${missionId}:`, err);
        setRecordingStatus('ERROR');
        setTimeout(() => setRecordingStatus('RECORDING'), 2500);
      }
    } else {
      setRecordingStatus('STARTING');
      try {
        const session = await startRecording(missionId, activeCamera);
        setActiveRecordingSession(session);
        setRecordingStatus('RECORDING');
        setRecordSeconds(0);
      } catch (err) {
        console.error(`Failed to start recording for ${missionId}:`, err);
        setRecordingStatus('ERROR');
        setTimeout(() => setRecordingStatus('IDLE'), 2500);
      }
    }
  }, [recordingStatus, missionId, activeRecordingSession, activeCamera, isSoundMuted]);

  // Real Snapshot Creation Handler (Using actual backend frame index)
  const handleTakeSnapshot = useCallback(async () => {
    if (!isSoundMuted) playSound('snapshot');
    setSnapshotMessage(null);

    try {
      const framesRes = await listFrames(missionId, 1);
      if (framesRes.count === 0 || framesRes.frames.length === 0) {
        setSnapshotMessage('No current backend frame available.');
        setTimeout(() => setSnapshotMessage(null), 4500);
        return;
      }

      const latestFrame = framesRes.frames[0];
      const newSnapshot = await createSnapshot(
        missionId,
        latestFrame.frame_index,
        activeCamera,
        `Captured during mission ${missionId}`
      );

      setSnapshots((prev) => [newSnapshot, ...prev]);
      setIsSnapshotDrawerOpen(true);
    } catch (err) {
      console.error(`Failed to create snapshot for ${missionId}:`, err);
      setSnapshotMessage('No current backend frame available.');
      setTimeout(() => setSnapshotMessage(null), 4500);
    }
  }, [missionId, activeCamera, isSoundMuted]);

  // Real Snapshot Deletion Handler
  const handleDeleteSnapshot = useCallback(
    async (snapshotId: string) => {
      try {
        await deleteSnapshot(missionId, snapshotId);
        setSnapshots((prev) => prev.filter((s) => s.snapshot_id !== snapshotId));
      } catch (err) {
        console.error(`Failed to delete snapshot ${snapshotId}:`, err);
      }
    },
    [missionId]
  );

  // Buffer and throttled rendering refs for telemetry
  const latestTelemetryPacketRef = useRef<TelemetryData | null>(null);
  const lastTimestampMsRef = useRef<number>(0);
  const rafIdRef = useRef<number | null>(null);

  // WebSocket telemetry lifecycle
  useEffect(() => {
    lastTimestampMsRef.current = 0;
    latestTelemetryPacketRef.current = null;

    const unsubStatus = telemetryWsClient.onStatusChange((status) => {
      setWsStatus(status);
    });

    const unsubTelemetry = telemetryWsClient.onTelemetry((event) => {
      const packet = event.data;
      if (!packet) return;

      if (packet.mission_id && packet.mission_id !== missionId) {
        return;
      }

      const packetTimeMs = packet.timestamp ? Date.parse(packet.timestamp) : Date.now();
      if (packetTimeMs < lastTimestampMsRef.current) {
        return;
      }
      lastTimestampMsRef.current = packetTimeMs;

      latestTelemetryPacketRef.current = packet;
    });

    const unsubAnalytics = telemetryWsClient.onAnalytics((event) => {
      if (event.mission_id && event.mission_id !== missionId) return;
    });

    telemetryWsClient.connect();

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
              const isEstop = data.state === 'EMERGENCY_STOP';
              updated.emergencyStop = isEstop;
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

  // Real Robot Driving & Command Handlers
  const handleDriveCommand = useCallback(
    async (command: DriveCommand) => {
      if (robotState.emergencyStop) {
        setSnapshotMessage('Robot is in EMERGENCY STOP state. Commands rejected.');
        setTimeout(() => setSnapshotMessage(null), 4000);
        return;
      }

      const targetRobotId = activeRobotId || missionRobotId || 'ROV-01';

      if (command === 'IDLE') {
        try {
          const res = await sendRobotCommand(targetRobotId, { name: 'STOP' }, missionId);
          setRobotState((prev) => ({
            ...prev,
            command: 'IDLE',
            direction: 'IDLE',
            speed: 0,
            isReady: res.controller_state !== 'EMERGENCY_STOP',
          }));
        } catch (err: unknown) {
          console.error('Failed to send STOP command:', err);
          const detail = err instanceof Error ? err.message : 'STOP command failed';
          setSnapshotMessage(`STOP Error: ${detail}`);
          setTimeout(() => setSnapshotMessage(null), 4000);
        }
        return;
      }

      const gearSpeed = robotState.gear === 'CRAWL' ? 0.3 : robotState.gear === 'CRUISE' ? 0.6 : 1.0;
      let linear = 0.0;
      let angular = 0.0;

      if (command === 'FORWARD') linear = gearSpeed;
      else if (command === 'BACKWARD') linear = -gearSpeed;
      else if (command === 'LEFT') angular = -1.0;
      else if (command === 'RIGHT') angular = 1.0;

      try {
        if (!isSoundMuted) playSound('click');
        const res = await sendRobotCommand(
          targetRobotId,
          { name: 'MOVE', arguments: { linear, angular } },
          missionId
        );
        const speedPercent = Math.round(gearSpeed * 100);
        setRobotState((prev) => ({
          ...prev,
          command,
          direction: command,
          speed: speedPercent,
          isReady: res.controller_state !== 'EMERGENCY_STOP',
        }));
      } catch (err: unknown) {
        console.error(`Failed to send MOVE command (${command}):`, err);
        const detail = err instanceof Error ? err.message : `Command ${command} failed`;
        setSnapshotMessage(`Command Error: ${detail}`);
        setTimeout(() => setSnapshotMessage(null), 4000);

        if (detail.includes('EMERGENCY_STOP') || detail.includes('safety')) {
          setRobotState((prev) => ({
            ...prev,
            emergencyStop: true,
            isReady: false,
            speed: 0,
            command: 'IDLE',
          }));
        }
      }
    },
    [robotState.emergencyStop, robotState.gear, activeRobotId, missionRobotId, missionId, isSoundMuted]
  );

  // Real Emergency Stop Handler
  const handleEmergencyStop = useCallback(async () => {
    const targetRobotId = activeRobotId || missionRobotId || 'ROV-01';
    try {
      if (!isSoundMuted) playSound('stop');
      const res = await sendEmergencyStop(targetRobotId, missionId);
      setRobotState((prev) => ({
        ...prev,
        command: 'IDLE',
        direction: 'IDLE',
        speed: 0,
        emergencyStop: true,
        isReady: false,
      }));
      setSnapshotMessage(`EMERGENCY STOP EXECUTED (${res.controller_state})`);
      setTimeout(() => setSnapshotMessage(null), 5000);
    } catch (err: unknown) {
      console.error('Failed to send E-STOP:', err);
      const detail = err instanceof Error ? err.message : 'E-STOP failed';
      setSnapshotMessage(`E-STOP Error: ${detail}`);
      setTimeout(() => setSnapshotMessage(null), 4000);
    }
  }, [activeRobotId, missionRobotId, missionId, isSoundMuted]);

  // Local Lights Toggle
  const handleToggleLights = useCallback(() => {
    setRobotState((prev) => ({ ...prev, lightsOn: !prev.lightsOn }));
    if (!isSoundMuted) playSound('click');
  }, [isSoundMuted]);

  // Keyboard Shortcuts & Deadman Keyup Safety Listener
  useEffect(() => {
    const isEditableElement = (el: HTMLElement | null): boolean => {
      if (!el) return false;
      const tagName = el.tagName?.toUpperCase();
      return (
        tagName === 'INPUT' ||
        tagName === 'TEXTAREA' ||
        tagName === 'SELECT' ||
        el.isContentEditable
      );
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (isEditableElement(e.target as HTMLElement)) return;
      if (e.repeat) return;

      const key = e.key.toLowerCase();

      if (key === ' ') {
        e.preventDefault();
        handleEmergencyStop();
        return;
      }

      if (robotState.emergencyStop) return;

      if (['w', 'arrowup', 's', 'arrowdown', 'a', 'arrowleft', 'd', 'arrowright'].includes(key)) {
        if (activeKeyRef.current === key) return;
        activeKeyRef.current = key;

        if (key === 'w' || key === 'arrowup') {
          handleDriveCommand('FORWARD');
        } else if (key === 's' || key === 'arrowdown') {
          handleDriveCommand('BACKWARD');
        } else if (key === 'a' || key === 'arrowleft') {
          handleDriveCommand('LEFT');
        } else if (key === 'd' || key === 'arrowright') {
          handleDriveCommand('RIGHT');
        }
      } else if (key === 'l') {
        handleToggleLights();
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (isEditableElement(e.target as HTMLElement)) return;

      const key = e.key.toLowerCase();
      if (['w', 'arrowup', 's', 'arrowdown', 'a', 'arrowleft', 'd', 'arrowright'].includes(key)) {
        if (activeKeyRef.current === key || activeKeyRef.current !== null) {
          activeKeyRef.current = null;
          handleDriveCommand('IDLE');
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [handleDriveCommand, handleEmergencyStop, handleToggleLights, robotState.emergencyStop]);

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

      {/* Transient Notification Toast */}
      {snapshotMessage && (
        <div className="fixed top-20 right-6 z-50 bg-[#1f0f11] border border-[#ff5449]/50 text-[#ffb4ab] px-4 py-2 rounded-lg font-['Space_Mono'] text-xs shadow-2xl animate-fade-in flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#ff5449] animate-pulse" />
          <span>{snapshotMessage}</span>
        </div>
      )}

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
                    missionId={missionId}
                    robotState={robotState}
                    activeCamera={activeCamera}
                    onChangeCamera={setActiveCamera}
                    isRecording={recordingStatus === 'RECORDING' || recordingStatus === 'STARTING' || recordingStatus === 'STOPPING'}
                    recordingStatus={recordingStatus}
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
                    onEmergencyStop={handleEmergencyStop}
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
        missionId={missionId}
        snapshots={snapshots}
        loading={snapshotsLoading}
        error={snapshotsError}
        onDeleteSnapshot={handleDeleteSnapshot}
        onRefreshSnapshots={fetchSnapshotsList}
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