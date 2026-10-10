# Container advisory review — 2026-10-07

Docker Scout 1.24.0 scanned exact locally running image IDs. Raw SARIF and the inventory summary are in this directory. Counts are scanner advisory rules, may contain overlapping CVE/GHSA references, and do not establish runtime exploitability. The summary captured the app before hardening; the separate hardened SARIF is the final app result.

| Image | Findings | High | Critical |
|---|---:|---:|---:|
| App before hardening | 36 | 7 | 0 |
| App after removing unused pip | 29 | 2 | 0 |
| PostgreSQL / backup (same image) | 58 | 23 | 2 |
| Proxy | 4 | 1 | 0 |
| Obsidian | 673 | 111 | 31 |
| Crawl4AI | 995 | 280 | 35 |
| Archive desktop | unavailable | unknown | unknown |

Removing pip and its vendored packages cleared seven app findings, including five high entries. The app's locked dependencies remain installed. All 19 disposable runtime tests passed, and the exact candidate `forgetfulme-test:b1258a3cddfe` was deployed to five app services. Final image: `sha256:23a20415044e90137a535527b1ca7f114f9be6073f92ef2121e3f0e1c07ca34b`. Runtime maintenance requiring package changes must rebuild and test the image.

Remaining app GCC/zlib scanner findings require reachability review and a patched base when available. Debian trackers currently list affected trixie packages: [GCC CVE-2026-95619](https://security-tracker.debian.org/tracker/CVE-2026-95619), [zlib CVE-2026-85091](https://security-tracker.debian.org/tracker/CVE-2026-85091). No blanket vulnerability-free claim is made.

The running archive desktop image `sha256:a2b034a967e2ff88b4c0308097f2c2c466f0086cba7954e4cd924939eb875a7e` is absent from local image storage. Scout cannot scan it. A read-only installed Python version inventory was collected, but does not replace its missing OS audit. Do not stop/recreate this service until a recoverable compatible image is available. No companion images were updated in this delivery.

Next: recover archive image reproducibility; triage critical/high companion findings against actual packaged binaries; select and test compatible same-major patched images in isolation with matched data/config restore, startup and rollback checks before production rollout. A read-only PostgreSQL registry digest lookup failed fetching registry metadata; no new image was pulled or deployed by that check.
