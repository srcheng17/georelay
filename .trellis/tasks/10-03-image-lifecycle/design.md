# Design

## Change boundary

The gaps live in CI job gating and GHCR version lifecycle. Add stdlib change detection and retention commands with boundary regressions. Modify CI and add scheduled/manual retention. Keep the runtime, publisher, and upstream updater unchanged. Parent owns docs/specs; implement agent owns workflow/scripts/tests.

## CI

Keep workflow triggers so required verify always exists. A lightweight checks job checks out full history, runs Python/whitespace checks and reports image_required=true|false. Compare PR base or push before with the tested checkout; include removed/renamed paths. Only docs/agent/Paseo/Trellis paths are exempt. Unknown paths, missing/zero base, ambiguous events, and dispatch require images.

Matrix build depends on checks and the decision. Preserve upstream tests, native architecture, nonroot/license/health assertions and artifact flow. Always-run verify requires successful checks plus successful required builds, or exactly skipped intentional lightweight builds. Missing decisions, failures, and cancellation fail. Publish also requires successful required builds and the existing event authorization.

## Retention

Inventory both packages through paginated GitHub Packages APIs; validate repository/owner and support User/Organization owners. Managed tags follow vMAJOR.MINOR.PATCH-amap-40hex and -amd64/-arm64. A complete release exists in both packages with exact linux/amd64 and linux/arm64 indexes matching its architecture tags and available version records.

Protect the ten most recently created complete groups, both latest indexes and children, and the complete latest group when identifiable. Protect other retained tags and their referenced children, including shared digests. Unknown/incomplete/unassociated versions stay. Malformed manifests or missing referenced records abort planning before any DELETE.

Validate the full two-package plan before writes. Delete obsolete indexes before children so interruption leaves retained indexes intact. Stop on DELETE errors. The command defaults to preview and accepts explicit --apply, emits a safe report and never prints remote error bodies or credentials.

Main-only weekly/manual workflow uses GITHUB_TOKEN package admin capability and the publication job concurrency group ghcr-publication-${{ github.repository }}. Manual preview defaults true. Never apply live during implementation.

## Tradeoffs and rollback

Use existing stdlib/subprocess patterns without a registry framework/dependency. The ten-group policy governs complete managed history; incomplete/unrecognized/unassociated records may remain for manual review. Users needing older pins must mirror them. Missing package permissions fail closed.

Disable/revert retention to stop future deletion; deleted package versions cannot be automatically restored. Reverting CI gating restores unconditional builds. The unmerged branch changes no deployed service.
