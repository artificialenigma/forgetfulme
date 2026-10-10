# Forgetful Me — project plan

Last updated: 2026-10-07 (Indian/Maldives, UTC+05:00).

This is the source of truth for confirmed project decisions. Conversation history and completed work are recorded in `WORKLOG.md`. Proposed details remain pending until agreed.

## Current state and next upgrades — 2026-10-07

The app now implements browser-history ingestion/import/export, public-page capture, the stack-owned Obsidian vault, local-vault ZIP import, configurable AI providers/model discovery, and a unified local knowledge library with section search, provenance, review/project/exclusion preferences, connections, research questions and vault diagnostics. The dated sections below preserve earlier decisions and proposals; statements such as “not implemented” in those historical sections describe their earlier milestone, not current functionality.

The user subsequently authorized implementation and a resumable checklist. [UPGRADE_CHECKLIST.md](UPGRADE_CHECKLIST.md) records the live execution checkpoint; [UPGRADE_PLAN.md](UPGRADE_PLAN.md) defines the full backlog; [AI_AGENT_HANDOFF.md](AI_AGENT_HANDOFF.md) provides continuation context. The first delivery addresses evidence boundaries, identity/citation/indexing foundations and metadata fidelity. Check the checklist/worklog for actual passed checks and deployment state; the full backlog is not yet complete.

Recommended order: evidence lineage/exclusions; stable document identities, revision citations and protected publication; resilient indexing/source jobs; metadata and multilingual extraction; PDF text/page citations; explicit ingestion controls; measured retrieval; project/research UI; reproducible dependency updates and recovery throughout. The first delivery is FM-01. Current code and outstanding uncommitted changes are the implementation baseline. Runtime settings and Docker health must be rechecked before future changes; the last recorded deployment state is history, not a fresh assertion.

## Confirmed purpose

Collect browsing history across browsers and devices, store it centrally, and provide a feature to export all collected data to Obsidian.

## Confirmed architecture

The product has two main parts:

1. A Docker stack containing a reverse proxy, database, and webapp. The application receives and stores data sent by browser plugins and provides the Obsidian export feature.
2. Browser plugins/extensions for Chrome and Safari that push browsing data to the application.

The initial Docker implementation uses Caddy, PostgreSQL 17, and Python/FastAPI. Browser ingestion API contracts and browser/device platform coverage remain undecided.

## Confirmed deployment lifecycle

- Initial development and testing run locally on the user's device.
- After local testing, the Docker stack moves to a server, where it will reside permanently.
- The final design must support browser data arriving from multiple devices at that server.

## Obsidian integration — stack-owned vault

Connectivity check on 2026-10-04: a registered local Obsidian vault exists and has readable/writable host permissions, but the Docker stack has no vault mount or implemented API/export connection. No vault write was attempted. Host availability does not establish container connectivity.

The Docker application must provide a feature to export all collected data to Obsidian. The user requested Obsidian inside the stack with its vault inside the application. The implementation adds a LinuxServer Obsidian desktop behind the app login at /obsidian/, embedded at /vault, with no directly published desktop port. A new named-volume vault is shared with the worker and mounted read-only by the webapp; settings use a separate volume. Initialization creates a welcome note and registers the new vault without modifying or importing the user's existing local vault. Both volumes are included in scheduled backups. Automatic history and Archive Desk exports remain pending.

The stack-owned vault and settings can move with the server through backup/restore. Remote desktop use requires HTTPS; local HTTP works at localhost. Synchronization with a separate local Obsidian installation has not been selected.

## Proposed details awaiting agreement

- Record URL, page title, visit timestamp, browser, and device identity.
- Provide searchable browsing history in the webapp.
- Authenticate and pair browser installations with the server.
- Queue data while offline and retry without duplicating visits.
- Provide collection pause controls, site exclusions, and history deletion.
- Track Obsidian export progress and retry failures.

These are discussion proposals, not committed scope.

### Proposed collection approach (2026-10-04)

