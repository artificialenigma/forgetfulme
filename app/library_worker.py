"""Independent local catalog/PDF queue; long scans cannot hold up AI answers."""
import logging
import threading
import time
from app.db import connect
from app.ingestion_policy import enabled


def heartbeat():
    with connect() as db:
        db.execute("INSERT INTO service_status(service) VALUES ('library-worker') ON CONFLICT(service) DO UPDATE SET last_seen=now()")


def heartbeat_loop(stop):
    while not stop.wait(15):
        try:heartbeat()
        except Exception:logging.error('Library heartbeat unavailable')


def cycle(last_scan):
    if not enabled('local_index'):return last_scan
    from app.library import scan
    from app.pdf_extract import process_one
    with connect() as db:
        queued=db.execute("SELECT id FROM library_index_jobs WHERE state='queued' LIMIT 1").fetchone()
    if queued or not last_scan or time.monotonic()-last_scan>60:
        scan();last_scan=time.monotonic()
    process_one()
    return last_scan


def main():
    stop=threading.Event()
    thread=threading.Thread(target=heartbeat_loop,args=(stop,),daemon=True);thread.start()
    last_scan=0
    try:
        while True:
            try:heartbeat();last_scan=cycle(last_scan)
            except Exception:logging.error('Local library cycle failed; will retry')
            time.sleep(5)
    finally:stop.set();thread.join(timeout=2)


if __name__=='__main__':main()
