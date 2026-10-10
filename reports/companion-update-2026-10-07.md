# Companion update checkpoint — 2026-10-07

The overdue backup service was restarted and became healthy. It completed `backups/20261007T173508Z`. Its previous last-success time was more than one configured interval plus health grace old; no claim about the underlying clock/sleep cause is made.

## Proxy delivered

Pulled same-major Caddy candidate `sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f`. Its four findings still included high-severity zlib. Built `infra/proxy/Dockerfile` from that digest with the minimum patched zlib version. [Alpine's package page](https://pkgs.alpinelinux.org/package/v3.23/main/x86_64/zlib) lists 1.3.2-r1. Package repositories are mutable: the base is pinned, but future rebuilds must be tested/scanned again.

Exact tested/deployed proxy image: `sha256:d13915e628d36145ba0df6728cfc6388f06e9981d91e0e36f6aab2b04aeba85e`, retained as `forgetfulme-proxy-test:20261007` and deployed as `forgetfulme-proxy:local`. Scanner findings reduced from four (one high) to three (two unspecified, one medium); no vulnerability-free claim. See `proxy-hardened-audit-2026-10-07.sarif.json`.

`python3 scripts/proxy_candidate_check.py --image <exact ID>` passed [Caddy configuration validation](https://caddyserver.com/docs/command-line), real routing/security headers, desktop redirect, denied authentication and allowed synthetic authentication. Disposable internal network, synthetic backend containers, no production volumes, ports or providers; resources removed. Same tests passed both upstream and patched candidates.

Saved previous image `sha256:881bbc60f9986d5ab8e7cfd6cf7e4ef3c9c0439fef2429d035d065577882f028` as `forgetfulme-proxy-rollback:20261007`, plus owner-only caddy data/config archives and identity in `backups/proxy-upgrade-20261007T173838Z/`. Archives are not restore-drilled; image switching is not certified storage rollback. Deployed only proxy using `docker compose up -d --no-deps --no-build proxy`. Live exact image, login HTTP/header and unauthenticated desktop login redirect passed. Five app services retained their prior tested release.

## Database recovery verified

The current PostgreSQL 17 Alpine tag still resolves to existing pinned image b0f9560a2de0; no database replacement deployed. Its 58 scanner findings (23 high, two critical) remain. Updated `restore_drill.py` to require an exact digest/local image ID via `--postgres-image`, defaulting to the existing pin, preventing a moving tag from silently changing recovery tests.

Latest 221833 backup restored in isolation: 6,540 files; 11,432 visits, 10,030 captures, 5,702 library documents and 478 scan jobs; original rows/settings retained across two migrations. Nonempty synthetic state/key compatibility roundtrip and six authenticated restored pages passed. First invocation used nonexistent short filenames and stopped at argument validation; corrected to the actual `database-before-second-delivery.sql` and `vault-before-second-delivery.tar.gz`.

## Archive candidate only

Available replacement image `sha256:73358403e0524062774cbb48891d91060913a07c213fa3fcb285eb87e83e9182` passed app/noVNC HTTP startup and restart with an empty disposable state volume on an internal network and no published ports. See `archive-candidate-startup-2026-10-07.json`. Audit found 565 rules: nine critical, 101 high, 92 medium, 326 low, 37 unspecified. This different image is not a recovery of the missing running image and is not deployed. Saved-state compatibility, provider configuration, actual browser workflow and old-image rollback remain unverified.

Next: triage database critical Go-binary findings and compatible patched build options; audit/update Obsidian/Crawl4AI candidates with saved-state startup/rollback testing; obtain a reproducible archive build with lower findings and verify saved state before replacing its running service. Model evaluation remains paused with AI disabled.
