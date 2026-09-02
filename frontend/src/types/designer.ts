export type DriveCommand = 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT' | 'IDLE';
export type GearMode = 'CRAWL' | 'CRUISE' | 'TURBO';
export type CameraId = 'cam-01' | 'cam-02' | 'cam-03' | 'thermal';

export interface RobotDriveState {
  command: DriveCommand;
  direction?: DriveCommand;
  speed: number;
  maxSpeed: number;
  gear: GearMode;
  lightsOn: boolean;
  isReady?: boolean;
  tetherLengthM: number;
  distanceTraveledM: number | null;
  batteryPercent: number | null;
  isArmed: boolean;
  emergencyStop: boolean;
}

export interface GenericGasSensorData {
  value: number;
  status: 'NORMAL' | 'ELEVATED' | 'HIGH' | 'CRITICAL';
  timestampMs?: number;
  history?: number[];
  // Legacy optional fields for backward compatibility
  co2Ppm?: number;
  co2BaselinePpm?: number;
  historyPpm?: number[];
}

export type SensorData = GenericGasSensorData;
export type GasSensorData = GenericGasSensorData;


export interface IMUPoint {
  x: number;
  y: number;
  z: number;
}

export interface IMUData {
  accel: IMUPoint;
  accelX: number;
  accelY: number;
  accelZ: number;
  gyro: IMUPoint;
  gyroX: number;
  gyroY: number;
  gyroZ: number;
  pitchDeg: number;
  rollDeg: number;
  yawDeg: number;
  orientation: {
    pitch: number;
    roll: number;
    yaw: number;
  };
  historyAccel: IMUPoint[];
}

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DefectDetection {
  id: string;
  type: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  confidence: number;
  distanceM: number;
  clockPosition?: string;
  bounding: BoundingBox;
  description?: string;
}

export interface SnapshotItem {
  id: string;
  imageUrl: string;
  thumbnail?: string;
  timestamp: string;
  cameraName: string;
  camera?: string;
  distanceM: number;
  distance?: number;
  defectCount: number;
}
