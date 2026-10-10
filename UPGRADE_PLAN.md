# Forgetful Me upgrade plan

Prepared: 2026-10-06, Indian/Maldives (UTC+05:00).
Status: implementation authorized by the subsequent request to work on the upgrade and keep a resumable checklist. See UPGRADE_CHECKLIST.md for the live checkpoint and WORKLOG.md for evidence. The backlog below is the full intended scope; partial deliveries stay explicitly incomplete.

## Current baseline

The current checkout implements the seven vault improvements: unified local note/section search; origin/type/tag/project/review filters; provenance and line views; capture-quality checks and per-URL controls; research questions and suggested connections; health diagnostics and Unicode filename recovery; shared navigation and knowledge metrics. Imported Markdown is indexed locally without invoking AI. AI Q&A requires a chosen evidence scope. Selected PDFs now have bounded local text extraction and page citations; indexing runs in a separate library worker. See UPGRADE_CHECKLIST.md for deployed evidence and remaining acceptance tasks.

The preceding deployment was verified healthy with all five app services matching the checkout. It preserved 1,200 visible imported file contents and indexed 356 visible imported Markdown notes. Archive automation was enabled and AI was disabled at that check. These are historical observations, not current runtime assertions; reread settings and health before implementation or deployment. The checkout contains uncommitted implementation work: preserve it and inspect the diff before editing.

Sources: `reports/vault-product-analysis-2026-10-06.md`, `WORKLOG.md`, `app/library.py`, `app/library_routes.py`, `app/wiki.py`, `app/wiki_worker.py`, `app/page_scraper.py`, `app/init_db.py`, and `compose.yaml`.

## Delivery order

| ID | Priority | Deliverable | Depends on | Status |
|---|---|---|---|---|
| FM-01 | P0 | Evidence scopes and immediate exclusion | Current baseline | Complete — checklist evidence |
| FM-02 | P0 | Stable document identities, revision citations and recoverable renames | FM-01 scope model | Complete — acceptance report |
| FM-03 | P0 | Resilient incremental indexing and observable jobs | FM-02 identity model | Complete — acceptance report |
| FM-04 | P1 | Reliable metadata, code-preserving chunks and multilingual matching | FM-03 | Complete — checklist evidence |
| FM-05 | P1 | Local PDF text extraction and page citations | FM-01–04 | Complete — checklist evidence |
| FM-06 | P1 | Explicit ingestion policies and queue controls | FM-01, FM-03 | Complete — checklist evidence |
| FM-07 | P1 | Retrieval benchmark and answer-quality improvements | FM-02, FM-04; extend after FM-05 | Partial — benchmark recorded |
| FM-08 | P2 | Project workspace, question workflow and usable health tools | FM-02, FM-03, FM-07 | Partial — workflow deployed |
| FM-09 | P1 | Reproducible dependency updates, deployments and recovery | Apply from first delivery | Partial — each delivery |

FM-09 supports every delivery; it is not postponed until the end. Split each item into small, reviewable changes. Stabilize FM-01–03 before increasing extraction throughput or adding semantic retrieval. A disposable test database and vault with injectable connection settings are a prerequisite for FM-01 regression reproduction, supported by FM-09; do not substitute the live catalog with a rolled-back test transaction.

## FM-01 — Evidence scopes and immediate exclusion

**Observed gap:** `inspect_note` assigns archive origin to every `Forgetful Me/` path. `answer_one` saves answers based on imported-note evidence under `Forgetful Me/wiki/queries`, while archive-only retrieval checks only the path-derived origin. An answer derived from personal notes can therefore re-enter a later archive-only prompt. An imported file placed beneath that prefix can also be misclassified. Answers have no persisted evidence-scope lineage in their frontmatter. Capture exclusions and per-note overrides are also independent controls.

**Change:** Separate display origin from allowed evidence scope. Track parent source/document IDs and effective scope for derived content. Until lineage is complete, keep generated answers and connection/index notes out of AI evidence by default. Make scope filters and source exclusion checks apply before excerpts are sent, including already queued questions. Propagate capture exclusions to every derivative through source identity rather than current file paths. Keep local search and outbound AI permissions distinct; do not infer consent from a folder name.