- Separate visit metadata collection from optional page-content extraction.
- Chrome: use the history API for existing-history import and new visits; use content scripts for permitted loaded-page extraction.
- Safari: validate supported APIs on the selected platforms and versions before committing to historical import; plan to capture new visits and permitted loaded-page content.
- Extract readable main content and available metadata, accounting for dynamic pages and recording extraction failures.
- Send authenticated batches from a persistent local queue with stable event IDs; keep repeat visits separate from content snapshots.
- Proposed default: collect history metadata and enable content capture for selected sites or explicit saves. Exclude private browsing, blocked sites, credentials, and form inputs.
- Historical links alone do not preserve the content that existed at the time of the visit.

This proposal awaits agreement; no collection code has been implemented.

### Proposed Docker additions (2026-10-04)

For the first version, add a background worker for extraction, indexing, and Obsidian export; a scheduler for recurring jobs; persistent storage for captured content; and scheduled backups with restore checks. A database-backed job queue can keep the initial deployment small, with a separate broker added if the selected framework requires it. PostgreSQL with built-in full-text search is a proposed database choice, not a confirmed selection.

For server deployment, consider an uptime monitor and optional search service such as Meilisearch if search requirements exceed the initial database search. Object storage may be useful if attachments and snapshots grow beyond simple file volumes. A browser-rendering worker and AI enrichment are optional later additions, dependent on content-capture scope and resource requirements. Server fetching cannot reproduce a user's authenticated browser session by default.

Pairing, per-device credentials, exclusion settings, export progress, and failed-job retry controls belong in the application. Additional containers do not replace these features. None of these additions are approved scope yet.

### Optional Archive Desk companion

Added `compose.archive.yaml` with an opt-in `archive` profile, building from the sibling `internetarchivemanager` checkout (configurable through `ARCHIVE_DESK_PATH`). Archive Desk provides Internet Archive/HathiTrust book inspection, permitted reader-page export as PDF/image ZIP, OCR, and its own Chromium/noVNC login session. Its original source and provider access checks remain unchanged.

The companion has local-only ports 8766 and 6080, its own internet-enabled network, health check, and persistent browser/export volume. It does not have access to the database network. This integrates service management only; database records, dashboard controls, and Obsidian export integration are still pending. Its state is not yet covered by the existing backup service, and queues are not persistent. Remote server use needs gateway authentication, host/origin handling, and a protected browser interface; the current companion is local-only.

## Open decisions

### Optional MinerU parsing service

Reviewed MinerU 4 and added `compose.mineru.yaml` as an optional NVIDIA-server deployment template with the `mineru` profile. It provides the V1 API, GPU selection, local pre-downloaded models, a private worker/parser network, read-only captured-content access, and persistent workspace. The worker endpoint setting is prepared; parsing jobs, result retrieval, and vault exports are not implemented.

The current Docker engine is ARM64 on macOS and cannot run the documented NVIDIA deployment. Official MinerU 4 non-NVIDIA Docker guidance is pending. Configuration validation passed, but no MinerU image was built or started here and no inference was tested. A compatible GPU server or separately validated native macOS/CPU setup must be selected before runtime deployment. Suggested workflow: Archive Desk PDF/uploaded document → MinerU Markdown/assets → worker → stack-owned Obsidian vault.

- Which operating systems and device types must Chrome and Safari support?
- Should plugins import existing browser history, collect new visits, or both?
- Should the archive contain history metadata only or saved page content as well?
- How should browsing records and Archive Desk exports be formatted and delivered into the shared stack-owned vault?
- What Markdown structure should exports use, and should export be manual, automatic, or both?
- What authentication, retention, and exclusion rules are required?
- What server environment will host the production deployment?

## Documentation maintenance

- Append project conversations and completed work to `WORKLOG.md` as work continues.
- Update this file when decisions are confirmed or revised.
- Keep tentative suggestions separate from confirmed plans.
- Record decision changes in the worklog so the reasoning remains available.
- Commit and push completed project changes afterwards, as requested by the user.

## Current status

The user requested the Docker stack first. The initial implementation includes:

