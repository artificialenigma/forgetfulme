# Forgetful Me

A self-hosted browsing archive that will collect history from Chrome and Safari and export it to Obsidian.

The initial Docker foundation includes Caddy, PostgreSQL, a Python/FastAPI webapp, a background worker, a scheduler, and scheduled backups. The dashboard shows service summary cards, database connectivity, service heartbeats, and the latest eight maintenance jobs, with timestamps in Maldives time and a responsive layout. Use Refresh to fetch current data. Browser ingestion, Safari/CSV/JSON import, paginated history, automatic visit indexes and public-page Markdown capture are implemented. Full-text history search remains planned.

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
python3 scripts/vault_smoke_test.py
docker compose down
```

`down` preserves named volumes. `down -v` deletes database and content volumes and should only be used when deliberately resetting the archive.

## Obsidian inside Forgetful Me

Open the dashboard's **Obsidian vault** link, or visit [the vault workspace](http://localhost:8080/vault). Obsidian runs in a LinuxServer container and streams its desktop through `/obsidian/`, embedded in the app. The app login protects the desktop HTTP routes and WebSocket upgrades; the Obsidian container publishes no host ports. Localhost works for local testing; remote access requires HTTPS because the desktop uses browser secure-context features. This is a containerized desktop, not an official Obsidian web edition. See [LinuxServer's image documentation](https://docs.linuxserver.io/images/docker-obsidian/).

The new **Forgetful Me** vault lives at `/vault` in the `obsidian_vault` named volume. It includes a welcome note and is registered for opening on first start. Settings persist in `obsidian_config`. Your existing macOS vault is not mounted, copied, or changed. Obsidian and the worker share the new vault; the webapp mounts it read-only. Automatic browsing-history exports remain future work.

Both the vault and Obsidian settings are included in scheduled backups as `vault.tar.gz` and `obsidian-config.tar.gz`. They must be restored along with the database/content archives when moving servers. For consistent recovery, stop Obsidian and other writers before restoring, then extract each archive into its corresponding empty volume and retain UID/GID 10001 ownership. Live backups are sequential rather than atomic; stop writers before a final migration backup. `docker compose down -v` deletes the vault and settings as well as database/content volumes.

The streamed desktop is shared by this single-user stack. Do not treat it as a separate per-user vault. Desktop hardening is enabled, and the container has no Docker socket, host vault, or privileged host access. An authenticated user still has access to the container desktop and its new vault.

## Storage and background jobs

PostgreSQL persists in `postgres_data`; captured-content storage is reserved in `content_data`. Caddy certificates and configuration have their own volumes. A one-shot migration service initializes the schema before application services start. The scheduler enqueues a maintenance job every minute; the worker processes it transactionally and removes completed jobs older than seven days. Both publish heartbeats. This is a functioning queue foundation, not a page-extraction or export implementation.

The database-backed queue does not need Redis. Additional job types and schema migrations will be introduced with browser collection and exports. Python dependencies are pinned in `requirements.lock`, with direct dependency ranges in `requirements.txt`. Container tags track supported major versions rather than immutable digests.

## Backups and restore

The backup service creates a PostgreSQL custom-format dump and compressed content, vault, and Obsidian settings archives at startup and every 24 hours. Completed backups are written to `./backups/<UTC timestamp>/`; partial backups are not published. The default retention is 14 days. Failures retry after 60 seconds. Dump readability is checked during backup, and the smoke test performs an actual restore into a disposable database.

Copy backups to a separate device or storage service: backups on the same server do not protect against losing that server. Database and file captures are sequential; once content writes are implemented, coordinated snapshots will be needed for strict cross-storage consistency.

For a database recovery, stop writers and choose a verified backup directory:

```sh
docker compose stop obsidian web worker scheduler
# Replace TIMESTAMP with the chosen directory. This replaces database contents.
docker compose exec backup pg_restore --exit-on-error --clean --if-exists --no-owner --dbname=forgetfulme /backups/TIMESTAMP/database.dump
# Restore captured files into the volume through the worker image.
docker compose run --rm --no-deps --user root -v ./backups:/restore:ro worker sh -c 'tar -xzf /restore/TIMESTAMP/content.tar.gz -C /data/content && chown -R app:app /data/content'
docker compose start obsidian web worker scheduler
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

## Optional Archive Desk service

