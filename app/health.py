"""Check that a background service is actually making progress."""
import sys
from app.db import connect

with connect() as db:
    row = db.execute(
        "SELECT last_seen > now() - interval '90 seconds' AS healthy FROM service_status WHERE service=%s",
        (sys.argv[1],),
    ).fetchone()
if not row or not row["healthy"]:
    raise SystemExit(1)
