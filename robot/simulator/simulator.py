import math
import time
from datetime import datetime, timezone
from typing import Any

import requests

API = "http://127.0.0.1:8000"
ROBOT_ID = "PV-SIM-001"


def register() -> None:
    response = requests.post(
        f"{API}/api/v1/robots/register",
        json={
            "robot_id": ROBOT_ID,
            "name": "PipeVision Simulator",
            "firmware_version": "sim-0.2",
            "capabilities": [
                "camera",
                "imu",
                "water_quality",
                "pressure",
                "cleaning",
                "adaptive_morphology",
            ],
        },
        timeout=5,
    )
    response.raise_for_status()


def create_mission() -> str:
    response = requests.post(
        f"{API}/api/v1/missions",
        json={"robot_id": ROBOT_ID, "objective": "INSPECT_AND_CLEAN"},
        timeout=5,
    )
    response.raise_for_status()
    mission_id = response.json()["mission_id"]
    print(f"Started mission {mission_id}")
    return mission_id


def complete_mission(mission_id: str) -> None:
    response = requests.post(f"{API}/api/v1/missions/{mission_id}/complete", timeout=5)
    response.raise_for_status()
    print(f"Completed mission {mission_id}")


def run() -> None:
    register()
    mission_id = create_mission()
    t = 0.0

    try:
        while True:
            distance = max(0.0, 0.15 * t)
            body_diameter = 105 + 15 * math.sin(t / 5)
            payload: dict[str, Any] = {
                "robot_id": ROBOT_ID,
                "mission_id": mission_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "battery_percent": max(0.0, 100 - t * 0.15),
                "distance_m": distance,
                "body_diameter_mm": body_diameter,
                "state": "INSPECTING",
                "imu": {
                    "ax": 0.03 * math.sin(t),
                    "ay": 0.02 * math.cos(t),
                    "az": 9.81,
                    "gx": 0.02,
                    "gy": 0.01,
                    "gz": 0.10 * math.sin(t / 2),
                },
                "pressure": {
                    "body_kpa": 95 + 4 * math.sin(t / 4),
                    "front_anchor_kpa": 175,
                    "rear_anchor_kpa": 170,
                },
                "water": {
                    "temperature_c": 25 + 0.5 * math.sin(t / 7),
                    "ph": 6.9 + 0.08 * math.sin(t / 9),
                    "conductivity_ms_cm": 1.6 + 0.15 * math.sin(t / 6),
                    "turbidity_ntu": 30 + 5 * math.sin(t / 3),
                },
            }
            response = requests.post(f"{API}/api/v1/telemetry", json=payload, timeout=5)
            response.raise_for_status()
            print(
                f"{ROBOT_ID} | {distance:5.2f} m | "
                f"diameter {body_diameter:6.1f} mm | "
                f"battery {payload['battery_percent']:5.1f}% | {mission_id}"
            )
            t += 0.5
            time.sleep(0.5)
    except KeyboardInterrupt:
        complete_mission(mission_id)
        print("Simulator stopped safely.")


if __name__ == "__main__":
    run()
