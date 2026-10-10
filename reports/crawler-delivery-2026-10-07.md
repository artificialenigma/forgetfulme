# Crawler security delivery — 2026-10-07

Exact deployed candidate: `sha256:e12f6af5ffe90c5554277fcd118034d949e230e78b9a2fcf8a1a779528f0f0f9`, retained as `forgetfulme-crawler-test:20261007` and `forgetfulme-crawler:local`. Base Crawl4AI/API version remains 0.8.6. `infra/crawler/Dockerfile` pins the upstream digest, applies available Debian package updates and pins PyJWT 2.14.0, urllib3 2.8.0 and chardet 5.2.0. `pip check` passed. Repositories/dependency resolution remain mutable; future builds require new frozen identity/tests/scans.

The upstream image installed both jwt 1.4.0 and PyJWT into the same `jwt` namespace. A direct PyJWT update made `/app/auth.py` fail importing JWT. Removed the overlapping jwt package, reinstalled PyJWT and supplied `infra/crawler/auth.py` with the server's existing create_access_token/get_token_dependency/TokenRequest interface. HS256 verification requires expiration; invalid/expired tokens return generic 401. JWT-enabled configuration requires an explicit SECRET_KEY of at least 32 bytes. With JWT disabled, a process-local random signing key replaces the upstream default. The current service remains JWT-disabled, matching its existing setting; no credentials/toggles were changed.

Compatibility: original and final candidates each passed real app `extract_html` calls before/after restart, including Unicode, absolute evidence links and active-resource stripping. Synthetic raw HTML only, internal Docker networks, no published test ports/live mounts/providers. Final checks also passed pinned dependencies, no RequestsDependencyWarning, helper signatures/expiration/algorithm restrictions and actual JWT-enabled HTTP API rejection of missing/invalid/expired tokens plus accepted authenticated extraction. See `crawler-auth-check-2026-10-07.json`.

Early candidates failed readiness: first retained root runtime identity after package installation, causing /root permission errors; restored upstream appuser. Next failed because overlapping JWT packages broke the auth import; replaced the helper as above. Neither failed candidate was deployed. Synthetic failure diagnostics were saved privately before cleanup. Final checker uses wall-clock readiness deadlines. Application source/build and the prior 19 app runtime tests are unchanged; new companion integration tests provide this delivery's validation.

Advisory counts (Scout 1.24.0, rule counts, not exploitability conclusions):

| | Total | Critical | High | Medium | Low | Unspecified |
|---|---:|---:|---:|---:|---:|---:|
| Original |995|35|280|255|354|71|
| Final |771|25|193|187|324|42|

The old PyJWT critical finding now exists only in the embedded historical SBOM; the active package is 2.14.0. Ten of 25 remaining critical rules have only embedded-SBOM locations. Keep the raw results; no blanket clean-image claim. See `crawler-auth-audit-2026-10-07.sarif.json` and `crawler-remaining-critical-2026-10-07.json` for packages/fixes/locations.

Deployment: `scripts/deploy_crawler_candidate.py` requires exact identity and passing extraction/auth proof; saved private original container/config/environment in `backups/crawler-upgrade-20261007T181014Z/`. Paused only the capture worker, stopped/renamed the old crawler, retained it as `crawl4ai-rollback-20261007T181014Z` and disconnected its app-network endpoint to avoid DNS ambiguity. Created the exact tested replacement with existing ports/environment/server config/networks, then resumed the unchanged worker. Candidate config bytes match the saved config. Worker GET /health passed; final image/user/health verified (appuser, healthy). No production extraction fixture was posted. The original stopped container and image are retained for rollback; automatic deployment-failure recovery is implemented but was not deliberately triggered live.

After rollout, `verify_release.py --baseline backups/upgrade-2026-10-07-225217/baseline.json --image forgetfulme-test:b1258a3cddfe` passed: five exact app-image/source/health checks, 1,201 original source files unchanged, automation=true/AI=false/nullable controls unchanged and 12 authenticated GETs. Latest index succeeded: 6,173 seen, zero changed/failed. Counts evolve. Database/backup/proxy releases remain unchanged. Disposable crawler resources removed. Optional Compose crawler now references the local derived build; the actual standalone container retains its original endpoint name and launch configuration.

Next: test Crawl4AI 0.9.0 (scanner lists fixes through 0.9.0), anyio>=4.14.2 and nltk>=3.10.3 against the same real API and auth matrix. Distinguish active package locations from embedded historical SBOM/egg-info. Debian Python/FFmpeg/TIFF entries currently report no fixed version; investigate reachable functions and patched supported base options. Continue Obsidian candidate download, copied-state cross-version/interactive rollback and archive recovery. AI answer/abstention evaluation remains paused.

Sources: [PyJWT 2.14.0 release](https://pypi.org/project/PyJWT/2.14.0/), [Requests encoding behavior](https://requests.readthedocs.io/en/stable/user/advanced/). Actual version/behavior evidence is in the local candidate checks.
