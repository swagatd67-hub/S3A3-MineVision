# Day 2 — PostgreSQL + real-time telemetry

1. Create PostgreSQL database `pipevision`.
2. Copy `.env.example` to `.env` and set `DATABASE_URL`.
3. Start FastAPI; the current sprint uses SQLAlchemy `create_all()` for the initial schema.
4. POST `/api/v1/telemetry` persists packets and broadcasts them on `ws://127.0.0.1:8000/ws/telemetry`.
5. GET `/api/v1/telemetry/{robot_id}` reads the latest 100 rows.
