# Recovery acceptance review — 2026-10-07

This review maps FM-02/03 acceptance to disposable fixtures. It does not authorize a production restore or claim arbitrary filesystem transactions are atomic.

| Acceptance | Evidence |
|---|---|
| Stable identities/preferences/connections/question resolutions after rename and restart | evidence_scope_test: atomic move plus interrupted filesystem/DB journal reconciliation; workflow_test: connection companion and authenticated conflict retry |
| Exact citations survive edit/rename/deletion | evidence_scope_test: retained excerpt/revision, changed/unavailable current-file indication; restored seeded citation state roundtrip |
| Retention protects cited evidence | Review found no automated deletion of question citation snapshots or generated revisions. Indexing marks missing identities absent and replaces current chunks, while exact cited excerpts remain in answer rows. Backup retention removes backup directories only. Any future revision cleanup must add referenced-revision guards/tests. |
| No overwrite/unsafe identity merge | publication_test/source_revision_test: immutable revisions, protected/imported/symlink/collision cases; evidence_scope_test: independently owned duplicate hashes |
| Capture revision/summary correctness | source_revision_test: changed recapture invalidates summary; unchanged content avoids inference; publication_test: caller-crash reconciliation, stale revision/exclusion/edited proposal guards |
| Human edits/review switches at publication boundary | publication_test: editor save and concurrent reviewed preference retain original bytes and conflict draft; workflow_test: activation refuses protected/changed/missing proposals |
| Missing/incomplete/unreadable source isolation | evidence_scope_test: missing root, traversal failure, per-file read error and unrelated successful index; metadata_test: malformed bounded metadata |
| Full reindex and index version | evidence_scope_test/index_restart_test: unchanged full parsing, durable version/fingerprints and unchanged incremental no-op |
| Publication starvation/truthful outcomes | source_revision_test: more than 20 missing/protected sources before valid work; failed writes are not successful indexing |
| Real large scan interruption | index_restart_test: 1,000 notes; SIGKILL at 100 snapshots; independent progress >=80 survives, catalog transaction rolls back, next scan marks interrupted job failed, reindexes changed ten revisions and preserves all identities; deletion retains absent identity |
| Worker fairness | worker_fairness_test: separate local queue pause, blocked scan does not block AI queue/heartbeat; scan progress cannot impersonate wiki-worker |
| Observable retry/staleness | workflow_test: paginated jobs/errors/rename conflicts, authenticated/CSRF actions, collision-safe retries and repeat protection; final release adds last successful scan/current progress/local worker heartbeat freshness and Maldives timestamps |

Limits: this is a deterministic 1k interruption fixture, not a claim of all hardware failure scenarios. Original Markdown links remain for Obsidian review; app aliases follow renames. Source snapshot races preserve files and surface conflicts rather than silently assuming identity. Detailed recovery state is bounded in batches; reviewed or edited proposals require explicit review. AI model accuracy/abstention remains unmeasured and paused.

Volume rehearsal: saved 20261006T124820Z content archive is empty; all 295 regular configuration files restored with exact hashes and UID/GID 10001. Three omitted links are Chromium SingletonCookie/SingletonSocket/SingletonLock runtime artifacts. Additional synthetic binary/hidden/nonempty files verified content recovery. Rehearsal used new offline volumes only and removed them. Earlier DB/vault and seeded state roundtrips are recorded in WORKLOG.md. These snapshots are from different times, so the combined evidence is not a matched full-stack restore or running Obsidian launch test.

Production recovery compatibility: use a matched backup set, stop writers/Obsidian, preserve the original credential/encryption environment and UID/GID, restore into empty destination volumes, run forward migrations, then verify settings/identities/citations before enabling workers. Never assume an older app image supports the newer schema or restore live volumes using the disposable rehearsal scripts. Full matched-set/runtime rollback review remains FM-09.

## Matched-set follow-up

`full_restore_drill.py --backup-dir backups/20261006T124820Z --image forgetfulme-test:356edb42335f` passed on one scheduled four-archive set. Original 11,432 visits, 10,030 captures, one AI row, one controls row and historical question rows survived original-column comparisons across migrations twice. The restored FastAPI served six authenticated library/recovery pages with no workers/provider calls or host ports. Synthetic encrypted credentials survived dump/restore with the matching environment; an incorrect environment was rejected. Actual saved secrets were not decrypted/logged. Volume regular-file hashes/ownership and nonempty fixtures passed. Original credential environment is still required for actual recovery. Obsidian desktop/third-party launch and older-image/new-schema backward rollback remain unverified.
