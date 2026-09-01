# PipeVision — Development Setup

> All instructions assume you are working from the **repository root**
> (`Pipevision/`).

---

## 1. Python virtual-environment

```bash
# Create a venv (only once)
python -m venv .venv

# Activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

---

## 2. Backend dependencies

```bash
pip install -r backend/requirements.txt
```

This installs: FastAPI, Uvicorn, Pydantic, SQLAlchemy, psycopg,
python-dotenv, pytest, ruff, httpx, websocket-client, python-multipart.

---

## 3. ML / Training dependencies

```bash
# Step 1 — Install PyTorch + TorchVision for your CUDA version.
# The line below targets CUDA 12.6 (verified on the current dev machine).
pip install torch==2.9.1+cu126 torchvision==0.24.1+cu126 \
    --index-url https://download.pytorch.org/whl/cu126

# Step 2 — Install the remaining ML packages.
pip install -r requirements-ml.txt
```

> **CPU-only machines:** replace the `--index-url` argument with the
> appropriate URL from <https://pytorch.org/get-started/locally/>.

This installs: opencv-python, Pillow, scikit-learn, numpy, ultralytics
(YOLO object detection).

---

## 4. Frontend (Node / npm)

```bash
cd frontend
npm install
npm run build        # TypeScript + Vite production build
npm run lint         # ESLint
cd ..
```

> **Note:** Frontend dependencies are declared in `frontend/package.json`
> and should **not** be modified without team review.

---

## 5. Verify torch / CUDA

```bash
python -c "import torch; print('torch', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

Expected output on a CUDA-capable machine:

```
torch 2.8.0+cu126
CUDA available: True
GPU: NVIDIA GeForce RTX …
```

---

## 6. Quick import smoke-test

```bash
# Backend core
python -c "import fastapi, uvicorn, pydantic, sqlalchemy, psycopg, dotenv; print('backend OK')"

# ML stack
python -c "import torch, torchvision, cv2, PIL, numpy, sklearn, ultralytics; print('ml OK')"
```

---

## 7. Running the backend server (development)

```bash
uvicorn backend.app.main:app --reload --port 8000
```

---

## 8. Running backend tests

```bash
pytest backend/tests/
```

---

## 9. Physical robot note

The PipeVision physical robot (and its Ethernet/serial connection) is
**not required** for software development. The repository includes a
software simulator at `robot/simulator/simulator.py` that sends
synthetic telemetry to the API. Start the backend first, then:

```bash
python robot/simulator/simulator.py
```

The simulator requires `requests` (`pip install requests`), which is
**not** listed in the main requirements files because it is only needed
by the standalone simulator script.

---

## File overview

| File | Purpose |
|------|---------|
| `backend/requirements.txt` | Backend runtime + dev/test deps |
| `requirements-ml.txt` | ML, training, computer-vision deps |
| `frontend/package.json` | Frontend (React + Vite) deps |
