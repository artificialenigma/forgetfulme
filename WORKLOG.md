# Forgetful Me — conversation and worklog

This file preserves the project conversation available in this chat and records completed work. Entries are chronological and append-only; corrections should be recorded in a new entry. Dates use Indian/Maldives time (UTC+05:00). System messages, tool output, and unrelated environment context are omitted.

Keep adding project user and assistant messages as work continues. Update `PLAN.md` when a decision is confirmed; suggestions in this log are not automatically accepted plans. Conversations in other chats must be provided before they can be recorded here.

## 2026-10-04 — initial planning conversation

### 1. User — project purpose

> forgetful me is an app that we are planning to keep the history of pages i browsed through the browsers across the devices where i can take all the history from and keep it stored and pushed to obsidian

### 2. Assistant — initial understanding

Forgetful Me will be a personal browsing archive: it collects your browser history across devices, stores it in one place, and sends it to your Obsidian vault so you can find pages again later.

The core flow would be:

1. Collect visited URLs, page titles, timestamps, and the source browser/device.
2. Sync them into a searchable archive, grouping repeat visits.
3. Export them to Obsidian as Markdown, with links and optional notes or summaries.
4. Let you exclude sites, pause collection, and delete stored history.

One important distinction is whether you want **a record of pages you visited** or **saved copies of their content**. History helps you rediscover links; saved content remains useful if a page disappears.

Which browsers and devices should the first version support, and do you want links only or saved page content too?

### 3. User — two-part architecture

> the plan is to have two parts, one a docker stack with a reverse proxy, database and webapp. the second part is a plugin for chrome and safari to push the data to app. within the docker stacked app a feature to push all the collected data to obsidian app

### 4. Assistant — architecture discussion

That gives Forgetful Me two main parts:

1. **Self-hosted Docker stack**
   - Reverse proxy for HTTPS and routing.
   - Database storing browsing history from all connected devices.
   - Webapp for searching history, managing devices, and configuring Obsidian exports.
   - API receiving history from the browser extensions.

2. **Browser extensions for Chrome and Safari**
   - Pair each browser with your server.
   - Collect visited URLs, titles, timestamps, and device identity.
   - Queue records locally when the server is unavailable, then retry.
   - Provide pause controls and site exclusions.

The Docker app would also handle **Obsidian export**, including export status and retries.

The main architectural decision is how the server reaches your Obsidian vault. Obsidian stores notes as local Markdown files, so a remote Docker server needs a bridge. We can either mount a vault accessible to the server or build an Obsidian plugin that downloads collected records and writes them into the local vault.

For the first version, should the Docker stack run on the same machine as your vault, or on a separate server?

### 5. User — deployment lifecycle and documentation

> first testing would be done on device and later moved to a server which it would reside afterwards. create a worklog or history to keep all the chat converstations we are having and plan file where all the final plans are written

### 6. Assistant — documentation work

> I’ll create a conversation worklog and a separate plan file, capturing the decisions so far and keeping unresolved choices clearly marked.

Completed:

- Created `WORKLOG.md` with the project conversation available so far.
- Created `PLAN.md` separating confirmed decisions from proposed details and open questions.
- Linked both documents from `README.md`.

Completion response: Created `WORKLOG.md` for our conversation history and ongoing work, and `PLAN.md` for confirmed plans and unresolved decisions. Both are linked from the README. The plan records local testing first, followed by permanent server deployment. I’ll keep these files updated as we continue.

### 7. User — Git publishing

> git push afterwards

### 8. Assistant — Git publishing

> I’ll commit the documentation and push it to the configured remote.

Publishing the initial project documentation on `main` to the configured `origin` remote. This request also establishes the preference to push completed project changes afterwards.

The initial commit and push attempt was blocked by automatic approval review because it required explicit authorization for publishing the conversation history to the configured GitHub destination.

### 9. Assistant — publishing approval request

