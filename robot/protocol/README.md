# PipeVision Robot Protocol v1

Transport-independent contract between any compatible robot and PipeVision.
Robot-specific GPIO, serial formats, motor drivers, valves, and hardware details stay inside the robot firmware/gateway adapter.

Core objects:
- RobotInfo / capabilities
- TelemetryPacket
- RobotPose
- RobotEvent
- RobotCommand
- Mission