**Acceptance:**
- An all-scope answer using an imported secret fixture never enters a subsequent archive-only provider prompt. An imported fixture beneath `Forgetful Me/` remains imported regardless of its path.
- Excluding a source prevents its raw capture, summary and derived excerpts from outbound processing; inclusion is explicit and does not automatically requeue downloads.
- Paused background AI sends no content inference requests. An explicitly requested provider connection test may send only its synthetic test prompt. Indexing/search continue locally. Scope selection remains explicit on the request.
- Provenance and scope are recorded on saved answers, with migration handling for historical answers whose lineage is unknown.

## FM-02 — Stable identity, revision citations and recoverable renames

**Observed gap:** Library records, overrides and connections use paths as identity. Research-question IDs include the path. Filename repair moves the file and updates only its override, leaving connections, question state and old citations at risk. Chunks are deleted/recreated on reindex; answers link to line numbers in the current file without preserving the cited revision. Recapture can retain completed `ai_state` and old `wiki_data`, making an old summary appear current after source content changes. `atomic_note` checks protection before replacement but can miss a human edit/review change between those steps.

**Change:** Introduce an immutable document ID, path history and content revisions. Retain exact cited excerpts, document/revision IDs, section/page coordinates, and hashes in answer citations. Support current-file navigation while clearly showing when the cited revision differs. Use a durable operation journal for rename/connection export steps that span PostgreSQL and the filesystem; make recovery idempotent. Do not claim an ordinary database transaction makes filesystem writes atomic. Bind summaries to source revisions: changed content invalidates the current summary and queues a new draft, while reviewed content stays intact with a pending-update indication. Use explicit parsed ownership and conflict detection for generated-note publication; retain an alternate draft instead of overwriting a changed protected destination.

**Acceptance:**
- Rename, move, rescan and worker restart preserve review/project/exclusion preferences, accepted connections and question resolutions.
- Old answers still show the exact cited excerpt after a source edit, rename or deletion; the viewer identifies a changed or unavailable current file. Retention/cleanup jobs preserve cited revisions.
- Destination conflicts never overwrite files. Failure between filesystem and database steps is detected and can be retried safely.
- No merge is inferred solely from identical content; duplicate independent notes remain independently owned.
- Changed recaptures invalidate the current summary; unchanged content avoids redundant AI calls. Previously reviewed summaries remain byte-identical and visibly tied to their old revision.
- A fixture human edit/review toggle inserted during publication is preserved with a visible conflict. Imported files, symlink targets and malformed ownership markers are never treated as replaceable app notes.

## FM-03 — Resilient indexing and observable jobs

**Observed gap:** `scan` processes the complete catalog in one transaction. It does not isolate a file disappearing or becoming unreadable mid-scan. Its final deletion treats unobserved paths as absent, without proving the vault was mounted and the traversal completed. Manual refresh requests a scan but unchanged fingerprints still skip parsing. Worker errors are reduced to a generic message; success time does not describe pending work or failures. Source publication repeatedly selects the oldest 20 rows and skips missing/protected raw notes without advancing them; sufficient skipped rows can starve newer work. It ignores a source-record write failure before marking the row indexed, and its returned count describes selected rows rather than successful publication.

**Change:** Validate the mount/root, track completed scan generations, and delete catalog entries only after a successful complete enumeration. Isolate per-file errors and keep the last good revision. Read/fingerprint/hash one consistent snapshot or retry if its file changes during reading. Persist queued/running/succeeded/failed index jobs with counts and sanitized error categories. Offer separate incremental scan and full reindex controls. Keep local indexing independent of AI and download pauses, and prevent long work from starving heartbeats/Q&A. Give source publication explicit missing/protected/conflict/retry/succeeded states, bounded retry/defer behavior and truthful completion counts.

**Acceptance:**
- Missing mount, permission error, concurrent edit/delete and one malformed note do not wipe the catalog or stop unrelated notes from indexing.
- A full reindex reparses unchanged files and records the parser/index version.
- More than 20 missing/protected publication jobs ahead of valid jobs cannot starve valid jobs. Failed source-record writes never receive indexed-complete status.
- UI reports last successful scan, current progress, stale state and retryable failures without logging private text, URLs or keys.
- Fixture tests run against an isolated test database/catalog, rather than temporarily replacing the live catalog in a rolled-back transaction.

## FM-04 — Metadata, chunk fidelity and multilingual matching

**Observed gap:** Frontmatter parsing supports only a limited YAML subset. Generic HTML removal runs through code-containing text; angle-bracket code such as C includes can be lost. Word counting and query tokenization use different Unicode rules. Exact accent matching lacks an explicit alias/folding policy.

