# Resumable upgrade checklist

Last checkpoint: **2026-10-08 10:15, Indian/Maldives (UTC+05:00)**.
Status: **Matching Crawl4AI 0.9.4 server/library and app client deployed and verified; remaining audit and recovery work listed below.**

This is the execution record for `UPGRADE_PLAN.md`. Read this file and the latest
`WORKLOG.md` entry before resuming. `[x]` means implemented and validated; `[ ]`
means remaining work. Never infer completion from an edited file or image build.

## Resume here

1. Read applicable instructions, this checklist and the latest WORKLOG.md. Preserve all uncommitted work (HEAD d181d12); no upgrade commit exists. Do not reset/clean or rewrite the reference host vault.
2. **Second delivery is validated, deployed and verified.** Publication action/reconciliation acceptance now passes. Filename impact/collision previews are deployed. Changed/deleted/FIFO/post-move rename conflicts now have coverage. FM-02/03 acceptance review and 1k real process-death restart tests are complete. Matched-set app/data recovery and synthetic credential compatibility passed; legacy display labels are deployed. Latest matching Crawl4AI 0.9.4 server/library and client update is complete. Next: approve metadata transmission for the exact new official-base candidate 3e099e0a5b4a, scan and assess remaining findings/Node/fork dependencies, then save a fresh baseline and roll out the accepted image; retry Obsidian copied-state upgrade/rollback and archive image/state recovery. See reports/modern-crawler-delivery-2026-10-07.md. Preserve the implemented publisher and conflict UI.
3. Paginated FM-03 job/error/rename retry controls are deployed. Keep unchecked acceptance tasks visible.
4. Run `python3 scripts/run_isolated_tests.py` after application changes. Providers and mutating fixtures belong only in disposable services. Retest a new frozen candidate if source changes; deploy the exact passing image.
5. Before another rollout, recheck runtime/settings and save a fresh private baseline/backup. `scripts/backup_before_upgrade.py` pauses background writers; they remain stopped until rollout. Obsidian/external editors are independent writers, so sequential backups are not an atomic full-stack snapshot.

## Current release and validation

- Checkpoint: **2026-10-07 23:35 Indian/Maldives (UTC+05:00)**.
- `python3 scripts/run_isolated_tests.py`: **20 scripts passed**, migrations twice, frozen app/fixtures/build inputs and image/source checks. Synthetic providers only.
- Exact candidate `forgetfulme-test:762a461c255a`, reused as `forgetfulme-app:local` without rebuilding.
- Image ID `sha256:38d6a90e94c59f046f4ffae8bc6cef181362d781c58a14fe9c466aac5aa2bf4e`.
- App fingerprint `ee0c78fbba80f2ccb2ae61c8312cd3e7e7b90be6b73db37ca025decfa1d4b945`; **40 app files** match all five healthy services: web, worker, wiki-worker, library-worker, scheduler.
- `python3 scripts/verify_release.py --baseline backups/upgrade-2026-10-07-232923/baseline.json --image forgetfulme-test:762a461c255a`: passed. Twelve authenticated read-only GETs; latest index status recorded in WORKLOG.md. Counts evolve.
- **1,201 baseline source files preserved**; automation enabled, AI disabled, nullable ingestion controls inherit these settings. Three renames and one addition predated this rollout; none reverted. Reference host vault untouched.
- Private ignored backups `backups/upgrade-2026-10-07/`: baseline, database SQL and vault archive. Disposable restore verified 3,511 vault files, existing catalog/job rows, migrations twice, and a second seeded database roundtrip covering identities/preferences/connections/questions/citations/PDF states.
- Public dependency audit: 37 locked Python packages, no known advisories returned. Python/PostgreSQL images pinned. Content/config volume restore passed; matched app/data and synthetic credential compatibility passed; Companion scans found high/critical advisories; archive-desk scan and actual desktop rollback remain incomplete. See reports/container-audit-review-2026-10-07.md.
- Labelled retrieval and 1k/10k measurements saved in `reports/retrieval-benchmark-2026-10-07.json`; no live model inference or model-abstention accuracy claim.
- Signed-in Projects page visually inspected at desktop/mobile sizes with keyboard skip-link focus. Ten populated responsive screens and representative visual/keyboard checks now passed.

## FM-01 — Evidence boundaries: COMPLETE

- [x] Disposable database/vault tests cannot access production defaults/resources.
- [x] Imported notes under archive folders retain imported evidence scope.
- [x] Generated answers/indexes/connections cannot feed later AI requests;
  historical unknown generated sources fail closed.
