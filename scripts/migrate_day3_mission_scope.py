from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
url = os.getenv("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL is not set in .env")

engine = create_engine(url)

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE telemetry ADD COLUMN IF NOT EXISTS mission_id VARCHAR(64)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_telemetry_mission_id ON telemetry (mission_id)"))
    conn.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_telemetry_mission_id'
            ) THEN
                ALTER TABLE telemetry
                ADD CONSTRAINT fk_telemetry_mission_id
                FOREIGN KEY (mission_id) REFERENCES missions(mission_id);
            END IF;
        END$$;
    """))

print("Mission-scoped telemetry migration complete.")