The documentation is ready, but the commit and push are blocked. Do you approve committing `README.md`, `PLAN.md`, and `WORKLOG.md` and pushing them to `artificialenigma/forgetfulme` on GitHub, branch `main`?

Automatic approval review rejected the action because the files include our conversation history and it requires explicit approval for that content and destination.

### 10. User — approval

> i approve

### 11. Assistant — approved publishing

> I’ll commit and push the approved documentation to `artificialenigma/forgetfulme` on `main`.

Publishing succeeded: commit `81a3e9b`, pushed to `origin/main`.

### 12. Assistant — publishing result

> Committed and pushed the documentation to `main`.
>
> Commit: `81a3e9b` — `docs: record project plan and conversation history`

### 13. User — collection approach

> how do you plan to scrape the information on the links from the browsers?

### 14. Assistant — collection proposal

> I’ll check the browser extension APIs so the collection plan reflects what Chrome and Safari actually allow.

Proposed approach: collect visit metadata through browser APIs, then optionally extract readable content from the loaded page with a permitted content script. Chrome supports historical import through `history.search()` and `history.getVisits()`, and new-visit events through `history.onVisited`. Safari support must be validated on the selected versions; historical import is not promised. Extract title, URL, description, author/date when available, and main article text after loading; account for dynamic navigation and missing content. Queue records locally and send authenticated batches to the Docker API with stable event IDs for retry deduplication. Preserve repeat visits separately from content snapshots. The server stores records and prepares Markdown for the pending Obsidian delivery mechanism. Proposed default is metadata collection, with content capture enabled for selected sites or individual pages; skip private browsing and excluded sites, and do not collect credentials or form inputs. Old URLs cannot provide the original page content unless it was saved at the time. This is a proposal, not an approved implementation decision.