- Caddy reverse proxy, loopback-only ports for local testing, and configurable HTTPS domain for server deployment.
- PostgreSQL with persistent storage and one-shot schema initialization.
- FastAPI webapp/API foundation with an authenticated stack-status dashboard and public health endpoints.
- Browser login uses an HTML form and signed eight-hour HttpOnly/SameSite session cookie, with CSRF checks and Secure cookies over HTTPS. Basic authentication remains available for API checks.
- Dashboard presentation includes service and job summary cards, service health details, the latest eight maintenance jobs, a manual refresh link, responsive navigation/layout, and Maldives-time timestamps. It displays actual database records; browsing features remain marked as planned.
- Database-backed job queue, worker, and scheduler executing periodic maintenance jobs with heartbeat checks.
- Scheduled database/content backups, retention, retry behavior, and a smoke test that restores a dump into a disposable database.
- Private generated local credentials, pinned Python dependencies, bounded logs, and startup health dependencies.
- Local startup, backup/restore, and server migration instructions.

The Docker stack is implemented. Browser extensions, history ingestion/search, page extraction, and Obsidian delivery remain future work. The content volume is reserved for future captures. Background jobs currently perform maintenance only. Local backup files must be copied elsewhere for protection from server loss.

## Browser collection implementation — 2026-10-04

- Per-browser revocable ingestion tokens, stored as SHA-256 hashes server-side; administrator sessions create/revoke tokens with session-bound CSRF protection.
- PostgreSQL devices and visits, unique device/event IDs, batches up to 100, URL/time validation, latest 200 visits in the webapp.
- Chrome MV3 extension: new local visits plus optional last-30-day import using history search/getVisits; minute alarms, persistent bounded offline queue, explicit opt-in, domain exclusions, server-specific optional permissions.
- Safari source: shared add-on with nonpersistent background script and new nonprivate completed tab-load capture when history API is unavailable. Existing Safari history import is unavailable. Native packaging/manual capture verification remain pending; local Xcode license prevents conversion.
- HTTPS for remote endpoints, loopback-only HTTP during local testing. Existing queue cleared when destination/token changes. No scraping or automatic Obsidian export in this collection milestone.

## File import — 2026-10-05

Add a signed-in Import history page accepting explicit CSV/JSON uploads (UTF-8, url/title/visited_at fields). Bound files to 4 MiB and 10,000 rows, validate all rows before the database transaction, and reject invalid URLs/timestamps. Named import sources use deterministic IDs and cannot authenticate ingestion; hash normalized UTC timestamp plus URL for repeat-import deduplication within that source. Show inserted/skipped counts and link to history. Browser database and vendor-specific export parsing are outside this import format; Chrome’s add-on importer remains available. Overlap with extension event identities can produce duplicates.

## Browser sign-in navigation — 2026-10-05

Protected browser pages redirect missing/invalid sessions to login and carry an allowlisted return destination. Protected mutations continue rejecting unauthenticated requests. Use a consistent hostname for the app and login because cookies are host-scoped.

## Import upload size — 2026-10-05

Accept history files up to 100 MiB, with 64 KiB multipart overhead allowance. Reverse proxy permits 105 MB requests. Retain the 10,000-visit limit.

## Safari history JSON — 2026-10-05

Accept Safari history schema version 1 with metadata and history arrays. Convert integer Unix time_usec to UTC using exact microsecond arithmetic, handle missing titles, and retain existing file/row validation and source-level deduplication. One record per exported entry; aggregate counts, load-failure flags and redirect metadata are not retained. ZIP archives and Safari database files are not accepted by this JSON importer.

## Large history imports — 2026-10-05

Raise the file import entry limit to 1,000,000 while retaining the 100 MiB byte cap. Validate before saving, stage entries using PostgreSQL COPY, then insert with conflict deduplication in the same transaction. Distinguish empty exports from oversized exports and show the actual count when oversized.

## Safari invalid entries — 2026-10-05

Add an explicit checkbox (checked by default) allowing invalid Safari records to be skipped. Return exact invalid-field reasons, a skipped count and first 20 entry numbers without exposing URLs. Strict mode rejects the entire export; CSV/generic JSON remain strict. Validate all records before a single atomic save of accepted visits. Reject files without any valid visits.

## History presentation — 2026-10-05

Use a dedicated responsive history page, bounded title/URL text, named sources, Maldives timestamps and stable 50-entry pagination. Mobile layout prioritizes page and visit time; desktop shows source as well.

## Obsidian delivery — 2026-10-05

