# AI agent handoff — Forgetful Me

Prepared: 2026-10-06 (Indian/Maldives, UTC+05:00).

## Task scope

The user authorized working on the upgrade and requested a checklist that can always resume where work stopped. Implementation is active. Read **UPGRADE_CHECKLIST.md first** for the current checkpoint, actual validation and deployment status, then follow UPGRADE_PLAN.md. Two deliveries are deployed; current acceptance status is in the checklist. Do not re-request authorization for this upgrade; preserve settings and source notes.

## Read first

1. Applicable `AGENTS.md` instructions and current `git status --short` / `git diff`.
2. `PLAN.md` current-state notice and `UPGRADE_PLAN.md`.
3. The latest entries in `WORKLOG.md` and `reports/vault-product-analysis-2026-10-06.md`.
4. `README.md`, `compose.yaml`, `Dockerfile`, `app/init_db.py`, then the files for the chosen delivery.

Preserve the existing uncommitted changes. Do not reset, clean, overwrite or claim ownership of unrelated edits. Repository root is `/Users/fa-001524/Documents/protos/forgetfulme`. The reference host vault is `/Users/fa-001524/Documents/llm-wiki/llm-wiki`; the stack vault is the Docker volume mounted at `/vault`. The host vault is a reference source, not a directory to rewrite or synchronize automatically.

## Current design and important files

| Area | Files |
|---|---|
| Local indexing, Unicode matching, chunk search and health diagnostics | `app/library.py` |
| Library, note viewer, preferences, connections, question state and filename repairs | `app/library_routes.py` |
| Generated captures, summaries, evidence retrieval and saved answers | `app/wiki.py` |
| Local indexing/PDF queue and AI/publication scheduling | `app/library_worker.py`, `app/wiki_worker.py` |
| Guarded page fetch, extraction and capture jobs | `app/page_scraper.py`, `app/crawl4ai_client.py` |
| Visit ingestion, imports and capture controls | `app/browser_history.py`, `app/history_import.py` |
| ZIP imports | `app/vault_import.py` |
| Database migration | `app/init_db.py` |
| AI configuration and calls | `app/ai_provider.py`, `app/ai_routes.py` |
| Layout and metrics | `app/layout.py`, `app/dashboard.py`, `app/static/dashboard.css` |
| Runtime / backup | `compose.yaml`, `Dockerfile`, `scripts/backup.sh` |

Last verified deployment: app files matched all five containers; original imported contents were preserved; archive automation was enabled and AI was disabled. Recheck rather than relying on this historical state. Never print `.env`, stored keys, session tokens, provider responses or personal note contents into logs or handoff files.

## Current checkpoint — second delivery deployed

Read UPGRADE_CHECKLIST.md for release identity and acceptance boxes. FM-01–06 are complete; FM-07/08/09 remain partial. All 19 disposable scripts passed. Five deployed app services are healthy, all 40 app files match the tested image, 1,201 source originals and processing settings are preserved. AI remains paused. Database/vault restore and seeded state roundtrip passed; content/config offline restore passed; matched-set FastAPI/data and synthetic credential recovery passed; Obsidian/companion runtime rollback remains pending.

**Next action:** Read reports/new-base-crawler-continuation-2026-10-08.md. Official image failed the missing-expiration JWT check; corrected maintained-build candidate 3e099e0a5b4a passes. Obtain Docker Scout metadata transmission approval and scan exact candidate before rollout. Keep current live release and AI pause until all required checks pass.

Important new modules: `publication.py`/`publication_routes.py`, `connection_export.py`, `library_worker.py`, `pdf_extract.py`/`pdf_routes.py`, `ingestion_policy.py`/`ingestion_routes.py`, `retrieval.py`, `reading.py`. Local scanning/PDF work belongs to library-worker; wiki-worker handles AI/publication work.

## Worklog for the implementing agent

Append chronological evidence to WORKLOG.md. The checklist is authoritative for individual acceptance tasks. Existing failed attempts/disconnect entries are historical and must remain intact.

