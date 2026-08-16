# PipeVision

AI-powered robotic pipeline inspection, mapping, cleaning and water-quality intelligence platform.

## Day 1 objective

Build the common software contract before connecting the physical robot.

Architecture:

Remote Controller --wired--> Robot
Robot sensors --> MCU --> Robot Gateway --wireless--> PipeVision
Robot camera --> Robot Computer --video--> PipeVision
PipeVision --> AI / Mapping / Water / Cleaning / Digital Twin

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

Open http://127.0.0.1:8000/docs

Simulator:

```bash
python robot/simulator/simulator.py
```
