import { useState, useEffect, useCallback } from 'react';
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

import type {
  RobotDriveState,
  DriveCommand,
  SensorData,
  IMUData,
  DefectDetection,
  SnapshotItem,
  CameraId,
} from '../types';

export default function LiveInspection() {
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

  // Sensor Data
  const [sensorData] = useState<SensorData>(() => ({
    co2Ppm: 420,
    co2BaselinePpm: 400,
    status: 'NORMAL',
    timestampMs: Date.now(),
    historyPpm: [410, 412, 415, 418, 419, 422, 420],
  }));

  // IMU Data
  const [imuData] = useState<IMUData>({
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
              {/* Header Bar */}
              <div className="flex flex-wrap items-center justify-between gap-4 bg-[#141619] p-4 rounded-xl border border-white/10 shadow-lg">
                <div className="flex items-center gap-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#a3e635] animate-pulse shadow-[0_0_8px_#a3e635]" />
                  <h2 className="font-['Poppins'] text-lg font-bold tracking-wide uppercase text-white">
                    ROV-01 Tactical Inspection Cockpit
                  </h2>
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

                  {/* Gas Sensor Panel Component */}
                  <CO2SensorPanel gasData={sensorData} />

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