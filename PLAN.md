# Forgetful Me — project plan

Last updated: 2026-10-04 (Indian/Maldives, UTC+05:00).

This is the source of truth for confirmed project decisions. Conversation history and completed work are recorded in `WORKLOG.md`. Proposed details remain pending until agreed.

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
