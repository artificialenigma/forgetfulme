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

The worker attempts one page per ten-second cycle, follows up to five redirects, checks robots rules, pins connections to validated public IPs with TLS hostname verification, limits fetched pages to 5 MiB and does not use browser cookies. Local/private addresses and nonstandard ports are excluded. Temporary failures retry up to three attempts. Login-only, JavaScript-only, robots-blocked, unavailable or non-HTML/text pages are reported rather than marked captured. PDFs are not sent to MinerU yet. Notes capture the current server-visible page; they cannot reconstruct its contents at the historical visit time. Images and browser session data are not captured. Changed recaptures create a new immutable capture file; unchanged extracted content reuses its existing revision. Keep annotations separately. The content request necessarily sends the URL, including its query, to the target website. The worker has an explicit egress network; other backend services remain on the internal network.

Extraction uses pinned [Trafilatura](https://trafilatura.readthedocs.io/en/latest/extraction-overview.html) with Markdown output, formatting and readable-content filtering. Verify isolated extraction/network-boundary behavior with `docker compose exec -T worker python - < scripts/page_scraper_test.py`.

### Crawl4AI integration

The running worker reuses the existing Docker container named `crawl4ai` (tested version 0.8.6). It connects over the dedicated `forgetfulme_crawl4ai` network; set `CRAWL4AI_URL=http://crawl4ai:11235` in private `.env`. If that container is recreated, attach it again with `docker network connect forgetfulme_crawl4ai crawl4ai`. Do not connect it to the database network.

Our guarded fetcher downloads the public page and checks redirects/robots. It sends sanitized `raw:` HTML to Crawl4AI’s `/crawl` API with JavaScript disabled; Crawl4AI returns Markdown for the same managed Pages notes. This mode provides extraction, not browser-driven JavaScript rendering or cookie/session replay. Active resources are stripped before transfer. Service errors fall back to Trafilatura so the backlog continues. Notes and Page scraping status show which extractor succeeded. Optional `CRAWL4AI_API_TOKEN` is forwarded as Bearer authentication for an endpoint that requires it. No LLM/cloud API is used.

For a later server deployment, `compose.crawl4ai.yaml` provides an alternative dedicated service (configuration validated; not started on this machine): set `CRAWL4AI_URL=http://crawl4ai-service:11235`, then run `docker compose -f compose.yaml -f compose.crawl4ai.yaml --profile crawl4ai up -d --build --wait`. It has no host port and only the internal extraction network, because offline raw-HTML extraction needs no internet egress. This template pins the locally verified 0.8.6 API; review [Crawl4AI’s migration/self-hosting documentation](https://docs.crawl4ai.com/core/self-hosting/) before updating to 0.9.x, which changes authentication defaults. Run `docker compose exec -T worker python - < scripts/crawl4ai_test.py` to verify service integration and fallback.

### Shared interface

All app pages now use the same sidebar, branding and stylesheet, including import results/errors and the Obsidian vault wrapper. Login shares the form/branding styles. Obsidian itself remains an embedded desktop with its own appearance. Device and history timestamps use Maldives time. Run `python3 scripts/run_isolated_tests.py` to check shared navigation and rendering in a disposable stack.

## Local knowledge wiki (Ollama)

The Obsidian layer follows the source/wiki separation, source attribution and reviewed-note protection described by [obsidian-llm-wiki](https://github.com/gd4ai/obsidian-llm-wiki). This is a native Forgetful Me implementation; installing that plugin is not required.

Open **Forgetful Me/Home** inside the shared Obsidian desktop. Captured Markdown is published under `Forgetful Me/Captured pages/<readable title and source ID>.md`; source records, simple website/library/history indexes and saved answers live under `Forgetful Me/wiki`. Automatic concept/entity expansion is disabled. Existing `Pages` captures and browsing history are preserved. Generated notes have `managed_by: forgetfulme`; setting `reviewed: true` in their YAML frontmatter prevents automatic replacement. Files without the ownership marker are also preserved. Put annotations in wiki notes, keeping raw captures as evidence.

A separate `library-worker` scans local notes and processes selected PDFs. `wiki-worker` publishes generated revisions and uses the configured AI provider for draft synthesis. Defaults are `OLLAMA_URL=http://host.docker.internal:11434` and `OLLAMA_MODEL=qwen2.5:3b`. Install Ollama on the Docker host and run `ollama pull qwen2.5:3b` before starting the stack. The [default model](https://ollama.com/library/qwen2.5:3b) is approximately 1.9 GB. Keep Ollama private; change these environment variables and recreate the wiki worker when moving to a server. Ollama/model files remain on the host and need separate backup from the app’s database/vault backups.

AI summaries use up to 18,000 characters sampled from sections throughout each capture. Any extracted names and supporting quotations must occur in those excerpts; summaries remain unverified AI drafts. Failed/invalid model output retries up to three times with a five-minute delay. The page scraper runs independently, so model downtime does not stop capture. Pages requiring login, blocked by robots or without readable content still cannot produce wiki sources.

The authenticated **Knowledge wiki** page (`/vault/wiki`) shows progress and queues questions. Local lexical retrieval matches note sections and title/aliases; answers use up to six sections, at most two per underlying source, retain exact cited excerpts/revisions, and are saved to `wiki/queries`. An explicit archive or all-notes scope governs each question. Ask short, focused questions and refresh for results. No matching compiled sources produces an explicit failure. This bounded retrieval does not implement the reference plugin’s graph-ranking algorithms, whole-vault reasoning or wiki linting. Source text is sent only to your configured AI endpoint; the model receives no browser credentials or tools.

Validation: `python3 scripts/run_isolated_tests.py` runs wiki and authenticated page fixtures in an isolated stack with AI paused and fixture providers.

### Configure AI inside Forgetful Me

Open **AI settings** (`/settings/ai`) to select Ollama or an OpenAI-compatible Chat Completions API, enter its base URL and model, and optionally save an API key. Ollama uses a host base URL such as `http://host.docker.internal:11434`; compatible APIs use their API prefix, such as `https://api.openai.com/v1`. The adapter follows the [Ollama chat API](https://docs.ollama.com/api/chat) and [Chat Completions API](https://developers.openai.com/api/reference/resources/chat); compatible models must accept JSON output, temperature and maximum output tokens. Native Anthropic/Gemini APIs require an OpenAI-compatible gateway.

Settings persist in PostgreSQL and apply to the next wiki job without a restart. Saved settings take precedence over the initial Ollama environment defaults. Configure temperature, output limit and Ollama context size; pause/resume processing; use **Save and test connection** and refresh for a queued test result; retry failed summaries after fixing configuration. The connection test sends a short synthetic prompt only. Cloud settings cause subsequent source excerpts and questions to be sent to that selected endpoint; existing compiled notes remain preserved.

Keys are encrypted with PostgreSQL pgcrypto using a key derived from the app’s administrator password. They are never returned in HTML. Leave the password field blank to retain a saved key; remove it explicitly or replace it. Changing the provider or base URL clears the old credential unless a new key is supplied. Redirects are refused to prevent credential forwarding. Keep `.env` private and use HTTPS for cloud endpoints. If you change `ADMIN_PASSWORD`, re-enter the provider API key because existing ciphertext will no longer decrypt. Database backups include encrypted provider credentials.

## Clean vault and importing an existing local vault

The vault was cleared on 2026-10-06 at the user’s request after a verified local backup. Previous notes are preserved in `backups/vault-before-reorganization-2026-10-06.tar.gz`, and database state in `backups/database-before-vault-reorganization-2026-10-06.sql`. These private files are ignored by Git. Existing browsing records remain in the app; old captures were retired rather than downloaded again. A new browsing import can requeue those specific URLs.

Open **Import vault** (`/vault/import`), ZIP your local Obsidian vault folder and upload it. The importer copies Markdown notes, folders and attachments into the stack vault, removes a single enclosing packaging folder, skips existing files, and excludes hidden metadata such as `.obsidian`, `.git`, `.trash` and macOS ZIP metadata. It never installs local plugins or changes the local vault. ZIP limits are 100 MiB compressed, 500 MiB expanded and 10,000 entries; unsafe paths, symlinks, encrypted ZIPs and duplicate destinations are rejected. Existing notes are never overwritten, and file contents are validated in staging before copying.

For a larger vault, copy its contents to a new folder in the stack vault through Docker instead of uploading a ZIP. Replace the source path with your real local vault folder:

```sh
docker compose exec --user root obsidian mkdir -p /vault/My-local-vault
docker compose cp "/absolute/path/to/Local Vault/." obsidian:/vault/My-local-vault/
docker compose exec --user root obsidian chown -R 10001:10001 /vault/My-local-vault
```

Use a new destination folder to avoid merging or overwriting existing notes. Copy only notes and attachments; omit `.obsidian` if using this method so local plugins/settings stay separate. Back up your local vault before reorganizing it. The shared desktop opens `/vault`; your imported folder appears inside it.

Automatic downloading, history exports and wiki generation are **paused persistently** after cleanup, including across Docker restarts. Importing a local vault does not enable them. Use **Enable automatic processing** on Import vault when ready for browsing data, and enable AI separately in AI settings if you want summaries. Imported personal notes are preserved and are not automatically sent to AI. The generated archive now uses readable filenames and simple library/website/history indexes; automatic concept/entity expansion is disabled.

### Discover available models

In **AI settings**, enter the provider type, base URL and optional API key, then select **Save and fetch models**. Refresh after a few seconds and choose from **Available models**, then save your selection. Fetching works while vault automation is paused and keeps AI paused until you choose a model and enable processing. It lists models without downloading any model or sending notes/questions. Manual model names remain available for providers without catalog support.

Ollama discovery uses [`GET /api/tags`](https://docs.ollama.com/api/tags); OpenAI-compatible discovery uses [`GET /models`](https://developers.openai.com/api/reference/resources/models/methods/list) under your API prefix. Results are cached in the database and cleared when the endpoint or credentials change. A listed model may still lack JSON/chat support; use the connection test after selecting it. Native non-compatible APIs need a compatible gateway.

## Unified local knowledge library

Open **Library** (`/library`) to search imported Obsidian notes and generated captures without AI. The library worker maintains an incremental local PostgreSQL section index. Local indexing has an independent ingestion control; when unset it inherits automation. AI pause does not pause permitted local indexing. **Scan for changed notes** queues an incremental scan; **Rebuild every local note** reparses unchanged files too. Hidden directories, symlinks, files over 5 MiB, empty notes, failed/authentication captures and legacy duplicate capture paths are excluded from retrieval. PDFs are catalogued and signature-checked. Select PDFs in Library for bounded local extraction and searchable page citations; encrypted/corrupt/scanned files have explicit outcomes. OCR is disabled. Originals remain intact.

Search supports Unicode words and aliases, folds Latin accents/case (café/cafe match), preserves Dhivehi combining marks, and returns sections with line ranges. Filter by origin, type, tag, project or review state. The note viewer displays provenance, source references, existing links and escaped source content with line anchors. Project, review and exclusion preferences are stored separately from source notes. Review preferences also protect source summaries from subsequent AI generation. AI summaries sample sections across a document instead of only its beginning.

**Ask AI** requires enabled AI settings and an explicit evidence scope. The default scope is browsing captures only. Choosing **Include my imported notes** authorizes matching personal-note excerpts to be sent to the configured provider for that question. Answers use up to six sections, at most two per underlying source, and retain the exact cited excerpts, document IDs, revision hashes and line ranges. Open a citation to read its original evidence even after the source changes or disappears. Historical answers predating this release cannot recover missing excerpt snapshots. Local indexing/search never invokes the provider. Imported instructions and source text are treated as evidence, never executable instructions.

**Vault health** (`/library/health`) reports empty/thin notes, incomplete provenance, inconsistent types, unresolved/ambiguous links, duplicate content, embedded page data, invalid PDF captures and recoverable filename encoding damage. Findings are review suggestions; example links can be intentional. Filename recovery previews referring notes and app relationships, reports file/catalog collisions, and requires a fresh content hash before applying. Edits after preview block the repair; existing Markdown links remain for review in Obsidian. ZIP imports recover legacy UTF-8 filenames mislabelled as CP437 and normalize Unicode while detecting duplicate destinations. Capture controls support per-URL retry/exclusion, and new login/redirect/challenge or unreadable captures are blocked before saving.

**Research questions** (`/library/questions`) collects Open questions sections from notes. Resolve one by linking an indexed answer note; reopen it when necessary. Shared tags and project assignments produce suggested connections on each note. Accepted connections are stored in the app and exported as companion notes under `Forgetful Me/Connections`; original imported notes are preserved. The Overview now reports searchable files, review coverage, research questions and health findings.


## Resumable upgrades and isolated validation

[UPGRADE_CHECKLIST.md](UPGRADE_CHECKLIST.md) is the current checkpoint: completed
checks, remaining tasks, exact next action and deployment state. Read it before
continuing, then [UPGRADE_PLAN.md](UPGRADE_PLAN.md) and the latest
[WORKLOG.md](WORKLOG.md) entry. [AI_AGENT_HANDOFF.md](AI_AGENT_HANDOFF.md) includes
agent context. Update all four when completing a delivery or stopping work.

Evidence permission is independent from a note's folder and display origin.
ZIP provenance keeps imported notes imported, including notes inside archive
folders. Generated answers, connection companions and navigation/index notes
stay available for local reading but cannot feed AI retrieval. Unknown generated
source lineage is excluded from outbound evidence. Source-family exclusions are
rechecked when constructing prompts, including questions queued earlier. Local
indexing/search works while AI is paused; explicit provider diagnostics use only
a synthetic prompt.

Index jobs and sanitized file/publication/rename failures appear in Vault health.
Missing mounts or incomplete enumeration never discard the catalog. A failed
file keeps its last good revision while unrelated files can index. Stable note
IDs preserve app preferences, question resolutions and connections across
journaled filename repairs. On the Linux Docker runtime, repairs use atomic
no-overwrite rename and recover pending journals after a restart. Unsupported
filesystems/platforms fail safely. Source notes are never rewritten to repair
embedded links; broader link/connection export recovery remains on the checklist.

New captures are immutable. Changed content invalidates a summary; reviewed
summaries stay intact with a pending update. Generated-note publication validates
ownership, stored generated-content signatures and expected destination hashes;
detected conflicts retain a separate pending draft. Existing managed-file
updates still use optimistic compare/replace: strict protection against arbitrary
external-editor races and conflict-resolution tools remain FM-02 work.

Run the repeatable fixture suite from this repository:

```sh
python3 scripts/run_isolated_tests.py --check-config
python3 scripts/run_isolated_tests.py
```

The runner validates a standalone `compose.test.yaml`, builds a unique candidate
image, applies migrations twice, and executes scripts via stdin. It creates a
unique disposable PostgreSQL/vault/content project on an internal network, with
synthetic credentials, no host mounts/ports and no inference workers. It records
source/image fingerprints, rejects source changes during testing, and removes
only that test project's resources afterward. Production `.env`, database,
vault and external services are excluded. Mutating library/HTTP fixtures refuse
production defaults. App database host/name/user/port can be injected using
`PGHOST`, `PGDATABASE`, `PGUSER`, `PGPORT`; existing production defaults stay intact.

Retain the exact passing candidate image for an authorized deployment, apply
additive migrations, recreate the four app services, and compare their app hashes
and health with the tested source. Use read-only production checks afterward.
The fixture harness is not a backup restore rehearsal; that FM-09 step is pending.

### Upgrade verification and recovery

See UPGRADE_CHECKLIST.md for the exact deployed candidate and pending acceptance work. `python3 scripts/run_isolated_tests.py` runs disposable regressions; add `--benchmark` for 1k/10k retrieval measurements. `scripts/backup_before_upgrade.py` saves a fresh private baseline/database/vault backup and leaves background writers paused until rollout. External editors/Obsidian are separate writers; these archives are sequential, not an atomic full-stack snapshot.

Use `python3 scripts/restore_drill.py --database PATH --vault PATH --image TESTED_IMAGE` to rehearse in disposable resources. `python3 scripts/verify_release.py --baseline PRIVATE_BASELINE --image TESTED_IMAGE` checks live code/image/health and original/settings preservation read-only. The DB/vault drill has passed; content/config offline recovery also passed; matched full-stack runtime/credential rollback remains pending. Older code is not a verified rollback against newer schema; review compatibility and restore a matched backup pair with the same credentials before production recovery.

Open **Index jobs and recovery** (`/library/jobs`) from Vault health for paginated scan history, file errors and rename conflicts. Retry failed scans after resolving permissions/content problems; local-index pause keeps scans queued. Rename journal retry reuses the original content hash and refuses changed files or destination collisions. Originals and last good evidence remain preserved.

`python3 scripts/volume_restore_drill.py --content PRIVATE_CONTENT_ARCHIVE --obsidian-config PRIVATE_CONFIG_ARCHIVE --image TESTED_IMAGE` verifies regular-file hashes/ownership in new offline disposable volumes only. It excludes links/special files; the rehearsed configuration had three Chromium Singleton runtime links, which must not be carried to a restored desktop. The saved content archive was empty, so nonempty binary/hidden fixtures were also tested. This tool never restores live volumes or starts Obsidian. Keep matched production archives and original credential environment for an actual recovery.

`python3 scripts/full_restore_drill.py --backup-dir PRIVATE_SCHEDULED_BACKUP_DIR --image TESTED_IMAGE` checks a matched four-archive backup set in disposable resources. It compares original database columns through forward migrations, verifies a seeded state/credential roundtrip, starts restored FastAPI with six authenticated page checks, and checks content/config hashes and ownership. It publishes no ports and starts no workers/providers/Obsidian. Synthetic encryption tests do not replace preserving the original production ADMIN_PASSWORD/environment; old-code/new-schema and desktop-runtime rollback remain unverified.

Library Origin now includes **generated** for app navigation and legacy browsing-history display, with explicit imported ZIP provenance taking precedence. Counts separate those files from imported notes. Display labels do not change AI evidence scope, source lineage or exclusions.


2026-10-07 latest checkpoint: FM-01–06 and FM-08 complete; FM-07/09 remain partial. Ten populated responsive UI screens passed scoped checks. Unused pip removed from runtime; 19 tests passed and exact candidate b1258a3cddfe deployed/verified. Companion scans have high/critical findings; archive desktop image is absent locally and its OS audit is unavailable. Resume UPGRADE_CHECKLIST.md and reports/container-audit-review-2026-10-07.md before companion recreation. AI remains paused; model answer/abstention evaluation and actual desktop rollback remain outstanding.


2026-10-07 companion follow-up: patched Caddy proxy deployed after isolated real-config/auth/routing checks; no high findings in its final scan (three other entries remain). Backup service healthy after restart and fresh scheduled backup. Exact pinned PostgreSQL restore verified latest saved DB/vault; PostgreSQL tag unchanged. Archive candidate passed empty-state startup/restart only and remains undeployed with high/critical findings. Resume remaining database/desktop/crawler advisory and saved-state rollback work in UPGRADE_CHECKLIST.md; evidence in reports/companion-update-2026-10-07.md.


2026-10-07 database/desktop follow-up: tested PostgreSQL17.11 zlib correction deployed to database/backup (exact image 5fab158ded33); source/settings verification passed. Matched same-image Obsidian HTTP/process startup/restart and original source preservation passed on copied volumes. Obsidian candidate downloads timed out; current desktop and optional Crawl4AI digests pinned. Remaining: crawler/desktop/archive patches, cross-version/interactive rollback and paused model evaluation. Resume reports/database-desktop-checkpoint-2026-10-07.md and UPGRADE_CHECKLIST.md.


2026-10-07 crawler delivery: available Debian updates, PyJWT/urllib3 fixes and Requests-compatible chardet deployed after real extraction/restart and JWT-enabled API tests. Upstream overlapping jwt/PyJWT namespace repaired with a maintained auth adapter. Exact image e12f6af5ffe9; original launch configuration preserved and old crawler retained stopped for rollback. Notes/settings verification passed; scanner rules 995→771, critical 35→25. Next: Crawl4AI 0.9.0/anyio/nltk candidate tests, desktop cross-version recovery and archive compatibility. Read reports/crawler-delivery-2026-10-07.md and UPGRADE_CHECKLIST.md.


## Latest checkpoint — 2026-10-07 23:35 Maldives

Matching Crawl4AI 0.9.4 server/library and compatible app client are deployed. Twenty isolated scripts and the actual API/auth/config/restart matrix passed; all five app services are healthy. Original 1,201 sources and ingestion settings are preserved; AI remains paused. Direct crawler API access now requires a bearer token; the app receives its private token from ignored `.env`. Final crawler scan still contains 25 critical rules (768 total), requiring further artifact/runtime triage. FM-07/09 remain partial. Resume `UPGRADE_CHECKLIST.md` and `reports/modern-crawler-delivery-2026-10-07.md` for minimal-base/advisory work, desktop cross-version recovery and archive image/state compatibility. Earlier dated entries are historical.


Latest continuation (2026-10-07 23:48 Maldives): read-only crawler triage recorded 22 critical rules in historical metadata and three in installed OS components; no exploitability clearance. Experimental Python 3.12 supervisor candidate e208621bb2ac passed the full extraction/restart/auth matrix and removes Python 3.11. It is not deployed. Automatic approval review blocked external Docker Scout metadata transmission; next prerequisite is explicit scan approval, then bundled Node/fork review and maintained-build integration. See reports/crawler-runtime-triage-2026-10-07.md and WORKLOG.md. Production and AI pause remain unchanged.


Latest continuation (2026-10-08 10:15 Maldives): official 0.9.4 image extraction/restart passed but no-expiration JWT acceptance failed. Maintained crawler build now uses the pinned new official base plus existing auth/dependency fixes and Supervisor 4.3.0 on Python 3.12.14; duplicate Python 3.11 removed. Exact candidate 3e099e0a5b4a passed the full modern API/extraction/restart matrix, but remains undeployed awaiting explicit Docker Scout metadata transmission approval and fresh scan. Remaining FFmpeg/TIFF, browser Node/fork advisory review and desktop/archive recovery stay open. Production and AI pause are unchanged. Resume reports/new-base-crawler-continuation-2026-10-08.md.