For each implementation entry, use:

```markdown
## YYYY-MM-DD — FM-XX: delivery title

**Request and scope:** Exact authorized task and relevant constraints.
**Starting state:** Branch/source revision, pre-existing changes, current service/settings state.
**Changes:** Concrete behavior, touched modules, schema/index version and source preservation.
**Validation:** Commands and meaningful cases, actual results, fixture versus live checks.
**Deployment:** If performed: exact image/source identity, migrations, health, settings preservation.
**Limitations / failures:** What remains incomplete, failure recovery and decisions needed.
**Next action:** One specific next task with prerequisite and status.
```

## Validation and deployment workflow

The image copies `app/` but not `scripts/`. The runner sends fixtures through
stdin. Mutating fixtures reject production defaults and validate a disposable
DB identity and vault marker. Do not run them in the ordinary production web
service or substitute its catalog inside a rolled-back transaction.

```sh
python3 -m compileall -q app scripts
git diff --check
python3 scripts/run_isolated_tests.py --check-config
python3 scripts/run_isolated_tests.py
```

The standalone harness validates networks/volumes/credentials, creates a unique
private fixture project, applies migrations twice, and runs 19 tests with paused
AI and fixture providers. It verifies app file hashes and unchanged source/tests
before PASS. It removes only that project's resources; the candidate image is
retained for exact-image deployment. A source/test change during a run requires
retesting the new candidate. Add meaningful new fixtures to the runner defaults.

For deployment under the existing upgrade authorization: save private backups
and a source/settings baseline, retag the **actual passing candidate image** as
`forgetfulme-app:local`, stop writers, run additive migration, recreate only
web/worker/wiki-worker/library-worker/scheduler and their required init dependencies. Do not
rebuild after testing, remove companion services, clear volumes or alter toggles.
Verify each service's exact image ID, all app-file hashes and health. Use only
read-only signed-in HTTP/status and source-preservation checks afterward; keep
mutating tests/providers in the disposable environment.

No private note text, keys, credentials, session tokens, provider responses or
unredacted private fixtures belong in docs/logs. Recovery needing schema restore
must be rehearsed in disposable services; switching image tags alone is not a
verified rollback procedure. Python advisories and DB/vault restore were checked; full-stack audit and matched runtime/credential recovery remain on the checklist.

## Continuation prompt

The user has authorized continuing the upgrade. Suggested continuation:

> Continue from UPGRADE_CHECKLIST.md and the latest WORKLOG.md. Preserve all uncommitted work, source notes and settings. The second delivery is deployed; resume companion advisory triage/tested updates, archive image recovery and desktop-runtime rollback review. Use disposable fixtures and synthetic providers. Update the checklist/worklog after each delivery and before stopping with the exact next action; deploy only the exact passing image and verify source/settings preservation under the existing authorization.


2026-10-07 latest checkpoint: FM-01–06 and FM-08 complete; FM-07/09 remain partial. Ten populated responsive UI screens passed scoped checks. Unused pip removed from runtime; 19 tests passed and exact candidate b1258a3cddfe deployed/verified. Companion scans have high/critical findings; archive desktop image is absent locally and its OS audit is unavailable. Resume UPGRADE_CHECKLIST.md and reports/container-audit-review-2026-10-07.md before companion recreation. AI remains paused; model answer/abstention evaluation and actual desktop rollback remain outstanding.


2026-10-07 companion follow-up: patched Caddy proxy deployed after isolated real-config/auth/routing checks; no high findings in its final scan (three other entries remain). Backup service healthy after restart and fresh scheduled backup. Exact pinned PostgreSQL restore verified latest saved DB/vault; PostgreSQL tag unchanged. Archive candidate passed empty-state startup/restart only and remains undeployed with high/critical findings. Resume remaining database/desktop/crawler advisory and saved-state rollback work in UPGRADE_CHECKLIST.md; evidence in reports/companion-update-2026-10-07.md.