Worker exports pending visits every ten seconds, at most eight date/ID groups per pass. Each note holds at most 1,000 visits, contains escaped Markdown title/link, timestamp and source, and resides in the managed Forgetful Me/Browsing History/YYYY/MM folder. Atomic note replacement precedes exported_at updates in a transaction; failures retry. Existing visits are backfilled automatically. History page and API expose exported/pending totals. Personal annotations belong outside managed files.

## Page content scraping — 2026-10-05

Queue all existing and new visit URLs for durable per-URL capture, excluding fragments from identity. Worker attempts one page per cycle, with row locks, state/attempt/backoff tracking and authenticated manual failed-page retry. Fetch public HTTP(S) only with validated/pinned DNS addresses, certificate verification, redirect revalidation, robots checks, bounded bodies/time and no cookies. Use pinned Trafilatura Markdown extraction; atomically save managed Pages notes. Preserve history indexes. Report unsupported/private/robots/unreadable/auth-required pages as blocked and transient errors as retry/failed. No browser-session replay or PDF/MinerU processing in this milestone.

## Crawl4AI service reuse — 2026-10-05

Reuse the existing crawl4ai container (installed 0.8.6) on a dedicated network shared with the worker. Keep guarded fetching in the worker; send resource-stripped raw HTML to the local /crawl API for Markdown extraction with JavaScript off. Record extractor in page capture status and notes; fall back to Trafilatura on errors. Private .env selects endpoint and optional API token. Provide a validated, unstarted optional Compose service pinned to the tested API for server deployment. Browser-driven JavaScript crawling is not enabled by this extraction adapter.

## Unified app UI — 2026-10-05

Use one dashboard-based app shell and stylesheet for every authenticated page, including result/error pages and the vault wrapper. Shared navigation covers Overview, History, Devices, Import, Page scraping and Vault with active-state labels; common typography/forms/tables/buttons and Maldives times. Login shares visual tokens/components without exposing authenticated workspace navigation. Embedded Obsidian remains its own desktop inside the shared frame.

## Capture table presentation — 2026-10-05

Present capture results in fixed page/status/result columns with semantic headers, hostname links, bounded URL previews, colored statuses and readable saved-note/error descriptions. Show full URL/path via hover text, keep mobile columns readable through horizontal scrolling, and retain shared layout/styles.

## 2026-10-06 — Obsidian linked knowledge layer

Approved provider: **local Ollama**. Adapt the source/wiki separation, native wiki links, source attribution and reviewed-note protection from gd4ai/obsidian-llm-wiki. Implement it in Forgetful Me’s backend and shared Docker vault.

- Preserve existing captures and history. Organize copied raw captures, linked source records, paginated source/website/history indexes, concepts and entities; expose a Home note and shared app navigation.
- Run local synthesis in a separate `wiki-worker`, using configurable host Ollama and Qwen 2.5 3B initially. Capture processing remains independent. Bound synthesis to 18,000 characters and validate concept/entity evidence quotations; label output as drafts.
- Preserve generated notes with `reviewed: true` and all files without the app ownership marker.
- Provide authenticated, CSRF-protected queued Q&A with bounded lexical retrieval over compiled summaries and answers grounded in up to three source excerpts. Save cited answers to the vault.
- Keep the database/vault backed up by the current stack. When moving to a server, install/reach Ollama there, configure its private URL/model, and back up model files separately.
- Advanced graph retrieval, global consistency checks and full-vault reasoning remain future work.

## 2026-10-06 — In-app AI configuration

Add authenticated, CSRF-protected AI settings for one active Ollama or OpenAI-compatible provider: base URL, model, encrypted API key, temperature, output tokens, Ollama context size and processing toggle. Persist in PostgreSQL; apply at the next job without restarting Docker. Save/test queues a synthetic JSON test through the wiki worker. Changing endpoint clears old credentials, redirects are refused, and failed summaries can be requeued. Cloud processing follows the selected endpoint; native non-compatible APIs need a compatible gateway. Administrator-password changes require re-entering stored provider keys.

## 2026-10-06 — Clean personal vault and local-vault import

User requested clearing gibberish, then directed stopping downloads and leaving browsing uploads for later, followed by requesting a clean vault and importing/copying a local vault. Clear stack note content only after verified vault/database backups; preserve desktop configuration and existing browsing records. Retire old capture exports, pause vault automation persistently and pause AI. Do not rebuild old notes.

