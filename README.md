# Forgetful Me

A self-hosted browsing archive that will collect history from Chrome and Safari and export it to Obsidian.

The initial Docker foundation includes Caddy, PostgreSQL, a Python/FastAPI webapp, a background worker, a scheduler, and scheduled backups. The dashboard shows service summary cards, database connectivity, service heartbeats, and the latest eight maintenance jobs, with timestamps in Maldives time and a responsive layout. Use Refresh to fetch current data. Browser ingestion, history search, and Obsidian delivery are not implemented yet.

## Run locally

Install and start Docker Desktop (or Docker Engine with Compose), then run:

```sh
python3 scripts/setup.py
docker compose up -d --build --wait
```

Open [localhost:8080](http://localhost:8080). Sign in with `ADMIN_USER` and `ADMIN_PASSWORD` from your local `.env`. Setup generates random passwords, excludes `.env` from Git and the Docker build, and refuses to overwrite existing settings. Only the proxy publishes ports; local bindings default to `127.0.0.1`.

Local `SITE_ADDRESS=:80` accepts both `localhost` and `127.0.0.1`. Use HTTP on port 8080 for local testing. The mapped port 8443 does not serve HTTPS until a TLS site is configured. Opening `/` redirects to a normal login page; `/health/ready` should return `{"status":"ready"}` without authentication. Browser sessions expire after eight hours and use signed HttpOnly/SameSite cookies, with Secure enabled behind HTTPS. Login forms have CSRF protection. Basic authentication remains available for API checks.

```sh
docker compose ps
docker compose logs --tail=100 web worker scheduler backup
python3 scripts/smoke_test.py
docker compose down
```

`down` preserves named volumes. `down -v` deletes database and content volumes and should only be used when deliberately resetting the archive.

## Storage and background jobs

PostgreSQL persists in `postgres_data`; captured-content storage is reserved in `content_data`. Caddy certificates and configuration have their own volumes. A one-shot migration service initializes the schema before application services start. The scheduler enqueues a maintenance job every minute; the worker processes it transactionally and removes completed jobs older than seven days. Both publish heartbeats. This is a functioning queue foundation, not a page-extraction or export implementation.

The database-backed queue does not need Redis. Additional job types and schema migrations will be introduced with browser collection and exports. Python dependencies are pinned in `requirements.lock`, with direct dependency ranges in `requirements.txt`. Container tags track supported major versions rather than immutable digests.

## Backups and restore

The backup service creates a PostgreSQL custom-format dump and compressed content archive at startup and every 24 hours. Completed backups are written to `./backups/<UTC timestamp>/`; partial backups are not published. The default retention is 14 days. Failures retry after 60 seconds. Dump readability is checked during backup, and the smoke test performs an actual restore into a disposable database.

Copy backups to a separate device or storage service: backups on the same server do not protect against losing that server. Database and file captures are sequential; once content writes are implemented, coordinated snapshots will be needed for strict cross-storage consistency.

For a database recovery, stop writers and choose a verified backup directory:

```sh
docker compose stop web worker scheduler
# Replace TIMESTAMP with the chosen directory. This replaces database contents.
docker compose exec backup pg_restore --exit-on-error --clean --if-exists --no-owner --dbname=forgetfulme /backups/TIMESTAMP/database.dump
# Restore captured files into the volume through the worker image.
docker compose run --rm --no-deps --user root -v ./backups:/restore:ro worker sh -c 'tar -xzf /restore/TIMESTAMP/content.tar.gz -C /data/content && chown -R app:app /data/content'
docker compose start web worker scheduler
```

Restore into empty content storage for an exact recovery; extracting an archive alone does not remove newer files. Keep a pre-recovery backup. Migration to another machine requires the database and content backups plus `.env`, not just the Git checkout.

## Move to a server

On the server, copy the project and private `.env`, restore the data, and set:

```dotenv
BIND_ADDRESS=0.0.0.0
HTTP_PORT=80
HTTPS_PORT=443
SITE_ADDRESS=history.example.com
```

Point the domain at the server and permit inbound TCP 80/443. Caddy obtains HTTPS certificates for the configured domain. Use strong private credentials; authentication is intended for this single-user foundation and must be used over HTTPS outside localhost. Device-specific API credentials will be added before extensions connect. No CORS policy for extensions is configured yet.

Changing `POSTGRES_PASSWORD` in `.env` does not change the password in an existing PostgreSQL volume; rotate it in the database as well. Do not expose the database directly.

## Project documentation

- [Project plan](PLAN.md) — decisions and open questions.
- [Conversation and worklog](WORKLOG.md) — discussions and completed work.
