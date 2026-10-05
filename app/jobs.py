import logging
import sys
import time
from app.db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def tick(role):
    with connect() as db:
        db.execute("INSERT INTO service_status(service) VALUES (%s) ON CONFLICT(service) DO UPDATE SET last_seen=now()", (role,))
        if role == "scheduler":
            # Transaction-scoped lock makes scheduling safe if accidentally duplicated.
            db.execute("SELECT pg_advisory_xact_lock(418240)")
            db.execute("INSERT INTO jobs(kind) SELECT 'maintenance' WHERE NOT EXISTS (SELECT 1 FROM jobs WHERE kind='maintenance' AND created_at > now() - interval '60 seconds')")
        else:
            job = db.execute("SELECT id FROM jobs WHERE completed_at IS NULL ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if job:
                db.execute("DELETE FROM jobs WHERE completed_at < now() - interval '7 days'")
                db.execute("UPDATE jobs SET completed_at=now() WHERE id=%s", (job['id'],))
                logging.info("Completed maintenance job %s", job['id'])


if __name__ == "__main__":
    role = sys.argv[1]
    if role not in {"worker", "scheduler"}:
        raise SystemExit("Expected worker or scheduler")
    while True:
        try:
            tick(role)
            if role == "worker":
                from app.obsidian_export import export_pending
                count = export_pending()
                if count:
                    logging.info("Exported %s visits to Obsidian", count)
                from app.page_scraper import process_page
                process_page()
        except Exception:
            logging.exception("Job loop failed; retrying")
        time.sleep(10)