**Change:** Use a bounded safe metadata parser with clear handling of unsupported/invalid values; normalize fields without editing source notes. Preserve fenced code, tables and meaningful inline code while removing page data. Unify Unicode normalization for matching, diagnostics and statistics; preserve original spelling. Support deliberate title/alias matching and test accent variants. Retain section/line coordinates and explain extraction omissions.

**Acceptance:**
- Quoted colons, multiline/list metadata, CRLF, nested author/source fields and invalid YAML are handled predictably.
- `#include <stdio.h>`, generics, tables and fenced examples survive extraction and can be cited.
- Dhivehi combining marks, decomposed accents, `café`/`cafe` matching policy and non-ASCII aliases have documented tests.
- Chunks stay within an enforced budget, retain late evidence, and do not turn embedded page data into relevant matches.

## FM-05 — Local PDF extraction and page citations

**Observed gap:** The corpus contains valid research PDFs, plus a `.pdf` containing HTML. The current app only checks PDF signatures; those attachments cannot supply searchable evidence.

**Change:** Add an asynchronous local extraction pipeline for explicitly imported/selected PDFs. Validate signatures/content type, bound size/page count/runtime, preserve originals and retain text by page. Index derived text with parent identity and scope. Start with text PDFs; make OCR an explicit optional capability with resource limits. Evaluate the existing optional MinerU template and CPU extraction options before selecting an engine; do not install GPU services or download models by default. Expose failed extraction and retry states.

**Acceptance:**
- A synthetic text PDF returns a passage with the correct page citation; a scanned PDF reports OCR required when OCR is disabled.
- HTML disguised as PDF, corrupt/encrypted files and exhausted limits fail clearly without discarding originals.
- Imported PDF text remains in imported-note scope. Exclusion/review/revision rules apply to derived text.
- No cloud upload occurs during local extraction. Health shows what is searchable versus merely catalogued.

## FM-06 — Explicit ingestion policies and queue controls

**Observed gap:** Unique history URLs enter the capture queue automatically; one global automation switch governs downloads and history exports. Per-URL exclusions exist, but there is no shared server-side site policy, capture budget or complete queue control surface. URL history represents visits while content is fetched later.

**Change:** Add separate controls for visit storage, history export, page downloading, local indexing and AI processing. Provide save-selected/recommended-site modes, server-side domain rules, per-domain backoff/concurrency, bounded throughput and clear pause/resume/cancel/retry behavior. Add canonical source identity carefully: keep original visits and significant query parameters, and redact sensitive/transient URL parameters from exported/generated displays without silently changing evidence identity. Surface backlog size, success/blocked/failure reasons and fetch time versus visit time.

**Acceptance:**
- New imports do not change toggles or bypass domain exclusions. UI explains exactly which actions will run.
- Pausing downloads stops new fetches after bounded in-flight work, while permitted history export/indexing can continue.
- Per-domain rate/backoff limits are enforced; cancellation does not delete existing evidence or original visits.
- Auth/redirect/challenge pages stay excluded; credential-bearing URLs are not exported into new notes or logs.
- Reimporting history preserves repeat-visit records and does not unexpectedly revive explicitly excluded capture jobs.

## FM-07 — Measured retrieval and answer quality

**Observed gap:** Ranking is lexical, with a maximum of six sections/two per path for answers. The tests prove a narrow fixture, not recall or usefulness across the corpus. The first 24 candidates can be crowded by title-matched chunks from one long note before the two-per-path rule is applied, leaving too few distinct sources. Saved answers do not expose all retrieval choices or omissions, and no human-labelled benchmark establishes when semantic search is warranted.

**Change:** Build a small corpus-derived benchmark with frozen fixtures, expected evidence and deliberately unanswerable questions. Diversify retrieval across underlying sources, avoiding raw/summary duplicate evidence and generated-answer feedback loops. Allow optional project filters, an evidence preview, token budgeting and clear insufficient-evidence behavior. Save retrieval/model/extraction versions with answers. Evaluate semantic/hybrid search only after the baseline reveals missing recall; keep embeddings local by default and require separate approval for external indexing.

**Acceptance:**
- At least 20 representative questions cover Maldives reports, Game Boy code, ESP32 comparisons, source caveats, late passages, title crowding, duplicates, accents and Dhivehi. A title-heavy long note cannot crowd distinct relevant sources out of the context budget.
- Report evidence Recall@5, citation validity, scope violations, exclusion violations, abstention and latency. Proposed initial target: Recall@5 ≥80% on labelled fixtures; zero invalid citations/scope/exclusion violations. Record actual results, including failures.
- Expected-unanswerable questions do not invent evidence. Every citation resolves to retained revision/page/section coordinates.
- Report p50/p95 on reproducible 1,000- and 10,000-note fixtures; choose performance targets from the measured hardware baseline.

