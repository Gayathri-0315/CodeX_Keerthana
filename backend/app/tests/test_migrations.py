"""Migrations must never lose data (SQLite batch copies tables; foreign keys must not cascade)."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def run(code: str, db: Path) -> str:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}", "APP_ENV": "dev", "SEED_DEV_PASSWORD": "x-sample-pass"}
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True, check=True).stdout


def test_upgrading_from_the_first_revision_keeps_child_rows():
    db = Path(tempfile.mkdtemp()) / "m.db"
    run("from alembic import command; from app.migrate import alembic_config as c; command.upgrade(c(), '0002')", db)
    run(
        "from app.db import engine\n"
        "with engine.begin() as c:\n"
        "    c.exec_driver_sql(\"INSERT INTO users (id,name,email,password_hash,role,city,max_distance_km,format_pref,skill_level,"
        "eligibility_tags,interest_text,strict_schedule,show_almost,notif_channels,notif_max_per_week,quiet_hours_start,"
        "quiet_hours_end,onboarded,failed_logins,session_version,created_at) VALUES ('u1','A','a@example.com','x','student','C',20,"
        "'either','beginner','[]','',1,1,'{}',3,'22:00','07:00',1,0,0,'2026-01-01')\")\n"
        "    c.exec_driver_sql(\"INSERT INTO availability_slots (id,user_id,day_of_week,start_min,end_min,recurring,kind,source,created_at)"
        " VALUES ('s1','u1',5,840,1080,1,'free','manual','2026-01-01')\")\n",
        db,
    )
    run("from app.migrate import upgrade; upgrade()", db)
    out = run("from app.db import engine\nwith engine.connect() as c: print(c.exec_driver_sql('SELECT count(*) FROM availability_slots').scalar())", db)
    assert out.strip() == "1"
