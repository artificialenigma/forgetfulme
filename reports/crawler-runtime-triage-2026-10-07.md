# Crawler runtime triage and isolated candidate

Read-only inventory against exact deployed image 35eabc8e6da1 confirmed 22 of 25 critical rules have locations only beneath `/tmp/project/` (historical SBOM/project egg-info). Three refer to installed Debian Python 3.11, FFmpeg libraries, and TIFF. All original scanner entries are retained; this classification does not establish exploitability or clear the image.

The crawler imports Crawl4AI 0.9.4 from Python 3.12 site-packages. Installed NLTK 3.10.3, PyJWT 2.14.0 and AnyIO 4.14.2 differ from versions in historical metadata. Original litellm and sentence-transformers distributions are absent. The unclecode-litellm fork remains installed and requires code/advisory review independently of its distribution name. Playwright's bundled Node is running even though the historical Node finding points solely to the old SBOM; its executable needs a separate version/advisory review.

Python 3.11 is actually running supervisord. FFmpeg and TIFF libraries are installed, so removing obsolete metadata alone would not address these OS findings. Disposable offline apt simulation showed removal of Python 3.11 removes 16 Python/supervisor packages without removing Redis/browser packages.

Experimental `infra/crawler/runtime-candidate/Dockerfile` derives from the exact live crawler image, moves supervisor to Python 3.12 and removes Debian Python 3.11. Initial supervisor 4.2.5 failed startup due to missing pkg_resources; that candidate was never deployed. Supervisor 4.3.0 avoids that dependency on supported Python versions, per [upstream release notes](https://pypi.org/project/supervisor/). The corrected candidate image is `sha256:e208621bb2acb45e169712f4e5782245b486f5e3ad63e03563a65a76917d58b8`. This is a retained experimental image, not the production build recipe or release.

Docker Scout scan was rejected by automatic approval review because it may transmit image-derived metadata to an external service without specific payload/destination authorization. No workaround was attempted. Candidate scanning requires user approval before this step can proceed. No scan result or reduced critical count is claimed for the candidate. Production remains the previous tested 0.9.4 release.

Corrected candidate passed the full real extraction before/after restart and auth/config rejection matrix. Offline validation confirmed supervisor 4.3.0 and absence of /usr/bin/python3.11. Disposable resources were removed.

Next: after approved scan assess its exact findings and bundled Node/forked dependencies. Integrate a passing change into the maintained crawler build, save fresh baseline and test/deploy exact candidate only after required checks. FFmpeg/TIFF and desktop/archive recovery remain open.