Provide an authenticated, CSRF-protected ZIP import for notes/folders/attachments with no overwrite, hidden metadata exclusion, path/symlink checks and size/count limits. Offer Docker folder copy for large vaults. Import must not enable downloads or AI; personal imported notes must remain user-owned. Future generated archives use readable source filenames and simple indexes, with automatic concept/entity expansion disabled.

## 2026-10-06 — Model discovery from provider base URL

Add Save and fetch models to AI settings. Persist connection details and pause AI during discovery, queue a bounded GET catalog request in the wiki worker, and offer the returned IDs in a selector alongside manual model entry. Use Ollama /api/tags or compatible /models, authenticate with the encrypted key, refuse redirects, limit response/list sizes and invalidate catalogs when endpoint/credentials change. Discovery must work while vault processing is paused and must not download models or transmit notes.


## 2026-10-06 — Proposed upgrade backlog and agent handoff

Created a dependency-ordered, testable upgrade plan after the seven vault improvements. Local code inspection identifies concrete follow-up gaps in derived-answer scope filtering, path-based identities, citation revision retention, stale summaries after recapture, publication conflicts/starvation, and index failure handling. The plan defines acceptance criteria, update/recovery checks and a first implementation task. No new app behavior, dependency updates or Docker deployment were executed by this planning request. See UPGRADE_PLAN.md and AI_AGENT_HANDOFF.md for the proposed work; WORKLOG.md records the planning evidence and limitations.


## 2026-10-06 — First upgrade delivery checkpoint

Implemented and deployed FM-01 evidence boundaries and FM-04 extraction fidelity,
with stable IDs/citation snapshots/rename journals, resilient scan/publication
jobs, recapture revision handling and disposable release validation foundations.
The full 12-script isolated suite passed; all four live app services match the
tested image, all 1,200 original visible source files and settings were preserved.
FM-02/03/07/09 remain partial; FM-05/06/08 remain pending. Resume from
UPGRADE_CHECKLIST.md at FM-02 strict versioned publication/conflict recovery;
WORKLOG.md records validation and exact image/source identity.

## 2026-10-07 — Second upgrade delivery checkpoint

The second delivery is tested and deployed (18 disposable scripts, five healthy exact-source app services). FM-01/04/05/06 are complete; FM-02/03/07/08/09 remain partial. Immutable publication, separate local indexing, selected PDF page extraction, ingestion policies, measured retrieval and project/reading workflow are delivered. DB/vault restore and Python advisory audit passed. Publication action/recovery acceptance now passes. Resume UPGRADE_CHECKLIST.md's rename impact/recovery tasks; broader failure UI, populated visual QA and full-stack recovery remain.

2026-10-07 follow-up: publication POST/reconciliation fixtures passed; reviewed proposals cannot activate, symlink proposals return conflict. Exact-image Docker rollout and fresh baseline are recorded in UPGRADE_CHECKLIST.md. Next: rename repair impact/collision previews and remaining recovery coverage.

2026-10-07 filename follow-up: inbound relationship/collision preview and content-bound approval are deployed. Broader rename recovery/retention coverage and detailed failure workflows remain; see checklist for exact candidate.

2026-10-07 recovery follow-up: bounded no-follow rename reconciliation and paginated job/error/rename retry controls deployed. Large-corpus index interruption/restart and final retention/acceptance audit remain; use the latest checklist checkpoint.

2026-10-07 acceptance checkpoint: FM-01–06 complete; FM-07/08/09 partial. Nineteen isolated scripts pass including actual 1k scan SIGKILL/restart and concurrent publication review. Content/config offline restore passed; matched runtime/credential recovery remains. Next action is in UPGRADE_CHECKLIST.md.

2026-10-07 matched recovery/display delivery: one scheduled four-archive set passed forward migration/original row preservation, restored FastAPI runtime and synthetic encryption compatibility. Generated navigation/history display labels/filter/counts now preserve evidence permissions. Remaining: populated visual/accessibility QA, AI answer evaluation while paused, OS/companion audit and actual desktop-runtime rollback.


