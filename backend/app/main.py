from fastapi import FastAPI
from backend.app.api.robots import router as robots_router
from backend.app.api.telemetry import router as telemetry_router
from backend.app.api.missions import router as missions_router

app = FastAPI(title="PipeVision API", version="0.1.0")
app.include_router(robots_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(missions_router, prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "ok", "service": "pipevision-api"}