Archive Desk, from the sibling `internetarchivemanager` project, exports accessible Internet Archive/HathiTrust reader pages to PDF or image ZIP, including available OCR. It is a book-export companion, not a general webpage scraper. Its original source remains unchanged and retains its GPL-3.0 license.

Keep that checkout beside this project, or set `ARCHIVE_DESK_PATH` to its path. Start it with:

```sh
docker compose -f compose.yaml -f compose.archive.yaml --profile archive up -d --build --wait
python3 scripts/archive_smoke_test.py
```

Open [Archive Desk](http://localhost:8766) and its [login browser](http://localhost:6080/vnc.html). Sign in and, where required, borrow the book in that dedicated browser. Access checks in Archive Desk remain intact. Your regular browser's login is separate.

Both added ports always bind to loopback. The browser view has no separate password; do not expose it on a server. The existing application accepts local HTTP hosts only and has its own app token rather than Forgetful Me login. Shared remote access therefore needs an authenticated gateway, host/origin adjustments, and WebSocket routing before deployment.

`ARCHIVE_HTTP_PORT` and `ARCHIVE_BROWSER_PORT` can change the local ports if occupied. The service has a separate network with internet access and no connection to Forgetful Me's database network. Browser profile and exports persist in the new `archive_state` volume; existing standalone Archive Desk data is not imported. Its in-memory queue does not survive restarts, although completed files remain on disk. This volume is not included in Forgetful Me's existing backup job; back it up separately, treating the saved browser profile as credentials.

Use the same two `-f` arguments and `--profile archive` for subsequent Compose management of this companion. Server relocation requires its source checkout or a published image, plus its separate state backup. This first integration adds service lifecycle management only; shared archive records, dashboard export controls, and Obsidian attachment delivery remain future work.

## Optional MinerU document processing

`compose.mineru.yaml` is a deployment template for MinerU's V1 parsing API on a Linux server with a supported NVIDIA GPU and NVIDIA Container Toolkit. It is not running on this ARM64 Mac. The current [official Docker guide](https://opendatalab.github.io/MinerU/quick_start/docker_deployment/) targets NVIDIA; non-NVIDIA Docker guidance for MinerU 4 is still pending. Apple Silicon acceleration requires a native macOS installation, rather than this GPU container.

MinerU can convert PDFs, scanned pages, and supported documents into Markdown/structured results. Its proposed role is **Archive Desk PDF or uploaded document → MinerU → reviewed Markdown/assets → Obsidian vault**. Its API is not a general URL crawler.

On a compatible server, build the image from the upstream checkout following the official guide, verify the installed version, and set `MINERU_IMAGE` to your built/versioned image tag. The default `mineru:4` refers to a locally built image; this project does not provide it. Then enable the optional profile:

```sh
docker compose -f compose.yaml -f compose.mineru.yaml --profile mineru config --quiet
docker compose -f compose.yaml -f compose.mineru.yaml --profile mineru up -d --wait
```

Add `-f compose.archive.yaml --profile archive` as well to manage Archive Desk in the same invocation. `MINERU_GPU_ID` selects the NVIDIA device; `MINERU_SHM_SIZE` defaults to 32 GB, so provision memory appropriately. Upstream image builds download models and use a CUDA/vLLM runtime that must match the server's GPU and driver. Model-file checks do not replace a real document parsing acceptance test.

The API has no published host port. It uses a separate internal network joined by the worker, with the internal endpoint `http://mineru:8000/v1/health`. Captured files are available read-only at `/input`; `/workspace` has a separate persistent volume. The parser does not mount the Obsidian vault or the database. Pre-downloaded local models are required because this network has no internet egress. The worker's endpoint setting is prepared, but submission/polling, result downloads, and vault writing are not implemented yet. MinerU workspace files are not included in the current backup job; canonical exports should be stored through the worker in backed-up content/vault storage when that integration is built.

Only Compose configuration was validated here. Image build, GPU inference, parsing quality, and end-to-end Obsidian export must be validated on compatible hardware. For local testing, a native macOS MinerU service or a separately tested CPU-only container is an alternative still to be selected.

## Project documentation

- [Project plan](PLAN.md) — decisions and open questions.
- [Conversation and worklog](WORKLOG.md) — discussions and completed work.

### Browser add-ons

Chrome collection and a Safari source package are now available. See [installation and privacy instructions](extensions/README.md). Sign in, create a token in **Browser devices**, load `extensions/chrome` as an unpacked extension, and configure it. New visits appear in **Browsing history**. Chrome optionally imports the last 30 days; Safari captures new tab loads and requires Xcode packaging. Safari packaging is currently blocked by the unaccepted local Xcode license. Automatic Obsidian export remains planned.

### Import browsing data files

Open **Import history** from the dashboard or Devices page. Upload a UTF-8 `.csv` or `.json` file with `url`, `visited_at`, and optional `title`. CSV uses a header row; JSON accepts an array or `{"visits": [...]}`. Dates must be ISO 8601 with a timezone, for example `2026-01-01T12:00:00Z`. See [CSV example](examples/history.csv) and [JSON example](examples/history.json).

Use the same source name for files from the same browser: identical URL/timestamp pairs are skipped, including equivalent timezone offsets. The importer validates the whole file before saving, limits uploads to 100 MiB and 1,000,000 rows, and reports imported/duplicate counts. It does not open browser databases or accept arbitrary vendor export schemas; convert those to the documented fields, or use the Chrome add-on’s history import. File imports and extension capture have separate event identities, so overlapping data can appear twice. Imported sources cannot authenticate browser ingestion. Verify with `python3 scripts/import_smoke_test.py` against the running stack.

Safari history JSON exports are also accepted: `metadata.browser_name="Safari"`, `metadata.data_type="history"`, `metadata.schema_version=1`, and a `history` array of entries with `url`, integer `time_usec`, and optional `title`. Upload the extracted JSON file rather than the ZIP. Safari timestamps are Unix microseconds; exact precision is retained for deduplication. Each entry becomes one stored visit; aggregate `visit_count`, load-failure flags and redirect metadata are not stored or expanded into additional visits. See [Safari example](examples/safari-history.json) and [Apple’s export schema](https://developer.apple.com/documentation/SafariServices/importing-data-exported-from-safari).

Safari exports can contain entries that the archive cannot accept, such as non-HTTP(S) pages or invalid timestamps. The import form defaults to **Skip unsupported or invalid Safari entries and report them**: valid entries are saved, and the result shows the skipped count and first 20 entry numbers/reasons without displaying their URLs. Uncheck the option to reject the entire file on any invalid entry. CSV/generic JSON imports remain strict. An export with no valid entries saves nothing.

Browsing history now uses a responsive page with 50 entries per page, previous/next navigation, bounded titles and URLs, and Maldives timestamps (UTC+05:00). This replaces the earlier latest-200-only view. Hover over shortened text for the full value.

### Automatic Obsidian delivery

The worker now exports existing and newly collected/imported history to `Forgetful Me/Browsing History/YYYY/MM` in the shared vault. Each managed Markdown file groups a day’s visits in chunks of at most 1,000 and includes links, titles, times and sources. The worker processes bounded batches every ten seconds; a large backlog takes time. Refresh Browsing history to see exported/pending counts, then open the Obsidian vault from the app. Managed notes may be rebuilt on new data/retry; keep annotations in separate notes. Exported content is visit metadata, not scraped page bodies. Database and vault backups already cover this data.

### Page content capture

The worker now queues every distinct imported/collected URL (fragments removed) and captures readable public HTML or plain text into `Forgetful Me/Pages/<URL hash>.md`. Existing history is queued at migration. Source URL and fetch timestamp appear in each note. The earlier Browsing History files remain visit indexes; page content is stored separately. Open **Page scraping status** from Browsing history to see counts, blocked/failed reasons and retry failed pages.

The worker attempts one page per ten-second cycle, follows up to five redirects, checks robots rules, pins connections to validated public IPs with TLS hostname verification, limits fetched pages to 5 MiB and does not use browser cookies. Local/private addresses and nonstandard ports are excluded. Temporary failures retry up to three attempts. Login-only, JavaScript-only, robots-blocked, unavailable or non-HTML/text pages are reported rather than marked captured. PDFs are not sent to MinerU yet. Notes capture the current server-visible page; they cannot reconstruct its contents at the historical visit time. Images and browser session data are not captured. Managed page notes can be rebuilt on retries; keep annotations separately. The content request necessarily sends the URL, including its query, to the target website. The worker has an explicit egress network; other backend services remain on the internal network.

Extraction uses pinned [Trafilatura](https://trafilatura.readthedocs.io/en/latest/extraction-overview.html) with Markdown output, formatting and readable-content filtering. Verify isolated extraction/network-boundary behavior with `docker compose exec -T worker python - < scripts/page_scraper_test.py`.
