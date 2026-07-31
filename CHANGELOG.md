# Changelog

## 1.6.0-inputfix5
- Recreate Chromium native IME contexts with blur/refocus after returning to the tab.

- Prevent the hidden raw-keyboard `InputSink` from stealing focus from the visible Guacamole text-input textarea after a tab switch.
- Continue releasing remote modifier keys in both raw-keyboard and text-input modes.
- Remove fake Git postimage blob IDs from the distributed patch.
- Make temporary-directory cleanup safe when `WORK_DIR` is supplied.
- Lock the patch to Guacamole 1.6.0 and use a local image namespace by default.
- Add package-integrity checks, OCI image labels, image inspection, and an `initdb` smoke test.
- Add Apache License 2.0 text and an expanded NOTICE.
- Expand state tests to cover focus ownership, coalesced events, hidden-page cancellation, and local form focus.

## 1.6.0-inputfix3

- Move global keyboard restoration from the wrong controller into `indexController`.
- Add source verification and upstream build tests.

## 1.6.0-inputfix2

- Withdrawn: contained a controller-scope error.
