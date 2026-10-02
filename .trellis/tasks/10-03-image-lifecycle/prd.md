# Image build and retention optimization

## Goal and authorization

Reduce unnecessary Docker builds and bound managed GHCR release history. The user approved the preceding recommendation with “帮我优化”: lightweight documentation/agent/Paseo checks, full image validation when needed, unchanged upstream automation, and retention of latest plus the newest ten complete releases.

## Background

ci.yml builds both architectures on every PR/main push. Main pushes publish immutable version tags and promote verified indexes to latest. publish_images.sh validates saved artifacts and freshness; update_release.py dispatches stable candidates without merging. There is no package retention policy.

## Requirements

- R1: Documentation, agent instructions, Trellis metadata, and paseo.json changes run Python checks and required verify without Docker builds/publication.
- R2: Runtime, patches, upstream pins, build/publication files, tests, and unknown paths retain full native amd64/arm64 validation. Explicit dispatch always performs full validation.
- R3: Preserve verified-artifact publication, latest freshness guards, and upstream detection. Push, successful CI, and continuing the task never authorize merging.
- R4: Retain latest and the ten newest complete release groups across both packages, including all referenced architecture manifests. Only positively identified older complete managed groups are deletion candidates; keep unknown, incomplete, and unassociated untagged records.
- R5: Cleanup defaults to preview; main-only weekly cleanup applies after an explicit merge. Serialize with publication and fail closed before writes on missing metadata/API errors.
- R6: Preserve primary checkout's local changes, other worktrees/tasks, production containers/databases, and credentials. No live image deletion in this task.

## Acceptance criteria

- AC1 (R1/R2): Real Git-diff regressions cover docs, runtime/mixed paths, renames/deletions, missing bases, and dispatch. Actual verify logic accepts only successful checks and intentional lightweight skips or successful required builds.
- AC2 (R3): Existing publisher/updater regressions pass. Upstream publication remains dual architecture. PR stays unmerged with auto-merge disabled.
- AC3 (R4/R5): Fake API/registry regressions cover pagination, ten-group selection, old latest, shared children, incomplete/unknown records, preview with zero DELETE, safe deletion order, and read failures with zero writes.
- AC4: Read-only public registry inventory/preview; disclose any package API access limitation. No live DELETE.
- AC5: Both READMEs, release guide, and executable specs match behavior. Local checks pass and an independent branch/PR has actual CI evidence.

## Out of scope

Production deployment, merging any PR, deleting live versions now, arbitrary orphan cleanup, rebuilding publication artifacts, adding dependencies, or changing upstream auto-update behavior.
