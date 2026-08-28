export type CameraId = 'cam-01' | 'cam-02' | 'cam-03' | 'thermal';

export type IMUData = {
  accel: { x: number; y: number; z: number };
  gyro: { x: number; y: number; z: number };
  orientation: { roll: number; pitch: number; yaw: number };
};

export type GasSensorData = {
  co2Ppm: number;
  temperatureC: number;
  humidityPct: number;
  h2sPpm: number;
  ch4Lel: number;
  status: 'OPTIMAL' | 'WARNING' | 'CRITICAL';
};

export type RobotDriveState = {
  direction: 'IDLE' | 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT';
  throttle: number; // 0 to 100
  gear: 'CRAWL' | 'CRUISE' | 'TURBO';
  speedKmh: number;
  distanceTraveledM: number;
  depthM: number;
  batteryPct: number;
  voltageV: number;
  isReady: boolean;
  isConnected: boolean;
  signalStrengthDbm: number;
  pingMs: number;
  lightsOn: boolean;
  lightIntensity: number; // 0 to 100
  armDeployed: boolean;
  scanMode: 'DEEPSCAN' | 'MANUAL' | 'AUTO_CENTER' | 'MAPPING';
  aiDefectDetection: boolean;
};

export type DefectDetection = {
  id: string;
  type: 'CRACK' | 'CORROSION' | 'ROOT_INTRUSION' | 'JOINT_OFFSET' | 'SEDIMENT';
  severity: 'LOW' | 'MEDIUM' | 'HIGH';
  confidence: number;
  x: number; // percentage
  y: number; // percentage
  width: number;
  height: number;
  description: string;
};

export type SnapshotItem = {
  id: string;
  timestamp: string;
  camera: string;
  distance: string;
  defectCount: number;
  thumbnail: string;
};
