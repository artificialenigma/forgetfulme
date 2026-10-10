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

## 2026-10-05 — Correct Obsidian delivery to include page contents

User clarified that the worker should scrape imported links into Markdown and place the content in Obsidian. Previous exporter only generated visit indexes. Added unique URL page-capture queue/backfill, ingestion/import enqueueing, public-network fetching with pinned DNS/TLS/redirect validation and robots policy, bounded reads, Trafilatura Markdown content extraction, atomic managed Pages files, persistent retry/blocked/failure states and authenticated status/retry UI. Added explicit worker-only egress networking and pinned extraction dependencies. Existing history indexes are retained, and their UI now labels them as visit indexes with a link to content-capture status. Raw personal URLs/content are not printed in logs. Public-page content reflects fetch time; cookies, PDF processing and JavaScript rendering are outside this capture path.

Validation: resolved and pinned extraction/transitive dependencies in an ephemeral container, rebuilt Docker successfully and confirmed healthy core services. Isolated scraper tests passed for private-address exclusion, readable Markdown extraction/boilerplate removal, unsupported types, robots restrictions, stable filenames and complete/blocked/retry/failed transitions. Live public documentation fetch produced a readable 70,218-character Markdown note in an isolated test directory. Auth redirects and existing stack smoke tests passed including backup restore. Confirmed actual worker-created content files in shared Pages folder (5 at verification); roughly 10,000 unique imported URLs remain queued and continue processing. No claim that all pages are captured; unavailable/restricted pages are tracked explicitly.

Final deployment check: a pre-existing stale backup heartbeat caused Compose --wait to fail even though the app/worker were healthy. Restarted backup; a fresh database/content/vault/config backup completed and all long-running services are healthy. Final scraper tests and browser-ingestion smoke checks passed. Synthetic ingestion page queue fixture is now removed with the device/visit fixture. Content capture continues in background; large backlogs take time at the conservative one-page-per-cycle rate.

## 2026-10-05 — Reuse existing Crawl4AI container

User requested adding Crawl4AI as a service or reusing the existing container named crawl4ai. Found running unclecode/crawl4ai:latest with installed version 0.8.6 and working health/API. Consulted official self-hosting docs and inspected local OpenAPI/config signatures; synthetic raw-HTML /crawl extraction succeeded. Added sanitized raw-HTML client, service preference with local fallback, extractor tracking, worker environment configuration and dedicated internal network. Attached existing container to that network and configured private .env without logging credentials. Added an optional Compose service template pinned to 0.8.6 for future deployment; it is configuration-validated, not running here. This integration performs Markdown extraction on guarded-fetched HTML, not browser-driven JavaScript/session capture.

Validation: private-network worker-to-service integration passed with synthetic HTML; client tests verified active-resource stripping, JavaScript-off configuration, service-outage fallback and live extraction. Existing scraper boundary/extraction/retry suite passed with Crawl4AI enabled. Actual queued content capture recorded 5 Crawl4AI successes at verification (plus other earlier/fallback notes). Docker/vault/backup/restore smoke suite passed. Optional Compose service configuration validates; only the existing container is used here.

## 2026-10-05 — UI audit and shared layout fix

User requested checking UI inconsistency before fixes, then explicitly asked to update the worklog and fix it. Audit found separate dashboard/sidebar, history/top-nav, generic inline-style pages, login styling and a minimal vault wrapper; inconsistent navigation, spacing, forms, tables and timestamps; and stale Foundation/export-planned copy. The initial audit made no changes.

Implemented a shared app shell with dashboard-based branding, sidebar, all workspace destinations, active navigation, common stylesheet, breadcrumb/footer and mobile navigation. Dashboard/history render content through it; Devices, Import, import results/errors, Scraping status and Vault use it too. Login uses the same branding and component stylesheet with a dedicated sign-in layout. Added shared form/table/button/feedback/vault/history styles, unified device timestamps to Maldives time, and removed stale dashboard copy. Obsidian's embedded desktop retains its own UI inside the consistent vault frame. Verification is through source/HTTP rendering; direct visual inspection of the signed-in browser remains unavailable.

Validation: Docker core services healthy after deployment. Shared-layout HTTP test passed across Overview, History, Devices, Import, Page scraping and Vault, verifying one stylesheet, shared sidebar/navigation and correct active item. Login and empty-import error page use the shared styling; empty import saved nothing. Login redirect/open-redirect tests and full stack smoke tests passed, including vault/desktop access and backup restore. Visual browser verification remains pending; no claim of screenshot-based review. Changes committed/pushed.

## 2026-10-05 — Capture table presentation

User asked to check the Page scraping table. Source inspection found unconstrained columns, headers rendered as an ordinary row, full URLs and hash-based vault paths wrapping into tall rows, and unstyled status labels. Added semantic table head/body/caption, fixed page/status/result proportions, clickable hostname with bounded full URL and hover text, colored status badges, readable saved-note/extractor descriptions, visible refresh/vault actions and an empty state. Full note paths remain available as hover text. Mobile uses horizontal scrolling to preserve readable columns. Shared layout/table components remain in use. Direct browser visual inspection remains unavailable.

Validation: Docker core services healthy after rebuild. Shared UI HTTP checks passed, including capture table head/body, status badge/URL classes, explicit refresh action, consistent sidebar and active navigation. Login and empty-import error rendering remain correct. Visual screenshot verification was not available.

## 2026-10-06 — Rework Obsidian using a linked local-AI wiki

**Conversation:** User requested reworking the Obsidian integration using https://github.com/gd4ai/obsidian-llm-wiki as inspiration. When asked about the AI provider, user selected “Local model through Ollama”.

**Implementation:** Added linked raw/source layers, Home and paginated library/site/history indexes, evidence-backed concept/entity pages, source attribution and reviewed-note protection. Added database migration fields and an independent Docker wiki worker. Added authenticated Knowledge wiki progress and queued source-grounded Q&A with saved answers. Downloaded Qwen 2.5 3B to existing host Ollama and confirmed Docker connectivity and a successful source synthesis. Original captures/history remain preserved. Model processing uses bounded excerpts and labeled drafts; the reference plugin’s advanced graph algorithms are not implemented.

**Deployment/validation:** Rebuilt Docker, backfilled 506 existing successful captures into the linked source library, and verified the first real local-model summary. Final validation results are recorded below after the running app checks.

**Final checks:** Docker services healthy; 511 source records indexed at verification, with 16 concept and 12 entity notes generated so far. Wiki ownership/reviewed-note preservation, safe links, malformed synthesis and citation allowlists passed. Shared page frame/navigation, login redirects and question authentication/CSRF checks passed over HTTP. Live Ollama Q&A successfully produced citations and a saved vault note; temporary test artifacts were removed. AI synthesis continues in the background. Visual browser automation was unavailable from the earlier UI-policy restriction, so UI verification used authenticated HTTP rendering. README and PLAN describe setup, server migration, bounded retrieval and draft limitations.

## 2026-10-06 — AI provider settings in the app

**Conversation:** User requested entering the AI provider base URL and settings inside Forgetful Me.

**Implementation:** Added shared-navigation AI settings with Ollama/OpenAI-compatible selection, URL/model/key and generation limits, processing pause, queued connection test and failed-summary retry. Settings persist in PostgreSQL and are read at each job. Keys use pgcrypto encryption, are never displayed back, and are cleared when changing endpoint unless replaced. Auth/CSRF checks protect mutations, and AI HTTP redirects are refused. Updated the worker, knowledge page and documentation for configurable local/cloud processing.

