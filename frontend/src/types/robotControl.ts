export type RobotCommandName =
  | 'MOVE'
  | 'STOP'
  | 'EMERGENCY_STOP'
  | 'CAMERA_PAN';

export interface MoveCommandPayload {
  linear: number;
  angular: number;
}

export interface CameraPanCommandPayload {
  angle_deg: number;
}

export type RobotCommandPayload =
  | { name: 'MOVE'; arguments: MoveCommandPayload }
  | { name: 'STOP'; arguments?: Record<string, unknown> }
  | { name: 'EMERGENCY_STOP'; arguments?: Record<string, unknown> }
  | { name: 'CAMERA_PAN'; arguments: CameraPanCommandPayload };

export interface RobotCommandResponse {
  robot_id: string;
  command: string;
  status: 'accepted' | 'rejected';
  controller_state: string;
  timestamp: string;
}

export interface RobotControlError {
  message: string;
  statusCode?: number;
  details?: string;
}