2026-10-07 database/desktop follow-up: tested PostgreSQL17.11 zlib correction deployed to database/backup (exact image 5fab158ded33); source/settings verification passed. Matched same-image Obsidian HTTP/process startup/restart and original source preservation passed on copied volumes. Obsidian candidate downloads timed out; current desktop and optional Crawl4AI digests pinned. Remaining: crawler/desktop/archive patches, cross-version/interactive rollback and paused model evaluation. Resume reports/database-desktop-checkpoint-2026-10-07.md and UPGRADE_CHECKLIST.md.


2026-10-07 crawler delivery: available Debian updates, PyJWT/urllib3 fixes and Requests-compatible chardet deployed after real extraction/restart and JWT-enabled API tests. Upstream overlapping jwt/PyJWT namespace repaired with a maintained auth adapter. Exact image e12f6af5ffe9; original launch configuration preserved and old crawler retained stopped for rollback. Notes/settings verification passed; scanner rules 995→771, critical 35→25. Next: Crawl4AI 0.9.0/anyio/nltk candidate tests, desktop cross-version recovery and archive compatibility. Read reports/crawler-delivery-2026-10-07.md and UPGRADE_CHECKLIST.md.


## Latest checkpoint — 2026-10-07 23:35 Maldives

Matching Crawl4AI 0.9.4 server/library and compatible app client are deployed. Twenty isolated scripts and the actual API/auth/config/restart matrix passed; all five app services are healthy. Original 1,201 sources and ingestion settings are preserved; AI remains paused. Direct crawler API access now requires a bearer token; the app receives its private token from ignored `.env`. Final crawler scan still contains 25 critical rules (768 total), requiring further artifact/runtime triage. FM-07/09 remain partial. Resume `UPGRADE_CHECKLIST.md` and `reports/modern-crawler-delivery-2026-10-07.md` for minimal-base/advisory work, desktop cross-version recovery and archive image/state compatibility. Earlier dated entries are historical.


Latest continuation (2026-10-07 23:48 Maldives): read-only crawler triage recorded 22 critical rules in historical metadata and three in installed OS components; no exploitability clearance. Experimental Python 3.12 supervisor candidate e208621bb2ac passed the full extraction/restart/auth matrix and removes Python 3.11. It is not deployed. Automatic approval review blocked external Docker Scout metadata transmission; next prerequisite is explicit scan approval, then bundled Node/fork review and maintained-build integration. See reports/crawler-runtime-triage-2026-10-07.md and WORKLOG.md. Production and AI pause remain unchanged.


## 2026-10-08 00:01 Maldives — official crawler image pulled

User requested latest Crawl4AI pull. `docker pull unclecode/crawl4ai:latest` completed successfully after a slow multi-layer download. Exact digest/image: sha256:9021b3cb5c6f12570bbcd5395638495e0a06969b3148e377b953d174af2ebc9b. Offline disposable package inventory confirms Crawl4AI 0.9.4 / Python 3.12.14. Existing production crawler remains healthy on custom image 35eabc8e6da1; no replacement performed. Next: run the existing modern API/extraction/restart matrix on this official candidate, review differences and approved advisory scan before deployment. Earlier external Scout approval request remains unresolved.


Latest continuation (2026-10-08 10:15 Maldives): official 0.9.4 image extraction/restart passed but no-expiration JWT acceptance failed. Maintained crawler build now uses the pinned new official base plus existing auth/dependency fixes and Supervisor 4.3.0 on Python 3.12.14; duplicate Python 3.11 removed. Exact candidate 3e099e0a5b4a passed the full modern API/extraction/restart matrix, but remains undeployed awaiting explicit Docker Scout metadata transmission approval and fresh scan. Remaining FFmpeg/TIFF, browser Node/fork advisory review and desktop/archive recovery stay open. Production and AI pause are unchanged. Resume reports/new-base-crawler-continuation-2026-10-08.md.