**Validation:** Provider adapter tests passed for Ollama and OpenAI-compatible request/response formats, authorization headers, endpoint validation and truncated-output rejection. Live authenticated settings tests passed saving, pause, blank-key retention, secret redaction, credential clearing on endpoint switch, CSRF rejection and a real queued Ollama JSON connection test; the original Ollama configuration was restored. Unified page navigation checks passed. Cloud adapters were verified with fixtures; no external cloud account/key was supplied or invoked. Docker was rebuilt for final labels/styling.

## 2026-10-06 — Clear vault, stop downloads and import personal notes

**Conversation:** User called existing notes gibberish and requested clearing/reorganizing the vault. User then instructed stopping downloads and uploading browsing data later, and requested a clean vault with the ability to copy/import a local vault. Adjusted the task to leave a clean personal vault without repopulating from old captures.

**Actions:** Stopped vault writers/desktop; verified a backup containing 3,597 Markdown notes and saved the database state under ignored backups/. Cleared note content, preserved Obsidian configuration and reset its stale workspace state. Retained browsing records in the app, retired old capture exports and removed generated question records. Persistently paused downloading/history export/wiki generation and paused AI. Added ZIP import with session/CSRF protection, no overwrite, attachment/folder preservation, hidden/plugin metadata exclusion, staging and traversal/symlink/size/count validation. Added an explicit automation toggle and documented Docker copying for large vaults. Simplified future archive indexes and readable filenames; disabled concept/entity fan-out.

**Validation:** Verified all 3,597 original Markdown entries in the backup before deletion. The clean vault contains one start note and no old generated content. ZIP tests passed layout/attachments, hidden-file exclusion, no-overwrite, duplicate/traversal/symlink rejection. A live authenticated ZIP upload copied two synthetic files, skipped them on repeat and rejected bad CSRF; test files were removed. Shared navigation passed with the Import vault page. Confirmed automatic processing stays false and the note count stays at one across worker cycles. Restarted an overdue backup service to refresh its health marker. Local vault files have not been copied: the user can now upload their ZIP or provide a local path for a future copy.

**Final checks:** Docker services are healthy, the vault status API reports one start note, and both vault automation and AI remain paused after restart. Verified a later browsing import requeues a reset URL in a rolled-back test transaction. Provider connection tests remain available while archive processing is paused. Simplified-index tests confirmed readable titles and no concept/entity fan-out. Private backup files have owner-only permissions.

## 2026-10-06 — Fetch model catalog from the AI base URL

**Conversation:** User requested entering a provider base URL and fetching the available models from it.

**Implementation:** Added Save and fetch models, a cached model selector and manual-name fallback. Discovery runs in the worker even with vault processing paused, using the selected provider endpoint and encrypted credential. Connection details are saved with AI paused until selection/enabling. Catalog requests use bounded, redirect-refusing GETs to Ollama /api/tags or OpenAI-compatible /models; no model download or browsing content is involved. Endpoint/key changes invalidate cached catalogs.

**Validation:** Ollama/OpenAI catalog fixture tests passed response formats, authenticated GETs, duplicate filtering and malformed catalog rejection. A live authenticated request fetched qwen2.5:3b from local Ollama with a blank initial model, displayed the selector and saved its selection. Unknown selector values and invalid CSRF were rejected; AI stayed paused and the original model setting was restored. No cloud catalog was contacted. Docker rebuilt with the final endpoint-change behavior.

## 2026-10-06 — Unified vault research library

**Request:** Implement all seven improvements from the vault analysis and update Docker: imported-note search, section retrieval, capture quality checks, project/connections/question workflows, evidence visibility, vault health/Unicode repairs, and unified navigation.

**Implementation:** Added a local incremental PostgreSQL note/section catalog maintained by the wiki worker independently of archive/AI pause. Library search and origin/type/tag/project/review filters now span imported notes and captures. Ranking prioritizes question-term coverage; Unicode tokenization includes combining marks and Dhivehi. The evidence viewer shows source metadata, related notes, escaped content and line anchors. AI questions retain an explicit archive-only or imported-note scope and cite retrieved sections; summaries sample across full documents. No cloud calls are made by indexing/search. Added quality checks for auth/challenge/thin captures and invalid PDF signatures, per-URL retry/exclusion, source-independent review/project preferences, preservation of app-reviewed generated notes, open-question resolution, shared-tag/project connection suggestions and companion-note exports. Vault health reports links, duplicates, missing provenance, thin/empty notes, metadata inconsistencies and recoverable encoding damage. ZIP import recovers legacy UTF-8/CP437 names; filename repair is previewed and applied individually. Overview and navigation now expose knowledge statistics and the unified library.

**Validation:** PostgreSQL tests passed Unicode retrieval, relevant evidence beyond the former prefix cutoff, query-term coverage ranking, archive-only scope, exclusions, suggestions, incremental indexing, grounded section citations with a fixture provider, and preservation of original notes. Existing wiki, page scraper, ZIP import, AI provider and history export regressions passed. Live authenticated HTTP checks passed search, filters, project/review/exclusion preferences, app-reviewed rewrite protection, accepted connection exports, question resolution/reopening visibility, no-overwrite filename recovery, capture exclusion/inclusion, login boundaries, CSRF and invalid AI scope rejection. Shared navigation checks passed. Synthetic data was removed. No live provider call was made; AI remains disabled.

**Deployment:** Rebuilt the image, applied additive schema changes and recreated web/worker/wiki-worker/scheduler. All four services are healthy and every app file matches the checkout. Verified all 1,200 visible imported file contents remain intact, including the ten pre-existing filename discrepancies. The catalog includes all 356 visible imported Markdown notes, attachments and generated captures. Archive automation remains enabled; AI remains disabled. PDFs are catalogued and signature-checked, but PDF text/OCR extraction is not part of these seven changes.


## 2026-10-06 — Upgrade plan and AI-agent worklog/handoff

**User request:** “Plan upgrades and updates and write worklog for an ai agent”.

**Scope:** Planning and documentation only. Preserved the existing uncommitted app implementation. Did not modify application code, source notes, database settings, dependencies or Docker services in this task.

**Inspection:** Reviewed the current PLAN/README/worklog, vault-analysis report, library/index/retrieval/routes/worker code, tests, Compose configuration and backup script. A read-only parallel audit checked concrete reliability and evidence-boundary gaps. Findings are from code inspection; they are not newly executed reproductions or fresh runtime-health assertions.

**Findings for the next agent:** Path-derived archive origin can admit imported-note-derived answers to a later archive-only request and misclassify imports under the generated folder. Recapture can retain old completed summaries despite changed content. Source publication can skip enough missing/protected rows to starve newer work, and can mark a failed source-record write as indexed. Full-catalog indexing lacks a completed-traversal/mount guard and per-file error isolation; separate file reads can mismatch content/hash under concurrent edits. Path-based renames can lose relationships/question state; saved line citations do not retain source revisions. Generated-note publication can miss a concurrent human edit/review toggle. Candidate truncation can reduce evidence diversity before per-note limits apply.

**Documents created:** UPGRADE_PLAN.md contains FM-01–09, dependencies, code-grounded problems, acceptance checks and a definition of done. AI_AGENT_HANDOFF.md contains the next-agent context, first-task fixture, pending task ledger, worklog template, test/deployment procedure and continuation prompt. PLAN.md now distinguishes implemented current behavior from dated historical proposals and links the new documents.

**Recommended first task:** FM-01 — reproduce the evidence-lineage issue with synthetic data, separate display origin from outbound evidence permission, exclude uncertain generated derivatives by default, and enforce source exclusions before prompt construction. FM-02 and FM-03 follow before broader PDF/throughput/search expansion.

