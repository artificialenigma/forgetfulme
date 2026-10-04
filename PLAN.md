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

## Obsidian integration — requirement confirmed, transport pending

The Docker application must provide a feature to export all collected data to Obsidian. The mechanism for delivering data to the vault has not been decided.

Local testing must not assume a shared local filesystem will also exist after server migration. Options discussed include a vault accessible to the server or an Obsidian plugin that retrieves records and writes them into a local vault. Neither option is approved yet.

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

## Open decisions

- Which operating systems and device types must Chrome and Safari support?
- Should plugins import existing browser history, collect new visits, or both?
- Should the archive contain history metadata only or saved page content as well?
- How will the server deliver data to the Obsidian vault?
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
- Database-backed job queue, worker, and scheduler executing periodic maintenance jobs with heartbeat checks.
- Scheduled database/content backups, retention, retry behavior, and a smoke test that restores a dump into a disposable database.
- Private generated local credentials, pinned Python dependencies, bounded logs, and startup health dependencies.
- Local startup, backup/restore, and server migration instructions.

The Docker stack is implemented. Browser extensions, history ingestion/search, page extraction, and Obsidian delivery remain future work. The content volume is reserved for future captures. Background jobs currently perform maintenance only. Local backup files must be copied elsewhere for protection from server loss.
