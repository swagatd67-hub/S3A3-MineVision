"""Baseline Performance Measurement Script for PipeVision Phase 17."""

from __future__ import annotations

import time
import gc
import json

from backend.app.db import SessionLocal, init_db
from backend.app.models import Robot
from backend.app.services.inspection.gateway import InspectionIngestionGateway
from backend.app.services.inspection.models import CanonicalInspectionFrame
from backend.app.services.mission.orchestrator import MissionOrchestrator
from robot.transport.simulator import SimulatorTransport
from robot.gateway.adapter import RobotGatewayAdapter


def get_memory_mb() -> float:
    import os
    import psutil
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


def measure_baseline() -> dict:
    init_db()
    db = SessionLocal()
    try:
        robot = db.get(Robot, "PV-PERF-001")
        if not robot:
            robot = Robot(robot_id="PV-PERF-001", name="Crawler-Perf")
            db.add(robot)
            db.commit()

        orchestrator = MissionOrchestrator()
        mission = orchestrator.create_mission(db, robot_id="PV-PERF-001", mission_id="M-PERF-BASELINE")
        orchestrator.start_mission(db, mission.mission_id)

        # 1. Telemetry Ingestion Rate
        transport = SimulatorTransport(robot_id="PV-PERF-001", mission_id="M-PERF-BASELINE")
        transport.connect()
        adapter = RobotGatewayAdapter(transport=transport, robot_id="PV-PERF-001", mission_id="M-PERF-BASELINE")
        adapter.connect()

        gc.collect()
        mem_start = get_memory_mb()
        t0 = time.perf_counter()
        telemetry_count = 200
        for _ in range(telemetry_count):
            raw = transport.step()
            adapter.ingest_telemetry_payload(raw, db=db)
        t1 = time.perf_counter()

        telemetry_duration = t1 - t0
        telemetry_pps = telemetry_count / telemetry_duration

        # 2. Frame Ingestion Rate (100 synthetic frames)
        gateway = InspectionIngestionGateway()
        frame_latencies: list[float] = []

        for i in range(100):
            pkt = transport.generate_synthetic_frame(frame_index=i, distance_m=i * 0.1)
            frame = CanonicalInspectionFrame(
                mission_id="M-PERF-BASELINE",
                robot_id="PV-PERF-001",
                frame_id=pkt.frame_id,
                frame_index=pkt.frame_index,
                image_bytes=pkt.image_bytes,
                distance_m=pkt.distance_m,
                source="live",
            )
            ft0 = time.perf_counter()
            gateway.ingest_frame(db, frame)
            ft1 = time.perf_counter()
            frame_latencies.append((ft1 - ft0) * 1000.0)

        gc.collect()
        mem_end = get_memory_mb()

        frame_latencies.sort()
        avg_lat = sum(frame_latencies) / len(frame_latencies)
        p95_lat = frame_latencies[int(len(frame_latencies) * 0.95)]
        p99_lat = frame_latencies[int(len(frame_latencies) * 0.99)]
        fps = 100 / (sum(frame_latencies) / 1000.0)

        results = {
            "telemetry_count": telemetry_count,
            "telemetry_duration_s": round(telemetry_duration, 4),
            "telemetry_packets_per_sec": round(telemetry_pps, 2),
            "frame_count": 100,
            "frames_per_sec": round(fps, 2),
            "avg_frame_latency_ms": round(avg_lat, 2),
            "p95_frame_latency_ms": round(p95_lat, 2),
            "p99_frame_latency_ms": round(p99_lat, 2),
            "memory_start_mb": round(mem_start, 2),
            "memory_end_mb": round(mem_end, 2),
            "memory_growth_mb": round(mem_end - mem_start, 2),
        }
        return results
    finally:
        db.close()


if __name__ == "__main__":
    res = measure_baseline()
    print(json.dumps(res, indent=2))
