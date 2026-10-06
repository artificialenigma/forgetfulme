"""Separate local AI queue; page capture continues independently."""
import logging
import time
from app.db import connect
from app.wiki import refresh_sources, rebuild_indexes, synthesize_one, answer_one


def heartbeat():
    with connect() as db:
        db.execute("INSERT INTO service_status(service) VALUES ('wiki-worker') ON CONFLICT(service) DO UPDATE SET last_seen=now()")


def main():
    indexed_at = 0
    while True:
        try:
            heartbeat()
            refresh_sources()
            if time.monotonic() - indexed_at > 60:
                rebuild_indexes()
                indexed_at = time.monotonic()
            heartbeat()
            if not answer_one():
                synthesize_one()
            heartbeat()
        except Exception:
            # Never include source text, browsing URLs, credentials or model output.
            logging.error('Wiki cycle failed; will retry')
        time.sleep(5)


if __name__ == '__main__':
    main()