2026-10-07 latest checkpoint: FM-01–06 and FM-08 complete; FM-07/09 remain partial. Ten populated responsive UI screens passed scoped checks. Unused pip removed from runtime; 19 tests passed and exact candidate b1258a3cddfe deployed/verified. Companion scans have high/critical findings; archive desktop image is absent locally and its OS audit is unavailable. Resume UPGRADE_CHECKLIST.md and reports/container-audit-review-2026-10-07.md before companion recreation. AI remains paused; model answer/abstention evaluation and actual desktop rollback remain outstanding.


2026-10-07 companion follow-up: patched Caddy proxy deployed after isolated real-config/auth/routing checks; no high findings in its final scan (three other entries remain). Backup service healthy after restart and fresh scheduled backup. Exact pinned PostgreSQL restore verified latest saved DB/vault; PostgreSQL tag unchanged. Archive candidate passed empty-state startup/restart only and remains undeployed with high/critical findings. Resume remaining database/desktop/crawler advisory and saved-state rollback work in UPGRADE_CHECKLIST.md; evidence in reports/companion-update-2026-10-07.md.


2026-10-07 database/desktop follow-up: tested PostgreSQL17.11 zlib correction deployed to database/backup (exact image 5fab158ded33); source/settings verification passed. Matched same-image Obsidian HTTP/process startup/restart and original source preservation passed on copied volumes. Obsidian candidate downloads timed out; current desktop and optional Crawl4AI digests pinned. Remaining: crawler/desktop/archive patches, cross-version/interactive rollback and paused model evaluation. Resume reports/database-desktop-checkpoint-2026-10-07.md and UPGRADE_CHECKLIST.md.


2026-10-07 crawler delivery: available Debian updates, PyJWT/urllib3 fixes and Requests-compatible chardet deployed after real extraction/restart and JWT-enabled API tests. Upstream overlapping jwt/PyJWT namespace repaired with a maintained auth adapter. Exact image e12f6af5ffe9; original launch configuration preserved and old crawler retained stopped for rollback. Notes/settings verification passed; scanner rules 995→771, critical 35→25. Next: Crawl4AI 0.9.0/anyio/nltk candidate tests, desktop cross-version recovery and archive compatibility. Read reports/crawler-delivery-2026-10-07.md and UPGRADE_CHECKLIST.md.


## Latest checkpoint — 2026-10-07 23:35 Maldives

Matching Crawl4AI 0.9.4 server/library and compatible app client are deployed. Twenty isolated scripts and the actual API/auth/config/restart matrix passed; all five app services are healthy. Original 1,201 sources and ingestion settings are preserved; AI remains paused. Direct crawler API access now requires a bearer token; the app receives its private token from ignored `.env`. Final crawler scan still contains 25 critical rules (768 total), requiring further artifact/runtime triage. FM-07/09 remain partial. Resume `UPGRADE_CHECKLIST.md` and `reports/modern-crawler-delivery-2026-10-07.md` for minimal-base/advisory work, desktop cross-version recovery and archive image/state compatibility. Earlier dated entries are historical.


Latest continuation (2026-10-07 23:48 Maldives): read-only crawler triage recorded 22 critical rules in historical metadata and three in installed OS components; no exploitability clearance. Experimental Python 3.12 supervisor candidate e208621bb2ac passed the full extraction/restart/auth matrix and removes Python 3.11. It is not deployed. Automatic approval review blocked external Docker Scout metadata transmission; next prerequisite is explicit scan approval, then bundled Node/fork review and maintained-build integration. See reports/crawler-runtime-triage-2026-10-07.md and WORKLOG.md. Production and AI pause remain unchanged.


Latest continuation (2026-10-08 10:15 Maldives): official 0.9.4 image extraction/restart passed but no-expiration JWT acceptance failed. Maintained crawler build now uses the pinned new official base plus existing auth/dependency fixes and Supervisor 4.3.0 on Python 3.12.14; duplicate Python 3.11 removed. Exact candidate 3e099e0a5b4a passed the full modern API/extraction/restart matrix, but remains undeployed awaiting explicit Docker Scout metadata transmission approval and fresh scan. Remaining FFmpeg/TIFF, browser Node/fork advisory review and desktop/archive recovery stay open. Production and AI pause are unchanged. Resume reports/new-base-crawler-continuation-2026-10-08.md.
