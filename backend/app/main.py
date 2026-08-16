from fastapi import FastAPI,WebSocket,WebSocketDisconnect
from backend.app.api.robots import router as robots_router
from backend.app.api.telemetry import router as telemetry_router
from backend.app.api.missions import router as missions_router
from backend.app.api.analytics import router as analytics_router
from backend.app.db import init_db
from backend.app.realtime import telemetry_broadcaster
app=FastAPI(title="PipeVision API",version="0.2.0",description="Robot-agnostic pipeline inspection platform.")
@app.on_event("startup")
def startup(): init_db()
app.include_router(robots_router,prefix="/api/v1"); app.include_router(telemetry_router,prefix="/api/v1"); app.include_router(missions_router,prefix="/api/v1"); app.include_router(analytics_router,prefix="/api/v1")
@app.get("/health")
def health(): return {"status":"ok","service":"pipevision-api","version":app.version}
@app.websocket("/ws/telemetry")
async def telemetry_websocket(websocket:WebSocket):
 await telemetry_broadcaster.connect(websocket)
 try:
  while True: await websocket.receive_text()
 except WebSocketDisconnect: telemetry_broadcaster.disconnect(websocket)
 except Exception: telemetry_broadcaster.disconnect(websocket)
