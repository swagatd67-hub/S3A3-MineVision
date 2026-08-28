import React, { useState, useEffect, useCallback } from 'react';
import { CameraId, DefectDetection, GasSensorData, IMUData, RobotDriveState, SnapshotItem } from './types';
import { TopNavBar } from './components/TopNavBar';
import { SideNavBar, ActiveNavTab } from './components/SideNavBar';
import { CameraFeed } from './components/CameraFeed';
import { StatusPanel } from './components/StatusPanel';
import { CO2SensorPanel } from './components/CO2SensorPanel';
import { MPU6050Panel } from './components/MPU6050Panel';
import { ControlConsole } from './components/ControlConsole';
import { NetworkMappingView } from './components/NetworkMappingView';
import { SettingsModal } from './components/SettingsModal';
import { HelpView } from './components/HelpView';
import { sounds } from './utils/audio';

export default function App() {
  // Navigation State
  const [activeTab, setActiveTab] = useState<ActiveNavTab>('telemetry');
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);

  // Active Camera & Recording State
  const [activeCamera, setActiveCamera] = useState<CameraId>('cam-01');
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordSeconds, setRecordSeconds] = useState<number>(0);

  // Robot Drive & Telemetry State
  const [robotState, setRobotState] = useState<RobotDriveState>({
    direction: 'IDLE',
    throttle: 45,
    gear: 'CRUISE',
    speedKmh: 1.6,
    distanceTraveledM: 42.8,
    depthM: 14.2,
    batteryPct: 89,
    voltageV: 24.6,
    isReady: true,
    isConnected: true,
    signalStrengthDbm: -48,
    pingMs: 16,
    lightsOn: true,
    lightIntensity: 85,
    armDeployed: false,
    scanMode: 'DEEPSCAN',
    aiDefectDetection: true,
  });

  // MPU6050 IMU Live Telemetry State
  const [imuData, setImuData] = useState<IMUData>({
    accel: { x: 0.23, y: -0.15, z: 9.72 },
    gyro: { x: 1.35, y: -0.75, z: 2.10 },
    orientation: { roll: 2.4, pitch: -1.1, yaw: 88.5 },
  });

  // CO2 Gas Sensor State (Temperature and Humidity removed)
  const [gasData, setGasData] = useState<GasSensorData>({
    co2Ppm: 412,
    temperatureC: 21.4,
    humidityPct: 84,
    h2sPpm: 0.2,
    ch4Lel: 0,
    status: 'OPTIMAL',
  });

  // Sample AI Defect Detections for conduit inspection
  const [defects] = useState<DefectDetection[]>([
    {
      id: 'def-1',
      type: 'CRACK',
      severity: 'MEDIUM',
      confidence: 0.94,
      x: 42,
      y: 35,
      width: 16,
      height: 18,
      description: 'Longitudinal shear fracture along conduit crown (Clock 11:00)',
    },
    {
      id: 'def-2',
      type: 'CORROSION',
      severity: 'LOW',
      confidence: 0.88,
      x: 62,
      y: 52,
      width: 14,
      height: 15,
      description: 'Surface aggregate exposure with minor oxidation',
    },
  ]);

  // Sound toggle handler
  const handleToggleSound = () => {
    sounds.enabled = !soundEnabled;
    setSoundEnabled(!soundEnabled);
    if (!soundEnabled) {
      sounds.playClick('switch');
    }
  };

  // Robot Drive Handler
  const handleDrive = useCallback((dir: 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT') => {
    setRobotState((prev) => {
      const speed = (prev.throttle / 100) * 3.2;
      return {
        ...prev,
        direction: dir,
        speedKmh: speed,
      };
    });

    sounds.startMotor(robotState.throttle);

    // Dynamic shift to IMU
    setImuData((prev) => {
      let deltaAccelX = 0;
      let deltaAccelY = 0;
      let deltaRoll = 0;
      let deltaPitch = 0;
      let deltaYaw = 0;

      if (dir === 'FORWARD') {
        deltaAccelY = 0.8;
        deltaPitch = -2.2;
      } else if (dir === 'BACKWARD') {
        deltaAccelY = -0.8;
        deltaPitch = 2.2;
      } else if (dir === 'LEFT') {
        deltaAccelX = -0.9;
        deltaRoll = -4.5;
        deltaYaw = -3.0;
      } else if (dir === 'RIGHT') {
        deltaAccelX = 0.9;
        deltaRoll = 4.5;
        deltaYaw = 3.0;
      }

      return {
        accel: {
          x: +(0.23 + deltaAccelX).toFixed(2),
          y: +(-0.15 + deltaAccelY).toFixed(2),
          z: +(9.72 + (Math.random() * 0.1 - 0.05)).toFixed(2),
        },
        gyro: {
          x: +(1.35 + deltaRoll * 0.5).toFixed(2),
          y: +(-0.75 + deltaPitch * 0.5).toFixed(2),
          z: +(2.10 + deltaYaw * 0.4).toFixed(2),
        },
        orientation: {
          roll: +(2.4 + deltaRoll).toFixed(1),
          pitch: +(-1.1 + deltaPitch).toFixed(1),
          yaw: +((prev.orientation.yaw + deltaYaw) % 360).toFixed(1),
        },
      };
    });
  }, [robotState.throttle]);

  // Stop Robot Handler
  const handleStop = useCallback(() => {
    setRobotState((prev) => ({
      ...prev,
      direction: 'IDLE',
      speedKmh: 0,
    }));

    sounds.stopMotor();

    setImuData({
      accel: { x: 0.23, y: -0.15, z: 9.72 },
      gyro: { x: 1.35, y: -0.75, z: 2.10 },
      orientation: { roll: 2.4, pitch: -1.1, yaw: 88.5 },
    });
  }, []);

  // Distance progression & subtle sensor fluctuation ticker
  useEffect(() => {
    const timer = setInterval(() => {
      if (robotState.direction === 'FORWARD') {
        setRobotState((prev) => ({
          ...prev,
          distanceTraveledM: +(prev.distanceTraveledM + (prev.speedKmh / 3.6) * 0.2).toFixed(1),
        }));
      } else if (robotState.direction === 'BACKWARD') {
        setRobotState((prev) => ({
          ...prev,
          distanceTraveledM: Math.max(0, +(prev.distanceTraveledM - (prev.speedKmh / 3.6) * 0.2).toFixed(1)),
        }));
      }

      setGasData((prev) => ({
        ...prev,
        co2Ppm: 412 + Math.floor(Math.sin(Date.now() / 3000) * 3),
      }));

      setRobotState((prev) => ({
        ...prev,
        pingMs: 16 + Math.floor(Math.random() * 4),
      }));
    }, 200);

    return () => clearInterval(timer);
  }, [robotState.direction, robotState.speedKmh]);

  // Video recording timer ticker
  useEffect(() => {
    let recTimer: NodeJS.Timeout;
    if (isRecording) {
      recTimer = setInterval(() => {
        setRecordSeconds((s) => s + 1);
      }, 1000);
    } else {
      setRecordSeconds(0);
    }
    return () => clearInterval(recTimer);
  }, [isRecording]);

  // Keyboard Shortcuts Listener (W/A/S/D, Space for Stop, L for Lights)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      const key = e.key.toLowerCase();

      if (key === 'w' || e.key === 'ArrowUp') {
        e.preventDefault();
        handleDrive('FORWARD');
      } else if (key === 's' && !e.ctrlKey && !e.metaKey && e.code === 'KeyS') {
        e.preventDefault();
        handleDrive('BACKWARD');
      } else if (key === 'a' || e.key === 'ArrowLeft') {
        e.preventDefault();
        handleDrive('LEFT');
      } else if (key === 'd' || e.key === 'ArrowRight') {
        e.preventDefault();
        handleDrive('RIGHT');
      } else if (e.code === 'Space') {
        e.preventDefault();
        sounds.playStopAlert();
        handleStop();
      } else if (key === 'l') {
        e.preventDefault();
        sounds.playClick('light');
        setRobotState((prev) => ({ ...prev, lightsOn: !prev.lightsOn }));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleDrive, handleStop]);

  // Take Snapshot
  const handleTakeSnapshot = () => {
    sounds.playClick('shutter');
  };

  return (
    <div className="min-h-screen bg-[#0d0e10] text-[#e5e2e1] flex flex-col font-['Inter'] selection:bg-[#a3e635] selection:text-[#121f00]">
      
      {/* Top Navigation Bar */}
      <TopNavBar
        robotState={robotState}
        onToggleSound={handleToggleSound}
        soundEnabled={soundEnabled}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Side Navigation Bar */}
      <SideNavBar
        activeTab={activeTab}
        onSelectTab={(tab) => setActiveTab(tab)}
        robotMode={robotState.scanMode}
      />

      {/* Main Content Area */}
      <main 
        id="main-canvas"
        className="flex-1 ml-16 lg:ml-64 mt-16 p-4 sm:p-6 lg:p-7 flex flex-col gap-5 overflow-y-auto"
      >
        {/* Telemetry View (Screenshot 1) */}
        {activeTab === 'telemetry' && (
          <div className="flex flex-col gap-5">
            {/* Top Row: Camera Feed (Left) & Telemetry Column (Right) */}
            <div className="flex flex-col lg:flex-row gap-5">
              {/* Central Live Camera Stream */}
              <CameraFeed
                robotState={robotState}
                activeCamera={activeCamera}
                onChangeCamera={(cam) => setActiveCamera(cam)}
                isRecording={isRecording}
                onToggleRecord={() => setIsRecording(!isRecording)}
                recordSeconds={recordSeconds}
                onTakeSnapshot={handleTakeSnapshot}
                defects={defects}
                onDrive={handleDrive}
                onStop={handleStop}
                onToggleLights={() => {
                  setRobotState((prev) => ({ ...prev, lightsOn: !prev.lightsOn }));
                }}
              />

              {/* Right Telemetry Column */}
              <div className="w-full lg:w-[380px] xl:w-[410px] flex flex-col gap-4 flex-shrink-0">
                {/* Robot Status & Headlights Panel */}
                <StatusPanel
                  robotState={robotState}
                  onToggleLights={() => {
                    setRobotState((prev) => ({ ...prev, lightsOn: !prev.lightsOn }));
                  }}
                />

                {/* CO2 Gas Sensor Panel (Without temp & humidity) */}
                <CO2SensorPanel gasData={gasData} />

                {/* MPU6050 6-Axis IMU Sensor Panel */}
                <MPU6050Panel imuData={imuData} />
              </div>
            </div>

            {/* Bottom Row: Robot Control Console */}
            <ControlConsole
              robotState={robotState}
              onDrive={handleDrive}
              onStop={handleStop}
            />
          </div>
        )}

        {/* Network Mapping View (Screenshot 2) */}
        {activeTab === 'network-mapping' && (
          <NetworkMappingView robotState={robotState} />
        )}

        {/* Help & Documentation View */}
        {activeTab === 'help' && (
          <HelpView
            onReturnToTelemetry={() => setActiveTab('telemetry')}
          />
        )}
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onCalibrateImu={() => {
          setImuData({
            accel: { x: 0.0, y: 0.0, z: 9.81 },
            gyro: { x: 0.0, y: 0.0, z: 0.0 },
            orientation: { roll: 0.0, pitch: 0.0, yaw: 0.0 },
          });
        }}
      />

    </div>
  );
}
