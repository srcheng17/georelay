# Verified starting points

- Required aggregate is verify; workflow path exclusions can leave it pending.
- Publisher tags: stable upstream tag-georelay-fullSHA plus -amd64, -arm64 and latest. It publishes saved checked images and validates both indexes/freshness.
- Publication concurrency is ghcr-publication-${{ github.repository }}. Cleanup must share it.
- update_release.py dispatches ci.yml publish=true from pin-only upstream/<tag>, never merges.
- test_publish.py extracts the native UID-check loop with indentation-sensitive regex; preserve its indentation.
- update_release.command/github provide bounded secret-safe patterns. JSON wrapper cannot directly decode empty DELETE responses.
- Anonymous registry reads work. Local Packages API previously lacked read:packages (403); do not request or print tokens. Workflow package-admin permission must be documented.

## Concurrent main integration

Main advanced to 3e6cbfa during this task and the remote is now srcheng17/georelay. Publisher packages are ghcr.io/<owner>/<repository> and <repository>-adapter; the managed release suffix is -georelay-<SHA>. Root MODIFICATIONS.md enters prepared images and TRADEMARK.md is a strict legal-validation input, so both require full builds. Preserve the other session's runtime/branding changes, merge them only into this feature branch, update retention to the publisher convention, and leave legacy packages unchanged.