- [x] Source-family exclusions are inherited, including older capture revisions,
  and checked at prompt construction for already queued questions.
- [x] Saved answers persist explicit scope, parent IDs, revision hashes/provenance.
- [x] AI pause and explicit synthetic provider diagnostics are tested.
- [x] Regression and live release checks passed; original notes/settings preserved.

## FM-02 — Identity and citations: COMPLETE

- [x] Immutable IDs/path history added; journaled renames preserve app preferences,
  accepted connections and research-question resolutions.
- [x] Exact citation snapshots remain accessible after edits/renames/deletion;
  historical answers without snapshots clearly report that limitation.
- [x] Atomic no-overwrite Linux rename, destination preflight, pending-journal
  recovery and source-ID collisions tested without deleting human revisions.
- [x] Changed captures are immutable; changed content invalidates summaries;
  unchanged content avoids redundant synthesis; reviewed files stay intact.
- [x] Managed publication parses ownership, rejects imports/symlinks, checks
  generation/destination/source hashes and retains detected conflict drafts.
- [x] Strict no-overwrite immutable generated revisions, frontmatter-only ownership checks, retained human edits/conflicts and journal recovery tested.
- [x] Conflict preview/activation/dismiss routes and capture-pointer reconciliation implemented; app path aliases and recoverable accepted-connection companion exports added.
- [x] Authenticated publication activation/dismiss POST, CSRF/repeated actions, edited/missing/imported/reviewed/identity/symlink proposals and caller-crash/stale/excluded/edited reconciliation acceptance matrix.
- [x] Reviewed proposal activation is blocked and symlink activation returns a reviewable conflict rather than a server error.
- [x] Rename repair preview shows inbound notes/connection/answer counts and file/catalog collisions; content-bound approval rejects edits after preview.
- [x] Changed/deleted/FIFO/post-move-edited journal failures preserve files; bounded batches and no-follow reads.
- [x] Final move/restart/retention acceptance review mapped in reports/recovery-acceptance-2026-10-07.md; cited snapshots are independent of current chunk cleanup. Future revision deletion requires referenced-revision guards. Static Markdown links are retained for Obsidian review; app path aliases follow renames.

## FM-03 — Indexing and publication: COMPLETE

- [x] Missing/unmounted roots and incomplete traversal cannot discard the catalog.
- [x] Per-file failures retain good data; no-follow descriptor reads/hash use the
  same snapshot and reject concurrent source replacement.
- [x] Full reindex reparses unchanged notes; queued/running/succeeded/failed jobs
  record counts, versions, errors and successful scan time.
- [x] More than 20 missing/protected publication jobs cannot starve valid sources;
  failed writes never report indexed success.
- [x] Vault health displays index jobs, sanitized file/publication/rename errors.
- [x] Separate local library worker/PDF queue, durable scan progress and independent heartbeat; fairness fixtures passed.
- [x] Health suffix lookup and bounded duplicate descriptions preserve resolution semantics and eliminate observed live diagnostic timeout.
- [x] Real SIGKILL in a 1,000-note full scan: durable progress/catalog rollback, restart recovery, changed revisions, stable identities and deletion retention.
- [x] Detailed paginated job/file-error/rename-conflict pages and guarded scan/journal retries; signed-in CSRF/collision/idempotence fixtures.
- [x] Final FM-03 acceptance audit, last successful scan/current progress/worker freshness and local timestamps.

## FM-04 — Metadata and extraction: COMPLETE

- [x] Bounded safe YAML handles nested/list/multiline/CRLF/BOM metadata; invalid,
  aliased/unsafe/duplicate/over-limit values produce sanitized diagnostics.
- [x] Code, tables and source coordinates survive cleaning/chunking; every chunk
  respects its budget, including long code lines and late document evidence.
- [x] Unicode word rules unify matching/counting, Latin accents fold deliberately,
  Dhivehi/other script marks remain; titles and aliases are searchable.
- [x] Pure metadata, real PostgreSQL matching and existing regressions passed.

## FM-05 — PDFs: COMPLETE

- [x] Selected bounded asynchronous local extraction, immutable page text/citations and original download.
- [x] Invalid/encrypted/scanned/budget/cancel/retry/superseded states tested.
- [x] Immediate scope/exclusion/revision inheritance and original preservation tested.
- [x] OCR remains explicitly disabled; no cloud uploads or model downloads.

## FM-06 — Ingestion controls: COMPLETE

