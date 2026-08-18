export type RobotConnectionStatus =
  | "connected"
  | "connecting"
  | "disconnected"
  | "error";

export interface RobotState {
  robot_id: string;
  connection: RobotConnectionStatus;
  battery_percent?: number;
  distance_m?: number;
  velocity_mps?: number;
  camera_online?: boolean;
  sensors_online?: boolean;
}