## FM-08 — Project and research workflow

**Observed gap:** Project assignment is a per-note text preference; questions require manually typed answer paths, and the page renders all questions. Suggestions use shared tags/projects but do not account for accepted connections. Health displays only the first 150 findings without pagination. The source viewer shows escaped Markdown rather than a full reading experience.

**Change:** Add project landing pages with saved filters, notes, sources, questions and recent reviewed changes. Provide a searchable answer-note picker, source-scoped Ask action, paginated open/resolved question views and question deduplication. Hide accepted suggestions; add remove/dismiss/retry/export status controls. Paginate health findings, persist dismissals with revision context, and preview repairs with collision/link impact. Add safe Markdown reading mode alongside raw line evidence and accessible mobile layouts.

**Acceptance:**
- A project can be followed from question to source to reviewed answer without typing paths.
- Accepted connections stop appearing as suggestions, can be removed, and remain consistent after rename/restart/export failure.
- Every health finding is reachable; ignored example links can be dismissed and reopened when the source changes.
- Keyboard, focus, labels, empty/error states and narrow-screen layouts pass direct signed-in browser checks. Report screenshots only if actually inspected.

## FM-09 — Updates, release and recovery

**Observed gap:** Multiple services share one local image tag; current Compose includes mutable third-party tags. Database/vault backups are present, but runtime settings and compatibility must be preserved through updates. Prior changes are currently uncommitted.

**Change:** Establish a release identity from source revision plus build metadata; build the shared app once and deploy that exact image to each service. Record image IDs, schema/index versions and dependency lock changes. Check supported versions and advisories using official upstream sources when performing an update; this plan does not claim particular versions are outdated. Upgrade dependencies in small groups and pin tested runtime images/digests where appropriate. Rehearse restoring database, content, vault and Obsidian configuration into disposable services, preserving credentials and ownership. Keep off-device backup/export configuration explicit.

**Acceptance:**
- Repeated migrations are safe. Tested data survives forward migration and documented recovery.
- Every running app file matches the delivered source; all five app services become healthy and expected toggles are preserved.
- Restore drill verifies usable notes, preferences, connections, question state, citations and extraction jobs.
- Release worklog records the actual source/image/schema versions, passed checks, limitations and recovery procedure.
- Do not run `docker compose down -v`, remove companion services, pull every `latest` image, or clean unrelated changes as a deployment shortcut.

## Definition of done for each delivery

A delivery requires a focused implementation, meaningful failure/success tests, relevant regression checks, explicit source-note preservation checks, current README/operator guidance and an appended worklog entry. When deployment is authorized, rebuild and recreate the changed app services, verify health and source/image identity, then report material limitations. Do not report planned or fixture-only behavior as live verified.

The current execution checkpoint is `UPGRADE_CHECKLIST.md`; the task log and continuation prompt are in `AI_AGENT_HANDOFF.md`. Historical completed work remains in `WORKLOG.md`.

2026-10-07 follow-up: publication POST/reconciliation fixtures passed; reviewed proposals cannot activate, symlink proposals return conflict. Exact-image Docker rollout and fresh baseline are recorded in UPGRADE_CHECKLIST.md. Next: rename repair impact/collision previews and remaining recovery coverage.

2026-10-07 filename follow-up: inbound relationship/collision preview and content-bound approval are deployed. Broader rename recovery/retention coverage and detailed failure workflows remain; see checklist for exact candidate.

2026-10-07 recovery follow-up: bounded no-follow rename reconciliation and paginated job/error/rename retry controls deployed. Large-corpus index interruption/restart and final retention/acceptance audit remain; use the latest checklist checkpoint.

2026-10-07 recovery acceptance: FM-02/03 complete, with actual 1k process-kill restart and requirement mapping in reports/recovery-acceptance-2026-10-07.md. Offline content/config volume restore passed; matched full-stack runtime/credential rollback, FM-07/08/09 refinements remain.

2026-10-07 matched recovery/display delivery: one scheduled four-archive set passed forward migration/original row preservation, restored FastAPI runtime and synthetic encryption compatibility. Generated navigation/history display labels/filter/counts now preserve evidence permissions. Remaining: populated visual/accessibility QA, AI answer evaluation while paused, OS/companion audit and actual desktop-runtime rollback.