**Validation:** Checked document references, task IDs, planned/delivered distinctions and documentation diffs. A second read-only review corrected the handoff to require disposable database/vault isolation before mutating tests, preserved synthetic provider diagnostics while background AI is paused, and made citation retention after source deletion explicit. No application tests or Docker operations are required for these documentation-only changes. Previous deployment and test results remain recorded in the preceding worklog; this task does not repeat or supersede them.

**Status:** Upgrade plan and AI-agent handoff prepared. All FM-01–09 implementation items remain Planned. Future dependency updates must verify supported versions/advisories against official upstream information when execution is authorized; no claim is made that a specific current package version is outdated.


## 2026-10-06 — Upgrade implementation started: resumable foundation delivery

**Request:** “now work on the upgrade and do a checklist so it can be continued always where it was left off”. The upgrade is authorized; created UPGRADE_CHECKLIST.md with individual acceptance boxes, current checkpoint and a checkpoint protocol. Existing uncommitted implementation was preserved (HEAD d181d12); no reset/clean was used. Host reference vault remains untouched.

**Starting runtime:** Read-only inspection found all four app services healthy. Recorded an ignored owner-only baseline of 1,200 original visible source file hashes; automation enabled, AI disabled. No note text or keys are required for fixtures. Baseline lives in backups/upgrade-2026-10-06/baseline.json.

**Candidate changes:** Explicit provenance-based evidence scopes, generated-answer/navigation suppression, prompt-time exclusions/AI pause, saved parent IDs and retained citation excerpts; immutable catalog IDs, path history and rename operation journals; complete-traversal/mount guards, no-follow descriptor snapshots, per-file error isolation, incremental/full index jobs with progress; publication deferral and truthful success counts; immutable changed captures, content-bound summaries and guarded managed publication. Safe bounded YAML and code/Unicode fidelity use PyYAML 6.0.3, verified against upstream releases/documentation/security. Test configuration/DB/HTTP settings now support disposable fixtures.

