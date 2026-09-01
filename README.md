# PipeVision

AI-powered robotic pipeline inspection, mapping, cleaning and water-quality intelligence platform.

## Day 1 objective

Build the common software contract before connecting the physical robot.

Architecture:

Remote Controller --wired--> Robot
Robot sensors --> MCU --> Robot Gateway --wireless--> PipeVision
Robot camera --> Robot Computer --video--> PipeVision
PipeVision --> AI / Mapping / Water / Cleaning / Digital Twin

## Run locally (quickstart)

1. Create and activate a virtual environment
   - Windows (PowerShell): `python -m venv .venv` then `.venv\Scripts\Activate.ps1`
   - Windows (cmd): `python -m venv .venv` then `.venv\Scripts\activate`
   - Linux/macOS: `python3 -m venv .venv` then `source .venv/bin/activate`

2. Install dependencies and run the API
```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/docs

## Simulator

Run the local robot simulator:
```bash
python robot/simulator/simulator.py
```

## Notes

- Use Python 3.10+.
- Telemetry is scoped to inspection missions; legacy rows remain null until backfilled.