- [x] Separate inherited visit/export/download/index/AI controls, selected/allowlisted capture and domain policies.
- [x] Domain budgets/delay/backoff, pause/cancel/retry and reimport preservation tested.
- [x] Original visits retained; newly exported credential URLs redacted.
- [x] Paginated queues and truthful states; immutable history exports retain older notes.

## FM-07 — Retrieval: PARTIAL

- [x] Diverse whole excerpts, prompt budgets, immediate scope/exclusion checks and revision/version metadata.
- [x] Evidence preview/project filtering and source-scoped Ask.
- [x] 25 labelled questions, 29 notes, duplicate/title/multilingual/private/unanswerable cases. Answerable Recall@5 1.0; invalid citations/scope/exclusion violations zero.
- [x] 1k/10k baseline: Recall@5 0.96; p50/p95 64/211 ms and 483/1,923 ms respectively (50 queries each, SQL plus selection only).
- [ ] Provider answer/abstention evaluation for related-hit unanswerable questions. AI is paused; no actual model accuracy measured. Optional semantic work awaits baseline decisions.

## FM-08 — Research workflow: COMPLETE

- [x] Project workspace, answer picker, source-scoped Ask, question deduplication/pagination/dismiss/reopen.
- [x] Revision-bound health dismissals/pagination and reversible connections with recoverable immutable exports.
- [x] Safe bounded Markdown reading and signed-in workflow fixtures; desktop/mobile Projects visual QA and keyboard focus.
- [x] Ten populated screens checked at 390×844 and 1280×900 for overflow, labels, button names and landmarks; representative note/ingestion visual inspection and keyboard skip/focus passed. See reports/ui-review-2026-10-07.md; no formal WCAG certification claimed.
- [x] Separate generated navigation/history display labels/filter/counts, with ZIP provenance priority; stored origin/evidence scope/source IDs unchanged.

## FM-09 — Release and recovery: PARTIAL, CONTINUES EACH DELIVERY

- [x] Isolated frozen test/build harness, migrations twice and exact passing candidate rollout.
- [x] Five services healthy/source/image matched; original sources/settings preserved.
- [x] Fresh private database/vault backups, disposable restore plus seeded state roundtrip.
- [x] Python dependency lock/advisory audit (37 packages), app fingerprint label and Python/PostgreSQL digest pins.
- [x] Backup/restore/verification scripts and synchronized checklist/plan/handoff/worklog.
- [x] Offline content/config volume rehearsal: 295 exact regular configuration files/ownership, three Chromium runtime links omitted; empty actual content plus nonempty binary/hidden fixture.
- [x] Matched scheduled DB/vault/content/config set, original visits/captures/settings preserved across forward migrations, restored FastAPI six-page runtime and synthetic matching/wrong-key recovery checks.
- [x] Same-image Obsidian runtime recovery: copied matched config/vault, actual process and HTTP startup/restart, original source hashes preserved (workspace metadata may change).
- [ ] New-to-old Obsidian/third-party runtime/config rollback and interactive/plugin compatibility; original production encryption environment required for actual saved keys. Older code on newer schema is not verified rollback.
- [x] Exact local app, DB/backup, proxy, Obsidian and Crawl4AI image advisory scans; unused pip removed from runtime, clearing seven app findings. Reports are time-bound, not exploitability assessments.
- [x] Patched pinned-base proxy tested with synthetic authentication/routing and deployed exactly; high zlib finding cleared. Overdue scheduled backup restarted successfully; exact pinned DB restore passed latest backup.
- [x] Exact restore-tested PostgreSQL/backup zlib correction deployed, fresh backup/source/settings baseline verified; Go critical findings investigated without suppressing scanner results. Obsidian/current optional crawler image digests pinned.
- [x] Crawler Debian/JWT/HTTP dependency fixes and overlapping JWT namespace repair: real app extraction/restart, JWT helper and authenticated API tests passed; exact candidate deployed with preserved launch config and retained prior container. Scanner rules reduced 995 to 771 (critical 35 to 25).
- [ ] Triage/test remaining companion high/critical updates and remaining app OS findings. Archive-desk image is absent from local image storage: recover a reproducible image before recreation; its full OS audit remains unavailable.

## Checkpoint protocol

After every validated delivery, update `Resume here` with the next task, changed
files/schema, actual commands/results, limitations and deployment identity.
Append evidence to `WORKLOG.md`; synchronize plan/handoff statuses. Before
stopping—even on a failed test—record its exact failure and next action. Leave
unvalidated tasks unchecked. The next agent rechecks the working tree/runtime,
then resumes the first unchecked prerequisite without running live fixtures.

