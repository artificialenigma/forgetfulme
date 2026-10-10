# Database and desktop recovery checkpoint — 2026-10-07

## Database/backup delivered

Built `infra/database/Dockerfile` from the existing exact PostgreSQL 17.11 base and applied `zlib>=1.3.2-r1`; server and entrypoint unchanged. Exact passing image `sha256:5fab158ded33436b060a9841ab8df3e69070e9db3ae07a92d12edd525f8f2988`, retained as `forgetfulme-db-test:20261007` and deployed as `forgetfulme-db:local`. The upstream base is pinned; APK repositories are mutable, so every future rebuild requires fresh tests/scans.

Matched scheduled backup `20261007T173508Z` restored using the candidate for archive conversion and the disposable database: 6,839 vault files, 11,432 visits, 10,030 captures, 5,983 library documents, 494 scan jobs; migrations twice, original row/settings checks, synthetic key/state/citation/PDF roundtrip and six authenticated restored app pages passed. Content/config restore checked 349 regular config files, omitted three runtime links and covered synthetic nonempty binary/hidden content. `full_restore_drill.py --postgres-image` now propagates the exact validated image throughout the database rehearsal.

Scout findings decreased from 58 to 57, high from 23 to 22; two critical entries remain. See `database-hardened-audit-2026-10-07.sarif.json`. Saved fresh baseline/SQL/vault in private `backups/upgrade-2026-10-07-225217/`; retained old image as `forgetfulme-db-rollback:20261007`. Paused background writers/backup, deployed only database/backup with no build or volume removal, resumed writers. Compose start also ran existing vault-init/migrate dependencies; these completed successfully. Both services verified healthy and exact-image matched. Original source files preserved: 1,201; automation=true, AI=false and inherited ingestion controls unchanged; twelve authenticated GETs passed. Latest scan succeeded: 6,173 seen, zero changed/failed. Counts evolve. App remains exact candidate b1258a3cddfe; proxy remains d13915e628d3.

## Critical Go findings: scoped triage, not suppression

Both critical database findings locate `/usr/local/bin/gosu` (1.19, Go1.24.6), not PostgreSQL. Scanner descriptions concern TLS resumption (CVE-2025-68121) and IDNA conversion (CVE-2026-39821). [gosu's security policy](https://github.com/tianon/gosu/blob/master/SECURITY.md) asks for function-reachability analysis and explains why unused Go interfaces do not trigger releases. [1.19 main](https://raw.githubusercontent.com/tianon/gosu/1.19/main.go) and [user setup](https://raw.githubusercontent.com/tianon/gosu/1.19/setup-user.go) switch user/group and exec a process. The PostgreSQL entrypoint invokes it as `gosu postgres` only.

Static inspection of this binary found main.SetupUser symbols and no crypto/tls, net/http or IDNA symbol prefixes. This supports limited reachability, but is not a govulncheck call graph or definitive exploitability proof. Findings remain recorded, not deleted/reclassified. Native strings was unavailable (exit69); ASCII symbol extraction used Python without installing tools. See `postgres-gosu-symbol-review-2026-10-07.json`. Remaining libxml2 high entry is reported without a fixed version. Next: verified binary/call-graph analysis of relevant Go findings and upstream OS patches.

## Existing Obsidian runtime recovery rehearsed

`scripts/desktop_restore_drill.py` restored the matched vault/config into new disposable volumes on an internal network with no published ports/providers or live mounts. Existing exact image 0ae1b2ffe772 passed HTTP plus actual Obsidian process startup and restart. All original vault source hashes remained unchanged; `.obsidian/` workspace metadata may change. Initial config hashes checked before startup. Private desktop logs/notes were suppressed; resources removed.

Early verifier failures were repaired: large hash manifest moved from arguments to stdin; HTTP readiness supplemented with bounded application-process wait; original-file checks narrowed to allow expected workspace metadata updates only under `.obsidian/`. Final result is `desktop-old-restore-2026-10-07.json` (6,839 vault and 349 config regular files, three config runtime links skipped). This demonstrates same-image runtime recovery, not cross-version rollback, interactive UI/plugin compatibility, or private provider-key recovery.

Obsidian candidate pull timed out twice (120s and 90s); running service unchanged. Compose now pins its tested current digest, preventing a moving latest tag from changing a later recreation. Reattempt a compatible candidate download, then audit and run copied-config/vault rehearsal plus interactive review before rollout.

## Crawl4AI triage and reproducibility

The configured 0.8.6 tag resolves to the same running image a45fd08f8f15, now pinned in optional compose.crawl4ai.yaml. No crawler replacement deployed. Active Python distribution is crawl4ai0.8.6; scanner's crawl4ai0.7.8/CVE-2026-26217 entry is solely in `/tmp/project/sbom/sbom.cdx.json`. Do not count that as proof the active package is 0.7.8. Scanner also locates PyJWT2.10.1 in active site-packages and embedded SBOM: fix version2.14.0 reported. Node/OS/Python advisories remain; active import emitted a requests dependency compatibility warning. Next: test a derived crawler candidate with bounded PyJWT/requests dependency corrections and supported OS updates, using a synthetic internal crawl target and no real browsing/provider calls. Retain original image/container definition and verify exact API behavior before replacement.

Remaining FM-09 work: actual newer-to-older desktop/config rollback, archive saved-state/reproducible image recovery, crawler/desktop patches and time-bound advisory review. FM-07 live model answer/abstention evaluation remains paused with AI disabled.
