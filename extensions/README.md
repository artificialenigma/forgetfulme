# Forgetful Me browser add-on

## Chrome: install and connect

1. Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and select this repository’s `extensions/chrome` directory.
2. Sign in at http://localhost:8080 and open **Browser devices**. Create a device such as “Laptop Chrome” and copy the one-time token.
3. Click the add-on icon. Enter the server address and device token, set excluded domains if wanted, check **Collect new visits**, and save. Approve access to the configured server.
4. Browse a public page. Visits are pushed in batches every minute. **Push queued visits now** sends one batch immediately. View them in the app’s **Browsing history** page.
5. Optional: **Import last 30 days** imports locally recorded Chrome visits. It runs in resumable steps on the minute timer and can take time for a large history. Chrome Sync visits marked nonlocal are skipped; install on each device for collection from that device.

Only HTTP(S) URLs, titles, and visit timestamps are collected. No page bodies, cookies, passwords, or form contents are read. Chrome’s history API does not record incognito visits. Domain exclusions include subdomains. The app’s own origin is excluded. URLs can contain sensitive query parameters; use exclusions before importing. History import needs collection enabled.

The token and queue are stored in extension-local storage, not Chrome Sync. Failed pushes keep the queue; repeated visits with the same Chrome visit ID are deduplicated by the server. The queue holds at most 10,000 records; overflow is reported, and new events cannot be saved until space is freed. Imports stop with an error on pathological density rather than silently truncating. Clearing the queue also cancels an import. Changing server or token clears pending data and cancels imports. Pausing stops collection/import, but already queued records may still be sent. Revoking the token in Devices stops ingestion immediately. Back up the central database, and treat device tokens as secrets.

Remote servers require HTTPS; HTTP is accepted only for localhost/loopback. The current stack listens on the local machine, so another device needs the planned server deployment. This version provides collection and a latest-200 history view; page scraping, full search, and automatic Obsidian note export are separate work.

## Safari source and packaging

`extensions/safari` shares collection and settings code with Chrome but uses a nonpersistent background script and no `history` permission. If the browser has no history API, it records completed, nonprivate HTTP(S) tab loads after installation. It cannot import Safari’s existing browsing history. Reloading a page records a new visit. Safari website access must be granted for the pages you want to collect and for your server.

With a licensed Xcode installation, convert the source into a native Safari extension project:

```sh
xcrun safari-web-extension-converter "$PWD/extensions/safari" --project-location "$PWD/safari-build" --app-name "Forgetful Me"
```

Build and run the generated project in Xcode, enable the extension in Safari Settings → Extensions, grant website permissions, and enter a separately created device token. Safari packaging and runtime behavior have **not** been verified on this machine: Xcode currently requires the user to review and accept its license. Review converter compatibility diagnostics before building. Do not commit generated signing identities or tokens.

## Verification

```sh
node scripts/addon_test.cjs
python3 scripts/history_smoke_test.py
```

The second command needs the running Docker stack and local `.env`; it creates a synthetic device and visit, checks ingestion/deduplication/validation/revocation, and deletes its fixtures. Browser installation and live browser event capture still need a manual test after loading the extension.

References: [Chrome history API](https://developer.chrome.com/docs/extensions/reference/api/history), [Safari extension compatibility](https://developer.apple.com/documentation/safariservices/assessing-your-safari-web-extension-s-browser-compatibility).