References checked: Chrome history API (https://developer.chrome.com/docs/extensions/reference/api/history), Chrome content scripts (https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts), Apple Safari web extensions (https://developer.apple.com/documentation/SafariServices/safari-web-extensions), and Safari browser compatibility guidance (https://developer.apple.com/documentation/safariservices/assessing-your-safari-web-extension-s-browser-compatibility).

The assistant explained that visit metadata and optional loaded-page extraction would be collected separately, queued locally, uploaded in authenticated batches, and prepared as Markdown for Obsidian. Existing history does not contain past page content. Automatic approval review blocked publishing these new documentation changes and requested fresh approval.

### 15. User — publish updates

> push the updates to git

### 16. Assistant — publishing updates

> I’ll commit and push the updated plan and conversation log to `main`.

Publishing succeeded: commit `b412b3c`, pushed to `origin/main`; working directory was clean.

### 17. User — Docker stack improvements

> what eles can you include in the docker stack to make the app better?

### 18. Assistant — proposed stack improvements

> I’ll look at useful additions for background processing, search, storage, and recovery, keeping the initial stack manageable.

Recommended first-version additions: background worker, scheduler, persistent captured-content storage, and scheduled backups with tested restores. Proposed PostgreSQL full-text search can cover initial search without a dedicated search container. Add a broker if the chosen job framework requires one. Later options: uptime monitoring, Meilisearch, object storage, a browser-rendering worker for selected public pages, and optional AI enrichment. Pairing, credentials, exclusions, and export/retry controls remain application features. These suggestions are pending agreement and were added to PLAN.md as proposals.

Sources checked: PostgreSQL full-text search (https://www.postgresql.org/docs/current/textsearch.html), Celery getting started (https://docs.celeryq.dev/en/main/getting-started/), and Meilisearch typo tolerance specifications (https://specs.meilisearch.dev/specifications/text/0117-typo-tolerance-setting-api.html).

Publishing succeeded: commit `3adba64`, pushed to `origin/main`.

### 19. User — implement the Docker stack

> build the docker stack first

### 20. Assistant — implementation

> I’ll build the initial Docker stack with the webapp/API, database, background worker, scheduler, reverse proxy, and backups, then validate it and push the changes.

> I’m using Caddy, PostgreSQL, and a small Python webapp, with a database-backed job queue to keep the stack compact. Docker is installed but its engine isn’t running; I’ll try starting it so I can test the containers. This first build will provide a working stack and status dashboard; browser collection and Obsidian delivery will follow.

Started Docker Desktop and built a Compose stack with Caddy, PostgreSQL 17, FastAPI, a one-shot schema initializer, worker, scheduler, and scheduled backup service. Generated private local credentials without including them in Git or the Docker build. Added an authenticated dashboard, readiness/liveness endpoints, persistent volumes, background maintenance jobs, heartbeat health checks, backup retention/retries, dependency locking, and README instructions for local use, HTTPS server deployment, and recovery.

> The containers are running, and the worker has processed its first scheduled job. I’m now checking authentication, backups, and a database restore. The README also covers moving the stack to a server with HTTPS.

Validation: Compose configuration and Python/shell syntax checked; images built and services started locally; smoke checks passed for readiness, authentication, dashboard, worker/scheduler execution, backup archive readability, and restoration into a disposable database. Browser ingestion, extraction, search, and Obsidian integration are explicitly not implemented in this foundational build.

References checked: Docker Compose startup order (https://docs.docker.com/compose/how-tos/startup-order/), Caddy configuration (https://caddyserver.com/docs/caddyfile/options), and PostgreSQL pg_dump (https://www.postgresql.org/docs/current/app-pgdump.html).

Implementation pushed as `06e175e`. The assistant reported the local dashboard at http://localhost:8080, credentials in the private .env, passing health and restore checks, and browser/Obsidian work still pending.

### 21. User — connection troubleshooting

> check errors not reachable check the ports

### 22. Assistant — port investigation and fix

Checked containers, proxy/app logs, listening sockets, and HTTP responses. Port 8080 was listening on 127.0.0.1; localhost readiness returned 200 with ready status and the dashboard returned the expected 401 login challenge. Port 8443 had no active TLS listener in local HTTP mode. Found that the localhost-only Caddy host matcher returned an empty 200 for requests addressed to 127.0.0.1. Changed the local site to :80 so both local hostnames route to the app; retained the configurable domain for server HTTPS. Added a regression check for the numeric loopback address and documented local ports and login behavior. The in-app browser inspection was blocked by its browser security policy; no browser-policy workaround was attempted.

Fix pushed as `894e519`. The assistant reported the hostname fix, HTTP port 8080, local TLS limitation, private credentials, and browser inspection limitation.

### 23. User — continued loading failure

> could not load

### 24. Assistant — browser login compatibility

> I’ll replace the browser’s HTTP authentication prompt with a normal login page. The server checks passed, but the browser may be failing to display that prompt. I’ll keep the dashboard protected and test the login flow.

Implemented a normal login page with username/password fields, CSRF validation, and signed expiring HttpOnly/SameSite session cookies. Secure cookies are enabled when Caddy forwards HTTPS. Anonymous dashboard requests redirect to login; API access remains protected, with Basic authentication retained for command-line checks. Added no-store response headers and a same-origin form-action policy. Browser authentication prompt failure is a hypothesis, not a directly verified cause: the earlier browser security-policy rejection prevents further browser inspection. Expanded HTTP smoke checks to exercise login, session access, invalid credentials/cookies, and missing CSRF tokens. Updated README and plan to match the implemented login flow.

Login-flow smoke checks passed and the fix was pushed as `08ccb33`. The assistant provided the direct login link and explained that browser rendering remained unverified.

### 25. User — login credentials

> whats the username pass

The assistant read the private local .env and supplied the existing login credentials directly to the user. The password is intentionally omitted from this version-controlled conversation log.

### 26. User — improve dashboard presentation

> looks good but the presentation of the data in the dashboard could be better

### 27. Assistant — dashboard presentation update

> I’ll improve the dashboard with clearer status cards, a service overview, and a more readable job summary, using the data the stack already provides. I’m applying the frontend design direction skill for this update.

Chose a calm, compact operations dashboard with a dark green navigation rail, neutral background, clear typography, and restrained state badges. Added summary cards for connected services and queued/completed jobs; a service table distinguishing current web/database checks from worker/scheduler heartbeats; and the latest eight real maintenance jobs. Missing/stale background services show attention states. Times use Indian/Maldives (UTC+05:00). Added manual refresh, section navigation, accessible table headers, a skip link, keyboard focus styles, and responsive mobile layouts. Planned collection/Obsidian features remain visibly unavailable rather than displaying sample browsing data.

> The dashboard now has summary cards, clearer service states, and a recent-job table. Timestamps use Maldives time, and the layout adapts for mobile. It also clearly marks browser collection and Obsidian delivery as planned features. I’m checking the rendered HTML, stylesheet, and existing login flow before pushing.

Rebuilt the running Docker app and reloaded the proxy stylesheet policy. HTTP smoke checks passed for the login/dashboard, worker/scheduler, backups and restoration; the stylesheet endpoint returned successfully. Python syntax and Git whitespace checks passed. Direct browser visual verification remains unavailable due to the previously reported browser policy restriction.

Dashboard presentation update pushed as `a15e514`.

### 28. User — inspect and integrate Archive Manager

> check /Users/fa-001524/Documents/protos/internetarchivemanager and possible bring that function as a service in this stack?

### 29. Assistant — Archive Desk companion

> I’ll inspect Internet Archive Manager to see what it does, how it runs, and whether it can fit into this Docker stack as a service.

Read its README, Dockerfile/Compose/entrypoint, server routing and authentication, session access checks, job storage, and package metadata. It is Archive Desk: a Node/Playwright app exporting accessible Internet Archive/HathiTrust scanned book pages to PDF or ZIP with available OCR. It is not a general website scraper. Its GPL-3.0 source remains in the original checkout. The service uses a separate Chromium login profile, a local-only host/origin policy, app tokens, and an unpassworded loopback noVNC interface. Jobs are in memory; exported files and profiles persist.

> The project is “Archive Desk”: it exports accessible Internet Archive and HathiTrust book pages to PDF or ZIP, with optional OCR. It already has a Docker service and a separate Chromium login session.
>
> I’ll add it as an optional service in Forgetful Me’s stack. Initially it will keep its own interface and storage; connecting its exports to Forgetful Me’s database and Obsidian will be a separate step.

Added an optional Compose overlay with the archive profile, source-path configuration, local-only ports, a separate egress network, persistent state, Chromium shared memory, health checking, and bounded logs. Documented startup, separate state/backups, queue restart limitations, and the changes needed before shared server access. No original Archive Desk source or existing browser profile was modified or imported. Compose configuration validation passed.

Archive Desk's existing test suite passed: 55 tests, including mocked access/session handling, PDF/ZIP generation, job lifecycle, and route boundaries. Added a companion smoke script that checks UI serving, API token enforcement, job listing, and the browser-view HTTP endpoint without signing in to a provider account.

Built and started the optional container successfully; its health check and all companion smoke checks passed. Local ports 8766 (app) and 6080 (browser view) were verified. No live authenticated book export was attempted. Shared Forgetful Me records, Obsidian integration, and inclusion of its state in the main backup job remain pending.

Archive Desk integration pushed as `70e525b`.

### 30. User — check Obsidian connectivity

> check the connectivity with obsidian vault

### 31. Assistant — connectivity inspection

> I’ll check whether the stack has an Obsidian connection configured and whether a local vault is available.

Read-only checks found an open local vault registered with Obsidian. The vault and its .obsidian directory exist, and host permissions permit reads and writes. No community-plugin list was found. Inspected application code, Compose settings, and running web/worker mounts: there is no implemented Obsidian integration, vault mount, or configured Obsidian API connection. The worker only mounts the internal captured-content volume. Conclusion: the local vault is available but is not connected to Forgetful Me. No vault files were changed, and no write/export test was performed. The private absolute vault location is omitted from this published log.

Connectivity findings pushed as `f4a6bd4`.

### 32. User — host Obsidian and vault inside the stack

> can you add obsidian to the docker stack so its running inside the app and the vault is inside the app

### 33. Assistant — containerized Obsidian implementation

> I’ll check a containerized Obsidian option and add it with a vault stored in the stack. I’ll use a new vault and leave your existing local vault untouched.

Checked LinuxServer's Obsidian image and Selkies documentation for architecture support, subfolder proxying, secure contexts, and desktop hardening. Added a containerized Obsidian desktop with /obsidian/ routing guarded by the app's signed session or API authentication, origin checks, and no host port. Added an embedded /vault page and sidebar link, a dedicated named-volume vault shared with the worker, read-only web mount, persistent settings, and initialization of a welcome note and vault registry. The existing local vault is not mounted or copied. Backup archives now include vault and desktop settings; automatic browsing/book note export remains future work.

Sources: https://docs.linuxserver.io/images/docker-obsidian/ and https://docs.linuxserver.io/selkies/user-guide/configuration/.

The initial lscr.io image pull stalled; retried with LinuxServer's Docker Hub mirror and successfully started Obsidian. The existing local vault was left untouched. Confirmed that the stack-owned vault is registered and Obsidian has initialized its workspace, and that the actual Obsidian process is running. All services are healthy. HTTP smoke tests passed for embedded desktop access, session protection, foreign-origin rejection, vault metadata, background jobs, backup archives, and a database restore. A vault backup was restored into a temporary directory successfully. A temporary connectivity note written by the worker was read by the Obsidian user, and then removed. Archive Desk smoke checks still pass. Direct visual browser verification remains unavailable because of the previously reported browser-policy restriction.

Obsidian implementation pushed as `d06116b`.

### 34. User — MinerU service

> can this be added as a service https://github.com/opendatalab/mineru

### 35. Assistant — MinerU deployment assessment and template

> I’ll check MinerU’s deployment options and resource requirements, then assess how it could fit into this stack.

Read the upstream repository, MinerU 4 Docker deployment/runtime documentation, Dockerfile, and Compose API configuration. MinerU is suitable for converting PDFs/scans and supported documents into Markdown and structured outputs. The official current Docker deployment uses NVIDIA/CUDA/vLLM; non-NVIDIA 4.x Docker guidance is pending. Confirmed this Docker engine is ARM64. This does not mean MinerU itself requires NVIDIA: native macOS and CPU runtimes exist, but the documented GPU container is not appropriate for this host.

> MinerU would fit as a document-processing service: it can turn PDFs, scans, and saved documents into Markdown for the vault. Its current official Docker deployment targets Linux with NVIDIA GPUs, while this Docker engine is ARM64.
>
> I’ll add an optional deployment configuration for a compatible server. I won’t start that GPU configuration on this machine. Local CPU testing would need a separately validated setup.

Added an opt-in NVIDIA deployment template with a private worker/parser network, V1 API health check, selected GPU, read-only content volume, separate workspace, and worker endpoint configuration. No parser host port, vault access, or database access is provided. Documented upstream image build/version checking, hardware/runtime requirements, local-model provisioning, and integration/backup limits. Both base+MinerU and base+Archive Desk+MinerU Compose configurations validated successfully. The image was not built or started and no parsing inference was tested; existing running services were left unchanged. Worker submission/result retrieval and automatic vault export remain pending.

Sources: https://github.com/opendatalab/MinerU, https://opendatalab.github.io/MinerU/quick_start/docker_deployment/, https://opendatalab.github.io/MinerU/usage/tiers/, and upstream docker/compose.yaml and docker/global/Dockerfile.

## 2026-10-04 — Browser add-on and history ingestion

User request: “now to make the browser addon to push the history”.

Implemented Chrome MV3 collection and optional resumable 30-day local history import; Safari source captures new completed nonprivate tab loads. Added browser-device pairing/revocation, one-time tokens hashed in PostgreSQL, session-bound form protection, validated/deduplicated batch ingestion, history view and dashboard navigation. Queues persist locally and retry failed pushes; collection starts only after configuration and opt-in. Added domain exclusions, loopback/HTTPS endpoint checks, installation/privacy documentation and meaningful synthetic API/queue tests.

Rebuilt Docker stack successfully. Synthetic tests passed for pairing, ingestion, duplicate retries, invalid tokens/URLs, batch limits, rendering and revoked tokens; fixtures deleted. Node tests passed for queue deduplication, exclusions, pause, failed-push retention and acknowledged deletion. Existing stack smoke test passed including login, dashboard, vault/desktop, jobs, backup archives and database restore. Browser live capture not tested because extension installation requires the user’s browser. Safari converter blocked by unaccepted Xcode license; source is supplied without claiming a built/tested Safari app. No personal browser history was imported during development. Automatic Obsidian export remains planned.

## 2026-10-05 — Import browsing data

User request: “can you create a import function to bring in browsing data”. Added an Import history page reachable from dashboard, Devices and History, accepting user-selected UTF-8 CSV/JSON exports. Added named import sources, repeat-import deduplication using URL and normalized UTC timestamp, complete-file validation before saving, upload/row limits, authenticated session/CSRF checks and import outcome counts. Included sample files and documented formats and boundaries. No local personal browser files were accessed or imported.

Validation: rebuilt the Docker stack with all core services healthy. Import smoke tests passed for CSV/JSON uploads, repeat imports, equivalent timezone offsets, invalid-row atomicity, malformed JSON, missing timezone, invalid CSRF and unauthenticated access. Existing history-ingestion smoke tests also passed. Synthetic fixtures were deleted. Changes committed and pushed to the existing main branch.

## 2026-10-05 — Import sign-in navigation fix

User reported `{"detail":"Sign in to manage browser devices"}` when opening history import in the Docker app. The browser-page dependency returned an API-style 401 for a missing session. Changed signed-out GET navigation for Devices, History and Import to redirect to login; successful login returns to the requested page. Return destinations are restricted to known local pages. POST operations still require a valid session; no authentication checks were removed. Cookie sessions are scoped to the hostname, so localhost and 127.0.0.1 do not share login state. Rebuilt the running Docker app.

Validation passed: missing/invalid session redirects, successful login returning to import, rejection of external redirect destinations, full import/ingestion synthetic checks, and existing stack smoke tests including backup restore. Synthetic data removed. Committed and pushed the navigation fix.

## 2026-10-05 — Increase history upload size

User requested raising the upload limit from 4 MiB to 100 MiB. Updated file validation, streamed request limit, import page messages and README. Raised Caddy body limit to 105 MB (decimal), enough for a 100 MiB file plus the bounded multipart overhead. The 10,000-visit limit remains in place.

Validation: rebuilt Docker with healthy core services and reloaded Caddy. Import smoke tests passed, including a valid JSON upload larger than 6 MiB, proving both former limits are removed; authentication, deduplication and invalid-file checks still passed. Synthetic fixtures deleted.

## 2026-10-05 — Safari backup format support

User supplied the Safari JSON structure (metadata browser/data type/schema version, history entries with url/time_usec/visit_count/load-failure flag). Added explicit Safari schema-1 detection and validation, exact conversion of Unix microseconds, optional-title handling, and existing repeat-import identity compatibility. Added a synthetic example without the user's personal URL and integration coverage for Safari imports/retries, microsecond-equivalent generic timestamps, invalid timestamp types and unsupported schemas. Confirmed the timestamp epoch against Apple's export documentation. No personal history was imported. Aggregate visit_count and load-failure/redirect metadata are not stored; the UI and README disclose this boundary.

Validation: core Docker services healthy after rebuild. Full import/ingestion smoke test passed, including Safari first import and duplicate retry, exact timestamp equivalence, invalid Safari timestamps/schema versions, >6 MiB upload, generic CSV/JSON, atomic invalid-row rejection and authentication. Synthetic fixtures removed.

## 2026-10-05 — Refresh running Docker stack

User requested “update the docker”. Rebuilt/recreated the core and Archive Desk services from the latest source with Compose --build --wait and reloaded Caddy. All long-running services reported healthy; migrations/vault initialization completed. HTTP readiness returned ready. Running app includes Safari JSON import and the 100 MiB upload limit. Persistent volumes retained.

## 2026-10-05 — Remove 10,000-entry import blocker

User reported the 1–10,000 visits validation error for a Safari backup. Raised the entry cap to 1,000,000, retained the 100 MiB byte cap, and updated the import page/README. Replaced per-row inserts for file imports with temporary-table COPY and one deduplicating INSERT inside a transaction. Empty-file and oversized-file errors now differ; oversized errors show the count. Added synthetic 10,001-entry Safari import and repeat-import checks.

Validation: rebuilt Docker and confirmed healthy services. Import smoke tests passed including 10,001-entry Safari first import and duplicate retry, empty-file feedback, previous format/validation checks and >6 MiB upload. Synthetic fixtures deleted. Parsing and database work run in the thread pool so imports do not hold the async request loop during validation/saving.

## 2026-10-05 — Safari entry 382 validation blocker

User reported Safari entry 382 failing the generic validation message. Its actual contents were not available, so no specific cause was assumed. Added field-specific diagnostics and an explicit Safari skip-invalid checkbox checked by default. Accepted entries are saved while skipped counts and first 20 entry numbers/reasons are shown; URLs are not included in the report. Unchecked strict mode and generic imports still reject invalid files atomically. All-invalid exports save nothing. Added mixed valid/non-HTTP/invalid-time Safari tests, strict rejection and retry deduplication.

Validation: Docker core services healthy. Import smoke suite passed for mixed Safari entries, skipped-count/field reports without URLs, strict rejection, all-invalid rejection, deduplicated retry, 10,001-entry bulk import, >6 MiB upload and existing authentication/format checks. Synthetic fixtures deleted.

## 2026-10-05 — Browsing history UI repair

User reported incorrect display in Browsing history. Source inspection found an unconstrained plain table with repeated long URL text and latest-200-only results. Added a dedicated responsive history layout with consistent workspace navigation, fixed column widths, ellipsis for long titles/URLs (full text via hover), hostname fallback for missing Safari titles, mobile layout, Maldives timestamps and 50-entry pagination with stable ordering. No direct visual inspection of the signed-in browser was available; validation uses rendering and HTTP checks.

Validation: Docker services healthy. Synthetic import/ingestion suite passed, including authenticated history rendering, 50-row first/second pages, pagination links and timezone labels. Browser visual verification remains pending. Synthetic fixtures removed.

## 2026-10-05 — Automatic Obsidian history export

User reported that nothing moved to Obsidian. Previous milestones collected history and provided the shared desktop/vault but had not implemented note delivery. Added worker-based automatic export of existing/new visits into Forgetful Me/Browsing History, grouped by Maldives date and bounded visit-ID chunks. Added exported_at state, pending index and history/API progress counters. Writes use atomic replacement and exact database-selected IDs; retries rebuild managed files rather than append duplicates. An advisory lock serializes workers. Managed notes warn to keep annotations elsewhere. Private URLs are never logged. Database/vault backups already include the new records/files.

Validation: Docker healthy; isolated export tests passed for Markdown escaping, Maldives date grouping, deterministic retries and failure-before-progress updates. Existing stack smoke suite passed including vault access, worker/scheduler, backup archives and database restore. Finished the initial backlog: 11,432 of 11,432 visits exported, 0 pending, 194 Markdown history notes in the shared vault. No history URL/title contents printed during verification. New visits continue exporting automatically.