2026-10-07 latest checkpoint: FM-01–06 and FM-08 complete; FM-07/09 remain partial. Ten populated responsive UI screens passed scoped checks. Unused pip removed from runtime; 19 tests passed and exact candidate b1258a3cddfe deployed/verified. Companion scans have high/critical findings; archive desktop image is absent locally and its OS audit is unavailable. Resume UPGRADE_CHECKLIST.md and reports/container-audit-review-2026-10-07.md before companion recreation. AI remains paused; model answer/abstention evaluation and actual desktop rollback remain outstanding.


2026-10-07 companion follow-up: patched Caddy proxy deployed after isolated real-config/auth/routing checks; no high findings in its final scan (three other entries remain). Backup service healthy after restart and fresh scheduled backup. Exact pinned PostgreSQL restore verified latest saved DB/vault; PostgreSQL tag unchanged. Archive candidate passed empty-state startup/restart only and remains undeployed with high/critical findings. Resume remaining database/desktop/crawler advisory and saved-state rollback work in UPGRADE_CHECKLIST.md; evidence in reports/companion-update-2026-10-07.md.


2026-10-07 database/desktop follow-up: tested PostgreSQL17.11 zlib correction deployed to database/backup (exact image 5fab158ded33); source/settings verification passed. Matched same-image Obsidian HTTP/process startup/restart and original source preservation passed on copied volumes. Obsidian candidate downloads timed out; current desktop and optional Crawl4AI digests pinned. Remaining: crawler/desktop/archive patches, cross-version/interactive rollback and paused model evaluation. Resume reports/database-desktop-checkpoint-2026-10-07.md and UPGRADE_CHECKLIST.md.


2026-10-07 crawler delivery: available Debian updates, PyJWT/urllib3 fixes and Requests-compatible chardet deployed after real extraction/restart and JWT-enabled API tests. Upstream overlapping jwt/PyJWT namespace repaired with a maintained auth adapter. Exact image e12f6af5ffe9; original launch configuration preserved and old crawler retained stopped for rollback. Notes/settings verification passed; scanner rules 995→771, critical 35→25. Next: Crawl4AI 0.9.0/anyio/nltk candidate tests, desktop cross-version recovery and archive compatibility. Read reports/crawler-delivery-2026-10-07.md and UPGRADE_CHECKLIST.md.


## Latest checkpoint — 2026-10-07 23:35 Maldives

Matching Crawl4AI 0.9.4 server/library and compatible app client are deployed. Twenty isolated scripts and the actual API/auth/config/restart matrix passed; all five app services are healthy. Original 1,201 sources and ingestion settings are preserved; AI remains paused. Direct crawler API access now requires a bearer token; the app receives its private token from ignored `.env`. Final crawler scan still contains 25 critical rules (768 total), requiring further artifact/runtime triage. FM-07/09 remain partial. Resume `UPGRADE_CHECKLIST.md` and `reports/modern-crawler-delivery-2026-10-07.md` for minimal-base/advisory work, desktop cross-version recovery and archive image/state compatibility. Earlier dated entries are historical.


Latest continuation (2026-10-07 23:48 Maldives): read-only crawler triage recorded 22 critical rules in historical metadata and three in installed OS components; no exploitability clearance. Experimental Python 3.12 supervisor candidate e208621bb2ac passed the full extraction/restart/auth matrix and removes Python 3.11. It is not deployed. Automatic approval review blocked external Docker Scout metadata transmission; next prerequisite is explicit scan approval, then bundled Node/fork review and maintained-build integration. See reports/crawler-runtime-triage-2026-10-07.md and WORKLOG.md. Production and AI pause remain unchanged.


Latest continuation (2026-10-08 10:15 Maldives): official 0.9.4 image extraction/restart passed but no-expiration JWT acceptance failed. Maintained crawler build now uses the pinned new official base plus existing auth/dependency fixes and Supervisor 4.3.0 on Python 3.12.14; duplicate Python 3.11 removed. Exact candidate 3e099e0a5b4a passed the full modern API/extraction/restart matrix, but remains undeployed awaiting explicit Docker Scout metadata transmission approval and fresh scan. Remaining FFmpeg/TIFF, browser Node/fork advisory review and desktop/archive recovery stay open. Production and AI pause are unchanged. Resume reports/new-base-crawler-continuation-2026-10-08.md.