Latest follow-up backup: `backups/upgrade-2026-10-07-221833/` (fresh baseline/database/vault; archives not separately restore-drilled). Previous restore evidence remains for the earlier snapshot.

Latest companion delivery: proxy sha256:d13915e628d36145ba0df6728cfc6388f06e9981d91e0e36f6aab2b04aeba85e; previous image/storage retained privately. DB tag unchanged. Archive candidate startup/restart passed empty-state isolation, but has high/critical advisories and is not deployed. Details: reports/companion-update-2026-10-07.md.

Latest database/backup: sha256:5fab158ded33436b060a9841ab8df3e69070e9db3ae07a92d12edd525f8f2988 (57 scanner entries, including two critical Go/gosu entries still recorded). Latest private baseline: backups/upgrade-2026-10-07-225217/. Same-image Obsidian rehearsal passed; candidate download timed out, no desktop/crawler replacement deployed.

Latest crawler image: sha256:e12f6af5ffe90c5554277fcd118034d949e230e78b9a2fcf8a1a779528f0f0f9. Private launch backup: backups/crawler-upgrade-20261007T181014Z/; prior stopped container retained as crawl4ai-rollback-20261007T181014Z. Further scanner findings remain; use reports/crawler-remaining-critical-2026-10-07.json for next package targets.


## Latest matching server checkpoint

- [x] Crawl4AI 0.9.4 matching server/library, AnyIO/NLTK updates and browser runtime tested and deployed.
- [x] Authenticated API/config trust-boundary matrix and modern app client passed; 20 isolated scripts.
- [x] Private token/config migration, exact candidate rollout and source/settings verification passed.
- [ ] Remaining 25 critical scanner rules require runtime/artifact/reachability triage; image is not clean.
- [ ] Full coordinated app/server rollback and desktop cross-version/interactive recovery remain incomplete.

Current crawler: `sha256:35eabc8e6da154873a6846bf95e6d11bb5bb1a97d129fa3d1efad21ba8bf81fe`. Previous e12f6 image is retained stopped in `crawl4ai-rollback-20261007T183030Z`. Fresh private backups: `backups/upgrade-2026-10-07-232923/` and `backups/crawler-upgrade-20261007T183030Z/`. Evidence and next action: `reports/modern-crawler-delivery-2026-10-07.md`. Earlier timestamped checkpoints below/above are historical. AI remains paused.


Latest continuation (2026-10-07 23:48 Maldives): read-only crawler triage recorded 22 critical rules in historical metadata and three in installed OS components; no exploitability clearance. Experimental Python 3.12 supervisor candidate e208621bb2ac passed the full extraction/restart/auth matrix and removes Python 3.11. It is not deployed. Automatic approval review blocked external Docker Scout metadata transmission; next prerequisite is explicit scan approval, then bundled Node/fork review and maintained-build integration. See reports/crawler-runtime-triage-2026-10-07.md and WORKLOG.md. Production and AI pause remain unchanged.


## 2026-10-08 00:01 Maldives — official crawler image pulled

User requested latest Crawl4AI pull. `docker pull unclecode/crawl4ai:latest` completed successfully after a slow multi-layer download. Exact digest/image: sha256:9021b3cb5c6f12570bbcd5395638495e0a06969b3148e377b953d174af2ebc9b. Offline disposable package inventory confirms Crawl4AI 0.9.4 / Python 3.12.14. Existing production crawler remains healthy on custom image 35eabc8e6da1; no replacement performed. Next: run the existing modern API/extraction/restart matrix on this official candidate, review differences and approved advisory scan before deployment. Earlier external Scout approval request remains unresolved.


Latest continuation (2026-10-08 10:15 Maldives): official 0.9.4 image extraction/restart passed but no-expiration JWT acceptance failed. Maintained crawler build now uses the pinned new official base plus existing auth/dependency fixes and Supervisor 4.3.0 on Python 3.12.14; duplicate Python 3.11 removed. Exact candidate 3e099e0a5b4a passed the full modern API/extraction/restart matrix, but remains undeployed awaiting explicit Docker Scout metadata transmission approval and fresh scan. Remaining FFmpeg/TIFF, browser Node/fork advisory review and desktop/archive recovery stay open. Production and AI pause are unchanged. Resume reports/new-base-crawler-continuation-2026-10-08.md.