**Parallel review:** A read-only audit identified a real editor-save race in link/unlink renames. Corrected it using atomic Linux renameat2 RENAME_NOREPLACE with anchored directory descriptors and no unsafe fallback ([Linux API contract](https://man7.org/linux/man-pages/man2/rename.2.html)). Isolated Linux filesystem fixtures verified collision handling and human revision preservation. Review also corrected stale provenance on unchanged scans, historical capture-family exclusions, and destination metadata conflicts. Existing managed-file updates still use optimistic compare/replace; FM-02 is not complete.

**Validation in progress:** Static compile and whitespace checks passed. A preliminary isolated suite verified guards, migrations twice, metadata, local library and evidence/citation/index/rename fixtures. Source publication testing exposed synthetic IDs sharing the same filename prefix; corrected fixtures and added explicit source-ID collision protection. Changing files during test runs correctly prevented a final PASS. The final frozen full-suite result and any deployment are recorded in the next entry; do not treat preliminary results as a release.

**Next action:** Complete the frozen 12-script harness run, fix any real regressions, then deploy the exact tested candidate under the existing Docker-update authorization and record health/code/source/settings preservation. Continue FM-02's strict versioned publication/link recovery and FM-03 fairness/failure UI afterward. FM-05–08 and full FM-09 dependency/restore work remain pending.


## 2026-10-06 — First upgrade delivery validated and deployed

**Scope/status:** Delivered FM-01 evidence permission/exclusions and FM-04 metadata/extraction. Supporting FM-02/03/07/09 foundations are deployed; the full upgrade backlog is incomplete. UPGRADE_CHECKLIST.md is the authoritative resumption record, synchronized with UPGRADE_PLAN.md, AI_AGENT_HANDOFF.md and PLAN.md.

**Final isolated validation:** `python3 scripts/run_isolated_tests.py` exited 0. All 12 scripts passed: harness_guard_test, library_test, metadata_test, evidence_scope_test, source_revision_test, wiki_test, page_scraper_test, vault_import_test, ai_provider_test, obsidian_export_test, library_smoke_test, ui_shell_test. Real disposable PostgreSQL migrations applied twice. Source-image matching and frozen app/fixture checks passed. Private-network disposable project forgetfulme-tests-d967011f4233 and its volumes/network were removed; candidate image retained. No production resources or live providers were used by these tests. Earlier source-ID prefix collision and old question-ID fixture failures were corrected; preliminary passes were not used for rollout.

**Release identity:** Candidate `forgetfulme-test:d967011f4233`; exact image `sha256:a43f30cbea858f23af33ecb35920ff13bb7ed0e89b13a64cc2cfc45e0b5fb9e8`; app fingerprint `055a7064b09959040c8f4c39a377ae9cb2e7646d9b911a2b66d636181a32faff`. Retagged candidate to forgetfulme-app:local without rebuilding. Stopped worker/wiki-worker/scheduler, ran additive migrate, then `docker compose up -d --wait --wait-timeout 120 web worker wiki-worker scheduler`. Required migrate/vault-init were recreated; companion archive desk/Obsidian/Crawl4AI services were preserved. Migration is repeat-safe in fixture validation. Git HEAD remains d181d12 with prior/current changes uncommitted; source hashes distinguish this release from HEAD alone.

**Preservation/recovery material:** Saved owner-only ignored backups/upgrade-2026-10-06/database-before-upgrade.sql (19,405,567 bytes), vault-before-upgrade.tar.gz (70,745,632 bytes), and baseline.json. Before/after comparison verified all 1,200 original visible files identical. Host reference vault untouched. Automation remained enabled and AI disabled. Saved backups are not yet restore-drill verified; FM-09 retains that task.

**Live read-only checks:** All four services healthy, exact image IDs matched, all 30 app files in each matched the checkout/tested fingerprint. First scan succeeded over 1,562 files with zero failures; following incremental scan also succeeded. Signed-in GETs for Library, Vault health, Research questions, Knowledge wiki and AI settings passed. An initial page-copy assertion expected “retained” where the actual label said “retain”; corrected that probe and the remaining GET checks passed. No production fixture writes or provider calls occurred. Static compile/whitespace/document checks passed. No screenshot/visual browser review was performed.

**Dependencies:** Added PyYAML==6.0.3 to requirements and lock after upstream verification ([releases](https://github.com/yaml/pyyaml/releases), [safe loading documentation](https://pyyaml.org/wiki/PyYAMLDocumentation), [security](https://github.com/yaml/pyyaml/security)). Full dependency/advisory/image-pin work remains FM-09; this release makes no claim that every dependency is current.

**Remaining limitations/next action:** Resume FM-02 strict versioned no-overwrite generated publication and conflict selection/recovery. Existing managed updates still use optimistic compare/replace; retain that limitation until tested across the final external-editor race. Add old-path link resolution and safe connection companion regeneration; broaden recovery/retention tests. FM-03 large-job fairness and detailed failure UI remain incomplete. PDF extraction, ingestion-policy controls, measured retrieval benchmark, project/reading workflow, visual QA and complete release/restore hardening remain unchecked. Do not repeat completed FM-01/FM-04 or claim all nine upgrades complete.


## 2026-10-07 — Disconnect checkpoint during second delivery

**Interruption:** Account usage-limit errors interrupted the agents during second-delivery integration. The user asked where work disconnected; inspected saved docs and checkout to establish the exact state. No new Docker deployment or complete second-delivery validation occurred.

**Drafted:** Immutable generated publication journal and wiki callers; selected bounded local PDF extraction/routes/fixtures and pinned dependency; ingestion controls/domain budgets/routes/fixtures; diverse retrieval selector and labelled benchmark. Latest root edits appended PDF schema and question-filter metadata columns, added PDF page-number search/exclusion guards, projected extracted page chunks during scans, and rejected nonregular descriptor sources. These latest edits are unvalidated.

**Exact next action:** Fix publication checksum stripping outside frontmatter, first-create crash-after-write idempotence, and synthesis returned-path persistence. Complete conflict recovery/UI, then wire routers/navigation/effective AI controls, retrieval selection/preview and worker isolation. `app/library_worker.py` and `scripts/publication_test.py` were not created before interruption. Run the frozen isolated suite and benchmark before a second rollout. Preserve all uncommitted changes.

**Runtime distinction:** Last verified deployed release remains the 2026-10-06 first delivery recorded above (12 passing scripts, exact tested image). Current checkout is newer than that image. No fresh runtime-health assertion is made by this checkpoint. UPGRADE_CHECKLIST.md now records this disconnect rather than implying the second delivery was tested.

## 2026-10-07 — Second delivery validated, deployed and checkpointed

**Request/scope:** Continued the authorized upgrade after the disconnect. Preserved HEAD d181d12 and existing uncommitted work; no reset/clean/commit. Reference host vault untouched. FM-01/04/05/06 complete; FM-02/03/07/08/09 partial.

**Changes:** Strict no-overwrite generated revisions with durable publication/conflict journal and recovery; frontmatter-only ownership checks, capture-pointer reconciliation, app path aliases and recoverable connection companions. History exports also retain immutable revisions. Added separate library-worker with independent heartbeats/scan progress, nonregular/FIFO rejection, selected resource-bounded local pypdf extraction with immutable page citations and queue states. Independent inherited ingestion controls, domain policies/budgets/backoff/cancel/retry and credential-redacted new exports. Diverse budgeted evidence selection, project/source filters and local preview. Project workspace, question/health pagination and dismiss/reopen, answer picker, reversible connections and safe Markdown reading. Additive migrations/index version 4; originals never rewritten for derived extraction/publication.

**Validation:** Final `python3 scripts/run_isolated_tests.py` exited 0, all 18 scripts passed, migrations twice, app/source/image identity and frozen app/fixtures/build inputs. No live provider calls; synthetic providers only. Temporary fixture resources removed. Static compile and git diff --check passed. Failure-driven corrections included PDF job-variable shadowing, early AI pause handling, publication collision/recovery fixtures, deterministic policy queue fixtures, constrained parser budget errors, Markdown renderer callback binding and authenticated CSRF fixture handling. Two disposable advisory-tool attempts failed due tmpfs execution/cache settings; corrected execution/cache placement and final audit succeeded. Preliminary images were not treated as final acceptance. Final safeguards prevent FIFO reads hanging and prevent library scan progress impersonating the wiki-worker heartbeat.

**Retrieval evidence:** reports/retrieval-benchmark-2026-10-07.json records 25 labelled questions/29 synthetic notes, answerable Recall@5 1.0 and zero invalid citations/scope/exclusion violations. Deterministic 50-query runs at 1k/10k notes returned Recall@5 0.96, p50/p95 64/211 ms and 483/1,923 ms. Timing is SQL retrieval plus selection, excludes scans/inference. Related-hit unanswerable cases still require model-abstention evaluation; no actual model accuracy claim. Benchmark candidate 8100b994ac8c predates final publication/heartbeat safeguards; retrieval code unchanged.

**Recovery/dependencies:** Fresh owner-only ignored backups/upgrade-2026-10-07 contain baseline.json, database-before-second-delivery.sql and vault-before-second-delivery.tar.gz. Three renames and one addition existed before rollout (no original content edits), retained rather than reverted. Disposable restore verified 3,511 vault files, 2,672 document rows and 96 index jobs; migrations twice/settings preserved. A second seeded SQL restore verified identities/preferences/exclusions/review/projects/connections/resolved questions/exact citations/PDF selection/jobs/pages. Content and Obsidian-config volume recovery remain pending. Public requirements lock audit returned no known vulnerabilities for 37 Python packages (reports/dependency-audit-2026-10-07.json); Python/PostgreSQL images pinned. This is not a full OS/companion-stack audit. Backup helper now also pauses library-worker; external editors remain independent writers and sequential archives are not atomic snapshots.

**Deployment:** Retagged final passing candidate forgetfulme-test:5dcb0feb89a5 to forgetfulme-app:local, without rebuilding; image sha256:0113f7c31a256acf2f2b06018db50d9332510cc631e500eadf0f4b986559661b, app fingerprint 049b37ed741dda233b5b1690b7ab5dd39d1e37f1b0fe7b7eab620123da299c7c. Additive migration completed, recreated only app services with --no-deps; companion services/volumes retained. Final permanent verify_release.py passed: five healthy services, 40 app files each match, image IDs/label match, 1,201 baseline sources preserved, automation true/AI false and nullable stage inheritance retained, nine authenticated GETs. Latest index succeeded with 2,853 seen/20 changed/zero failures; counts evolve.

**UI:** Actual signed-in Projects view inspected at 1280x900 and 390x844, no overflow and visible keyboard skip-link focus; viewport reset afterward. Safe empty-project screenshots saved in the Codex visualization directory. Populated forms/notes/accessibility matrix remains pending.

**Next action:** Extend disposable authenticated POST publication activation/dismissal tests for protected/imported destinations and crash/retry reconciliation; then rename link-impact preview and detailed FM-03 failure pagination/retry. Core publication/PDF/policy/retrieval/workflow implementation is already deployed. Checklist, plan, handoff and README updated; do not claim the full backlog complete. Preserve AI pause unless instructed otherwise. No private contents/keys/tokens/provider outputs included in this record.

## 2026-10-07 — Publication action/reconciliation acceptance follow-up

**Scope:** Continued the first unchecked FM-02 prerequisite under the existing upgrade authorization. Added disposable signed-in publication POST fixtures: valid activation, dismissal, repeated actions, invalid identity/CSRF, changed/missing/imported/reviewed/identity-conflicting/symlinked proposals. Tests assert original and retained proposal bytes survive. Added caller-crash summary reconciliation/idempotence, stale revision, immediate source exclusion and changed proposal recovery fixtures.

**Findings/fixes:** Activation failed to consult reviewed overrides on the proposal destination; it now uses the same generated ownership/protection check as publication. Symlink path validation escaped the route's error handler and returned HTTP 500; it now returns HTTP 409 with originals retained. The first run used a nonexistent archive_name fixture column; corrected the fixture to the actual import-origin schema. The second run reproduced the symlink failure; final frozen full regression is recorded below. No production fixtures or provider calls, no schema changes, prior uncommitted work preserved.

**Publication follow-up release:** Final frozen full 18-script suite passed, migrations twice. Candidate forgetfulme-test:d6cad7348827 (image sha256:09c543d8f856912d004c9e746aaafe78afda72943bf6314aa98150840a06002a; fingerprint ac722bc3c1a585f405c788ed0d7871f4aa1e6e7c8c5aa7319e067312b73f0346) retagged and deployed without rebuilding. Fresh private baseline/database/vault saved at backups/upgrade-2026-10-07-150752. Permanent read-only verification passed five healthy exact-source/image services, all 1,201 originals preserved, automation true/AI false/stages unchanged, nine authenticated GETs. Latest index succeeded (3,811 seen, 11 changed, zero failures). This follow-up backup is saved, not separately restore-drilled. Continued next to rename previews.

## 2026-10-07 — Filename-repair impact preview

**Changes:** Vault health now links to an authenticated repair preview showing referring notes (bounded first 50), accepted connections and resolved-answer counts. Filesystem or destination catalog/preferences collisions hide the apply action. Preview describes app aliases versus retained Markdown links. Repair POST requires the preview content hash; a later source edit returns a conflict without moving the file. Initial source reads use bounded no-follow regular-file snapshots. Existing atomic no-overwrite rename journals remain responsible for final collision and recovery checks.

**Fixtures:** Added signed-in inbound-link/connection preview, filesystem and catalog collision, stale-preview human edit and successful relationship-preserving rename cases. Updated earlier repair smoke test to submit the preview hash. Full frozen regression and rollout results follow. Broader move/delete/restart/retention acceptance review remains open; a preview is not a guarantee against all external filesystem edits.

**Filename follow-up validation/deployment:** Frozen full 18-script suite passed, migrations twice and source/build/fixture identity checks. Exact candidate forgetfulme-test:c5d875f955ab, image sha256:dd898b3f53998445a266316caec7bdb551bbfa9871dd90e3d0a25ae0b7441c6d, app fingerprint 91301d197e1923a3d25116acc25dd0978d366ac78a6849ddfcb6648d3a5438a7; retagged and deployed without rebuilding, companion services/volumes retained. Fresh private backup and baseline backups/upgrade-2026-10-07-151106 saved (not separately restore-drilled). Static compile/whitespace checks passed. Checklist/plan/handoff/README synchronized. No schema or provider changes.

**Next action:** Broaden rename move/edit/delete/restart/retention recovery coverage and review remaining acceptance gaps, then implement detailed paginated FM-03 failures/retry controls. Publication action matrix and rename impact preview are complete; broader FM-02/03/07/08/09 are still partial. No populated visual review was performed for the new preview screen; authenticated synthetic HTTP flows were tested.

**Final read-only verification:** verify_release.py passed all five healthy app services with 40 source files/image IDs/fingerprint matched, 1,201 baseline originals unchanged, automation true/AI false and ingestion stages preserved, nine authenticated GETs. Latest index succeeded (3,843 seen, 11 changed, zero failures). Counts evolve with authorized automation.

## 2026-10-07 — Bounded rename recovery and failure/retry workflow

**Scope:** Continued recorded FM-02 recovery and FM-03 failure controls. No schema changes or live provider requests; preserved existing uncommitted work and source notes.

**Changes:** Rename reconciliation uses bounded no-follow regular-file snapshot hashes, including crash-after-move recovery; FIFO/nonregular destinations cannot hang a worker. Pending rename recovery processes at most 20 journals per batch with row skipping. New authenticated /library/jobs sections paginate index jobs, file errors and incomplete rename operations at 30 rows. Failed jobs queue another scan; file failures queue a full reparse, retaining last good evidence until success. Rename conflict retry acquires the index lock and reuses the original journal hash/no-overwrite rules. Health links to the detailed controls. Retry controls respect local-index pause; no toggles are changed.

**Acceptance fixtures:** Added edited/deleted/FIFO/post-move-edited rename journal failures, original retention, paginated job history, signed-in/CSRF scan retries, blocked destination collision and successful rename retry/idempotence. Existing retained citation/delete and atomic crash-recovery tests remain. Full frozen suite results and exact rollout identity are recorded below. Broader large-corpus index interruption/retention/full FM-02/03 audits remain open.

**Initial live follow-up:** Candidate 196c603b7042 passed all 18 scripts and deployed; five services/source hashes/health matched. Fresh private backup baseline saved at backups/upgrade-2026-10-07-213825. Live verification timed out following login to the dashboard, then directly on Vault health. Preservation assertions ran before HTTP but the full check did not pass; do not claim complete live verification of that candidate. Updated the read-only verifier to consume the actual 303 login/session without loading the dashboard and to report route names, not content. A temporary 302 expectation in this helper was corrected to the app's 303 response.

**Performance correction:** Health resolved every fallback link by scanning all catalog paths and joined whole duplicate groups before truncating display text. Added a per-health suffix lookup retaining exact/local/history/ambiguity behavior, and bounded duplicate description construction. Regression fixture compares indexed and original link resolution semantics. This also benefits dashboard diagnostics. Final candidate tests/rollout/read-only verification follow; no timeout increase used to conceal the latency.

**Final release:** Full frozen 18-script suite passed again, migrations twice and source/fixture/build checks. Exact candidate forgetfulme-test:2344befd48e8, image sha256:9e2d081ef19cf6e0191f3dc9e28010c59f3f4f36c7a70a4f9625055968935756, app fingerprint e8df78f4eff073d07782323c37c3a59cbbd198b5c617fda133c89b52fda4f5c5 reused without rebuilding. Fresh private baseline/database/vault backups/upgrade-2026-10-07-214324 saved; snapshot not separately restore-drilled. Five app services healthy and all 40 source files/image IDs matched. Permanent read-only verification passed twelve authenticated pages including Vault health and all new recovery sections, within the unchanged per-route timeout. All 1,201 baseline sources preserved; automation true/AI false/stage controls unchanged. Latest index succeeded (5,670 seen, 22 changed, zero failures). Counts evolve. Static compile and whitespace checks passed.

**Next checkpoint:** Large-corpus index interruption/restart and final FM-02/03 retention/acceptance audit; remaining full-stack content/config restore and broader populated visual QA remain listed. Core retry workflow and additional rename conflict matrix are delivered. No private content, credentials or provider responses logged; host reference vault untouched. Checklist/plan/handoff/README reflect the deployed state. The dashboard benefits from the shared diagnostic fix but was not included in the final twelve-route assertion; no measured dashboard latency claim.

## 2026-10-07 — Checklist recovery acceptance and volume rehearsal

**Changes/evidence:** Added index_restart_test.py to default harness (19 scripts): 1,000 synthetic notes, real SIGKILL at 100 snapshots, durable progress >=80, transaction rollback, restart marks interrupted job failed, exact 1,000-note successful reindex, ten changed revisions and stable identities, deletion retains absent identity, unchanged incremental no-op. This is a deterministic process-death test, not all possible hardware failures. Added concurrent review-switch publication fixture and explicit last-success/current-progress/heartbeat freshness timestamps to job UI.

**Volume recovery:** New volume_restore_drill.py accepts private content/config archives and tested image, creates new unique offline volumes only, validates archive paths/budgets, restores regular files/directories with data filter and UID/GID 10001, verifies exact file hashes as the app user, and removes only generated volumes. Actual saved content archive was empty; all 295 regular Obsidian configuration files verified. Three skipped links were confirmed Chromium SingletonCookie/SingletonSocket/SingletonLock runtime artifacts. Separate hidden/binary/nonempty synthetic files (two) verified content restore. No production mounts/services changed by rehearsal, no private filenames or contents printed.

**Acceptance review:** reports/recovery-acceptance-2026-10-07.md maps FM-02/03 requirements to actual fixtures and records retention behavior/limits. No automated citation/revision deletion was found; current chunks may be replaced but retained citation snapshots are stored independently. Backup retention operates on backup directories. Full matched-set runtime rollback/credential compatibility remains distinct from separate archive rehearsals, which used snapshots from different times. Saved configuration was not launched as Obsidian during the offline rehearsal.

**Validation:** Initial new 19-script full frozen suite passed. Application source matched the already deployed release in that initial run, so no deployment was needed for that test-only change. Final 19-script run includes the job freshness UI and concurrent review boundary; results and rollout follow. Static compile/whitespace checks passed.

**Final recovery acceptance release:** All 19 full frozen scripts passed, migrations twice, app/build/fixture/source identity verified. Exact tested candidate forgetfulme-test:356edb42335f reused as local app tag without rebuilding; image sha256:36a2b2601eb555da4545b32ed54243ab46ee8c4f3d2f2224277ea2d746045a19; app fingerprint 0c7d36ee57739294089873ef7fa0096968b3b4f27babc3b63282c500b89150cf. Fresh private baseline/database/vault backups/upgrade-2026-10-07-215433 saved (not separately restore-drilled). Deployed only five app services with --no-deps, companions/volumes retained. Final verify_release.py passed: five healthy exact-image/source services (40 app files), twelve authenticated GETs, all 1,201 baseline sources unchanged, automation true/AI false/ingestion stages unchanged. Latest index succeeded (5,670 seen, zero changed/failures). Static compile/whitespace checks passed. No live inference or reference-host-vault writes.

**Checklist disposition:** FM-01–06 complete against recorded acceptance, FM-07/08/09 remain partial. Next: matched full-stack runtime/credential compatibility review; then populated responsive/accessibility review and generated legacy display metrics. Model answer/abstention evaluation remains unmeasured with AI paused. Full OS/companion dependency audit remains. Separate content/config archives and DB/vault rehearsals are not falsely reported as a single matched full-stack restore. Updated all checkpoint/plan/handoff/operator docs and retained historical failed attempts.

## 2026-10-07 — Matched recovery compatibility and legacy display refinement

**Matched recovery:** New full_restore_drill.py requires one scheduled backup directory containing database.dump/vault/content/config archives, converts the custom database archive offline into private owner-only temporary SQL, and invokes disposable database/vault and volume rehearsals. Updated restore_drill.py compares original table columns across forward migrations (older snapshots may not have newer library tables), preserves browsing/capture/AI/control rows as well as existing library state, seeds nonempty identity/citation/PDF states and synthetic encrypted credentials, and starts only restored FastAPI with no workers/host ports/provider calls. It checks six signed-in pages via the app's signed-session mechanism. Matching synthetic encryption environment decrypts the fixture; wrong environment is rejected. Real stored keys were not decrypted or logged. Temporary SQL/resources removed.

**Result:** Matched 20261006T124820Z set passed: 11,432 visits, 10,030 captures, one AI settings row, one control row and empty historical questions retained through migrations twice; six archived vault files restored; nonempty seeded restore state roundtrip passed; six authenticated app pages passed. Content/config check passed 295 exact regular configuration files/ownership, three omitted Chromium runtime links and separate two-file hidden/binary fixture. First runtime attempt mistakenly used HTTP Basic against session-only library routes and failed; corrected the harness to signed-session authentication before recording PASS. Rehearsed the full set again with original browsing/capture/settings-column preservation assertions. Actual Obsidian/companion desktop launch or old-image/new-schema backward rollback is not claimed.

**Display refinement:** Added a separate display_origin field for generated navigation/history, respecting explicit ZIP import provenance. Local Origin filter offers generated; imported-note/generated counts are separate in Library/dashboard. Stored origin, evidence_scope, source IDs and AI allowlist are unchanged. Generated navigation remains excluded from AI; namespace-based legacy labels do not confer or remove evidence permission. Tests cover imported marker priority and unchanged evidence boundaries. Full 19-script candidate validation and live rollout follow.

**Display release:** Full frozen 19-script suite passed, migrations twice, image/app/fixture/build identity checks; scope regressions passed. Exact candidate forgetfulme-test:9ae53065ffff retagged without rebuilding; image sha256:053ea879addf3dc8d48e103038690334076e8f020f7ee931b2067a55d2d34ac0; fingerprint 05e58923b371efc5100c0d79b211bd920fa5648bac4c305eaffcbef05ca1d7a2. Fresh private baseline/database/vault backups/upgrade-2026-10-07-220352 saved, snapshot not separately restore-drilled. Five services healthy with all 40 files/image IDs matched, twelve authenticated GETs passed. All 1,201 originals preserved; automation true/AI false/nullable stages unchanged. Latest index succeeded (5,686 seen, zero changed/failures). Companions/volumes preserved; no host-vault writes, providers or private contents logged. Static checks passed.

**Next checkpoint:** Populated desktop/mobile/accessibility QA; then OS/companion dependencies and actual Obsidian/third-party runtime rollback review. Matched-set app/data compatibility and generated legacy display refinements are checked. AI answer/abstention quality still unmeasured with AI paused. FM-07/08/09 remain partial; no claim of whole-backlog completion. Checkpoint/plan/handoff/README and acceptance report synchronized.


## 2026-10-07 22:28 Maldives — populated UI and runtime hardening checkpoint

Standalone ui_snapshot_test passed after adding required synthetic PDF extractor_version; saved ten inert synthetic HTML snapshots and scoped browser results in reports/ui-review-2026-10-07.md. Desktop/mobile semantics matrix and representative visual/keyboard checks passed. Lighthouse navigated to a 404 static route, so its score was discarded. Preview bind required sandbox escalation; no auto-review rejection occurred.

Docker Scout exact-image audits recorded in reports/container-audit-review-2026-10-07.md and SARIF. Archive desktop scan unavailable because its running image is absent locally; collected only read-only Python version inventory. PostgreSQL registry metadata read failed; no companion replacement was deployed.

Dockerfile removes unused pip after locked installation. `python3 scripts/run_isolated_tests.py` passed 19 scripts with migrations twice and frozen image/source checks. Exact passing candidate b1258a3cddfe / sha256:23a20415044e90137a535527b1ca7f114f9be6073f92ef2121e3f0e1c07ca34b deployed via compose up --no-deps --wait to web/worker/wiki-worker/library-worker/scheduler. Fresh backup backups/upgrade-2026-10-07-221833 saved. verify_release with that baseline/candidate passed five image/source/health checks, 1201 unchanged original files, unchanged automation=true/AI=false/inherited controls and 12 authenticated GETs. Latest index succeeded: 5702 seen, zero changed/failed. App fingerprint remains 05e58923b371efc5100c0d79b211bd920fa5648bac4c305eaffcbef05ca1d7a2 (40 files); Dockerfile/image changed. Hardened audit dropped 36 to 29 findings, including removal of five high entries.

Next: recover archive image availability, triage/test compatible companion patches and desktop rollback; remaining model evaluation requires intentionally enabled AI. Preserve all uncommitted work, original vault and settings.


## 2026-10-07 22:39 Maldives — companion continuation

Fresh read-only inventory found scheduled backup unhealthy/overdue; `docker compose restart backup` restored healthy status and completed 20261007T173508Z. Pulled PostgreSQL17/Caddy2 candidates with bounded timeout: database digest unchanged; Caddy newer but retained high zlib advisory. Built pinned-base infra/proxy/Dockerfile with zlib>=1.3.2-r1, exact image d13915e628d36145ba0df6728cfc6388f06e9981d91e0e36f6aab2b04aeba85e. Isolated real-config/synthetic routing/auth/header checks passed; Scout shows three findings, zero high. Saved previous proxy image and private data/config in backups/proxy-upgrade-20261007T173838Z; deployed only exact tested proxy, verified live identity/login header/desktop auth redirect. No app/database/desktop containers replaced.

Available archive replacement 73358403e052 passed isolated app/noVNC startup and restart; new empty volume/internal network/no ports/providers. Audit565 rules includes101high/9critical; no deployment, saved-state/old-image recovery not claimed. Updated restore_drill.py to exact PostgreSQL pin/optional validated image argument. First restore command invalid filenames stopped before resource creation; corrected actual filenames, latest221833 restore passed6540files/originalrows/migrationstwice/synthetic state and key checks/six restored FastAPI pages. Compile/diff checks passed. Disposable resources removed.

Continue reports/companion-update-2026-10-07.md: database critical Go-binary triage, desktop/crawler/archive patched builds and saved-state rollback. Five app services remain b1258a3cddfe, AI disabled. No live provider calls or host vault changes.


## 2026-10-07 22:55 Maldives — database correction and desktop recovery

Exact PostgreSQL17.11 base zlib>=1.3.2-r1 derived candidate 5fab158ded33436b060a9841ab8df3e69070e9db3ae07a92d12edd525f8f2988 passed full_restore_drill using fresh matched 20261007T173508Z (6,839 vault files / 349 config files, original rows, migrations twice, synthetic state/key checks,six app GETs). Scout 57 vs 58 entries;22 vs 23 high,two critical Go/gosu findings remain. Fresh 225217 baseline/SQL/vault saved; old image retained. Database/backup deployed exact tested image, writers resumed; Compose start ran existing init/migrate dependencies successfully. Both healthy; verify_release passed 1,201 original files/settings/12 authenticated GETs, latest scan 6,173 seen, zero changed/failed. App/proxy release images unchanged.

Added desktop_restore_drill.py: early failures from large command arguments, HTTP-before-process readiness and expected .obsidian metadata writes repaired; final copied matched-state existing image actual Obsidian HTTP/process startup/restart passed with originalsource hashes intact. No live volumes/ports/providers; cleaned resources. Interactive/new-to-oldrollback not claimed. Obsidian pulls timed out after 120s and 90s, no rollout. Optional crawler 0.8.6 resolves existing a45fd... digest, active package 0.8.6 (old 0.7.8 finding only embedded SBOM); installed PyJWT 2.10.1 still affected. Current desktop/optional crawler digests pinned. Go/gosu 1.19 source+symbols indicate no TLS/IDNA calls, but no govulncheck proof; retain findings. Native strings exit 69 replaced with Python ASCII extraction, no tools installed.

Next: synthetic crawler candidate PyJWT/requests/OS tests; retry desktop candidate and copied-state upgrade/rollback; archive compatibility/image recovery. Details reports/database-desktop-checkpoint-2026-10-07.md. Compile/diff checks passed; preserve all uncommitted work, AI paused and source vault.


## 2026-10-07 23:13 Maldives — crawler security delivery

Built pinned upstream-derived candidate with 91 Debian package updates and PyJWT 2.14.0 / urllib3 2.8.0 / chardet 5.2.0; pip check passed. Initial root-runtime candidate failed /root permissions; restored appuser. Next candidate failed importing JWT because upstream jwt 1.4.0 and PyJWT share a namespace. Removed overlapping jwt and supplied server-compatible PyJWT auth adapter. Failed candidates were never deployed; private synthetic diagnostics captured before cleanup.

Final exact image sha256:e12f6af5ffe90c5554277fcd118034d949e230e78b9a2fcf8a1a779528f0f0f9 passed original-vs-final real application raw HTML extraction before/after restart, Unicode/absolute citations/resource stripping, pinned dependency/warning checks, JWT helper expiration/signature/algorithm rejection, and actual JWT-enabled API invalid/missing/expired rejection plus authenticated extraction. Tests used disposable internal networks, synthetic content/keys, no live mounts/ports/providers. Final Scout 771 rules vs 995; critical 25 vs 35 / high 193 vs 280. Ten critical entries are embedded SBOM only; PyJWT finding now solely embedded historical SBOM. Remaining concrete package targets recorded in crawler-remaining-critical JSON.

Saved private launch config/environment/container metadata in backups/crawler-upgrade-20261007T181014Z; deployed using deploy_crawler_candidate.py, retaining original stopped container crawl4ai-rollback-20261007T181014Z. Only capture worker paused/resumed; original ports/environment/server config/networks preserved and config bytes checked. Candidate healthy/non-root; worker health GET passed. App verify_release against 225217 baseline passed five exact-image/source/health checks, 1,201 unchanged source files/settings and 12 authenticated GETs; latest scan 6,173 seen/0 changed/0 failed. App/database/proxy versions unchanged, AI disabled. No production extraction fixtures posted. Compile/diff checks passed; disposable resources removed.

Next: Crawl4AI 0.9.0, anyio 4.14.2 and nltk 3.10.3 candidate API/auth checks; unresolved OS/base review, desktop newer-to-older copied-state and interactive recovery, archive image/state compatibility. Resume reports/crawler-delivery-2026-10-07.md. Full checklist remains partial.


## 2026-10-07 23:35 Maldives — matching modern crawler release

Crawl4AI server and library are both 0.9.4. Vendored upstream runtime comes from tag v0.9.4, commit `133e1d92e37885dfccc03ea2e3687d06c98b7ceb`; LICENSE and source hashes are retained in `infra/crawler/upstream-source.json`. The image applies a narrowly scoped JWT expiration requirement. The obsolete local 0.8.6 auth adapter is no longer copied into the image. Upstream release context: [0.9.4 release notes](https://github.com/unclecode/crawl4ai/blob/main/docs/blog/release-v0.9.4.md), [published package](https://pypi.org/project/Crawl4AI/0.9.4/).

The server now requires authentication for its exposed API. Migration saved the previous private environment/configuration, installed a private API token in ignored `.env`, and coordinated all five app services so the worker sends it automatically. External direct crawler clients must supply a valid bearer token. No credentials are recorded here. Modern security defaults are merged with previous operational settings; this is a configuration migration, not byte-identical preservation. Automation remains enabled and AI remains disabled.

The client omits forbidden crawler `base_url` configuration and still resolves relative links against the source URL. AnyIO 4.14.2, NLTK 3.10.3, PyJWT 2.14.0, urllib3 2.8.0 and chardet 5.2.0 are installed. Upstream's unclecode-litellm distribution replaces the original litellm distribution. Matching Playwright Chromium headless shell is installed. No model/provider calls occurred. The base/source version is pinned, but package repositories and upstream dependency ranges can change; future builds require another test and scan.

Validation passed 20 isolated application scripts, migrations twice, frozen source/image checks, and a disposable real server matrix before and after restart. That matrix covers raw HTML extraction, Unicode and absolute citations, resource stripping, absent/invalid/expired/no-expiration JWT rejection, unauthorized metrics/MCP/monitor routes, admin-scope rejection, forbidden JavaScript/base_url/browser proxy settings, private/file destinations, and environment-secret configuration rejection. Fixtures used internal networks, synthetic credentials/content, no production mounts or published ports. Live read-only worker checks confirmed health 200, unauthenticated metrics 401 and actual worker bearer authentication 200.

Failed candidates were not deployed: a library-only upgrade failed legacy server compatibility; the first matching server lacked its required browser shell. The proxy rejection fixture initially placed the field in the wrong configuration type and was corrected to BrowserConfig before the final matrix passed.

Deployed crawler: `sha256:35eabc8e6da154873a6846bf95e6d11bb5bb1a97d129fa3d1efad21ba8bf81fe` (`forgetfulme-crawler:local`). Deployed app: `forgetfulme-test:762a461c255a`, exact image `sha256:38d6a90e94c59f046f4ffae8bc6cef181362d781c58a14fe9c466aac5aa2bf4e`. App fingerprint: `ee0c78fbba80f2ccb2ae61c8312cd3e7e7b90be6b73db37ca025decfa1d4b945`.

Private baseline/SQL/vault backup: `backups/upgrade-2026-10-07-232923/`. Crawler migration backup: `backups/crawler-upgrade-20261007T183030Z/`; previous crawler retained stopped as `crawl4ai-rollback-20261007T183030Z`. Release verification passed all five healthy exact-image/source services, 1,201 unchanged original source files, preserved ingestion settings, and 12 authenticated read-only GETs. Latest indexing succeeded: 6,307 seen, 14 changed, zero failed; generated/index changes are normal and original sources were checked separately. Reference host vault was untouched. The backup from this delivery has not had a new restore drill; earlier matched-set recovery evidence remains in the checklist. Coordinated full app/server rollback was not deliberately exercised. The staging worker stop flag in the rollout report is historical; the worker has resumed and authenticated checks passed.

Final exact-image Scout scan: 768 advisory rules, including 192 high and 25 critical (prior crawler 771/193/25; original 995/280/35). Critical count remains 25. Some locations refer to historical embedded SBOM/artifacts; path classification alone is not a reachability verdict. This release does not claim a clean image or that all findings are exploitable. See `modern-crawler-audit-2026-10-07.sarif.json` and `modern-crawler-remaining-critical-2026-10-07.json`.

Next: triage remaining active runtime/OS/binary findings and test a compatible minimal crawler base; complete copied-state Obsidian upgrade/downgrade and interactive recovery, and recover archive image/state compatibility. FM-07 model answer/abstention evaluation remains pending while AI is paused; FM-09 remains partial. Preserve all uncommitted work and use the latest checklist checkpoint.

Commands: `python3 scripts/run_isolated_tests.py` (20 passed); `scripts/modern_crawler_check.py` with exact crawler/app candidates (passed); `scripts/deploy_crawler_candidate.py --modern-server --keep-worker-stopped` followed by exact-image tags and `docker compose up -d --no-deps --no-build --wait` for five app services; `scripts/verify_release.py` against 232923 baseline (passed). Compile, Compose configuration and diff checks passed. See the delivery report for exact images and limitations.


## 2026-10-07 23:48 Maldives — crawler runtime candidate, not deployed

Read-only exact-image inventory classified 22 critical rules as historical project metadata locations and three as installed OS components. No findings suppressed. Python 3.11 runs the supervisor; FFmpeg/TIFF remain installed. Added scripts/crawler_runtime_inventory.py with image-match guard and credential-free inventory. Report: reports/crawler-runtime-triage-2026-10-07.md/.json.

Disposable apt purge simulation passed. Built a candidate moving supervisor to Python 3.12 and removing Python 3.11. First invocation used a build config digest instead of Docker image identity and stopped; corrected identity then exposed supervisor 4.2.5 pkg_resources startup failure. Diagnostics captured privately; resources cleaned. Updated to upstream supervisor 4.3.0. Corrected image e208621bb2acb45e169712f4e5782245b486f5e3ad63e03563a65a76917d58b8 passed full real extraction/restart/auth/config matrix with retained app 762a461c255a. No production mounts, ports or model calls. Compile/diff checks passed.

Automatic approval review rejected Docker Scout because image metadata may be sent externally without specific authorization; no workaround or deployment attempted. Next: obtain approval for external scan, audit exact candidate and bundled Node/forked dependencies, integrate passing build into maintained Dockerfile before rollout. Current production remains 35eabc8e6da1. FM-09 remains partial; AI paused.


## 2026-10-08 00:01 Maldives — official crawler image pulled

User requested latest Crawl4AI pull. `docker pull unclecode/crawl4ai:latest` completed successfully after a slow multi-layer download. Exact digest/image: sha256:9021b3cb5c6f12570bbcd5395638495e0a06969b3148e377b953d174af2ebc9b. Offline disposable package inventory confirms Crawl4AI 0.9.4 / Python 3.12.14. Existing production crawler remains healthy on custom image 35eabc8e6da1; no replacement performed. Next: run the existing modern API/extraction/restart matrix on this official candidate, review differences and approved advisory scan before deployment. Earlier external Scout approval request remains unresolved.


## 2026-10-08 10:15 Maldives — new official base tested, rollout pending

The newly pulled official image `sha256:9021b3cb5c6f12570bbcd5395638495e0a06969b3148e377b953d174af2ebc9b` contains Crawl4AI 0.9.4 / Python 3.12.14. Real application raw extraction, Unicode, absolute citations, active-resource stripping and restart passed. Its authentication matrix failed: a correctly signed JWT with no expiration returned HTTP 200 rather than the required 401. This does not mean an unsigned or forged token was accepted. The matrix stopped at that failure, so later cases are not claimed to pass. The official image also includes PyJWT 2.10.1 and the Debian Python 3.11 supervisor runtime. It was not deployed.

Updated the maintained `infra/crawler/Dockerfile` to the pinned new upstream base, retaining the matching reviewed server/source provenance, JWT expiration requirement and tested dependency pins. Added Supervisor 4.3.0 on Python 3.12 and removed the duplicate Debian Python 3.11 packages. Retained the reviewed non-root runtime and matching browser shell. Previous experimental Dockerfile remains historical evidence rather than the production build recipe. Supervisor's removal of the legacy pkg_resources dependency is documented in [upstream release notes](https://pypi.org/project/supervisor/).

Exact candidate `sha256:3e099e0a5b4ab2eb7c8e20d64be06d34ab626f4f36a2ec450f01e1d4bb1b7745`, tag `forgetfulme-crawler-test:20261008-official-base`, passed the full existing modern server matrix with app `forgetfulme-test:762a461c255a`: real extraction before/after restart; absent/invalid/expired/no-expiration JWT rejection; scoped admin route checks; metrics/MCP/monitor authentication; forbidden JavaScript/base_url/proxy/file/private destinations; environment-config disclosure rejection; active dependency and warning checks. Offline runtime verification confirms Python 3.12.14, Supervisor 4.3.0, successful supervisor import and absence of `/usr/bin/python3.11`. All fixtures used synthetic content/credentials, internal disposable networks, no live mounts/published ports/providers. Test resources were cleaned. Matrix now labels authentication failures without printing tokens. Compile and diff checks passed.

FFmpeg 5.1.9 and TIFF 4.5.0 Debian libraries remain installed. The previous critical counts must not be reused as a fresh scan of this image. Bundled browser Node and unclecode-litellm code/advisory review also remain incomplete. Removing Python 3.11 does not establish that all runtime risks are cleared.

The previous automatic approval rejection of Docker Scout metadata transmission remains unresolved; no scan workaround or new external scan was attempted. The candidate has no fresh external advisory report and is not deployed. Current crawler remains 35eabc8e6da1; app/services/notes/settings and AI pause are unchanged. No fresh deployment backup was taken because no rollout occurred.

Next prerequisite: user authorization for sending this candidate's package/image metadata to Docker Scout. Then scan exact candidate, triage remaining runtime/fork/binary findings, save fresh private baseline and deploy only a passing accepted candidate. Continue desktop copied-state cross-version/interactive recovery and archive image/state compatibility separately. FM-07/09 remain partial.

Commands: modern_crawler_check.py for official image (failed missing_expiration 200, extraction/restart passed), docker build from maintained infra/crawler/Dockerfile (passed), modern_crawler_check.py for exact 3e099 candidate (full matrix passed), offline interpreter/supervisor/OS inventory (passed). Reports: official-crawler-check-2026-10-08.json, new-base-crawler-check-2026-10-08.json, new-base-crawler-runtime-2026-10-08.json. No app source changes; no full 20-script rerun required for this companion-only candidate.
