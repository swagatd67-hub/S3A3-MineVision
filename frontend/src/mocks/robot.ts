import type { RobotState } from "../types/robot";

export const mockRobot: RobotState = {
  robot_id: "robot-01",
  connection: "connected",
  battery_percent: 68,
  distance_m: 126.4,
  velocity_mps: 0.14,
  camera_online: true,
  sensors_online: true,
};