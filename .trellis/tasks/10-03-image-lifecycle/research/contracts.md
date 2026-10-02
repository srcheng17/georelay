# Verified starting points

- Required aggregate is verify; workflow path exclusions can leave it pending.
- Publisher tags: stable upstream tag-amap-fullSHA plus -amd64, -arm64 and latest. It publishes saved checked images and validates both indexes/freshness.
- Publication concurrency is ghcr-publication-${{ github.repository }}. Cleanup must share it.
- update_release.py dispatches ci.yml publish=true from pin-only upstream/<tag>, never merges.
- test_publish.py extracts the native UID-check loop with indentation-sensitive regex; preserve its indentation.
- update_release.command/github provide bounded secret-safe patterns. JSON wrapper cannot directly decode empty DELETE responses.
- Anonymous registry reads work. Local Packages API previously lacked read:packages (403); do not request or print tokens. Workflow package-admin permission must be documented.
