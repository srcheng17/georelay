# Release implementation independent review

- Date: 2026-10-03
- Scope: read-only product review of publication receipt, trusted writer, controller, updater and workflow integration. Reviewer previously implemented the adapter, not Release code.
- Authorization: implementation approved; no GitHub writes, notifications outside fake/loopback, publishing, merge or production operations performed.
- Status: three confirmed findings were reported immediately and fixed by the Release implementer; final focused regression result recorded below.

## Confirmed findings and fixes

### P1 — Stale PR head blocked a valid fixed image record (closed)

Initially `notes` required the current beta PR head to equal the already-tested image source. A publisher receipt with `skipped/stale_source` or `skipped/stale_pr` therefore failed `pull_provenance` after the PR advanced, despite a verified complete fixed pair. That contradicted R5.

Fix readback: `scripts/record_release.py:491` now treats current PR association as optional, omits an unprovable PR link and retains exact source/run/attempt/image evidence. Current PR eligibility for merge remains separately enforced in `scripts/release_control.py:181,229`. Regression: `test_stale_pr_head_does_not_prevent_recording_verified_fixed_images` covers both stale receipt reasons, produces a non-latest Release and does not weaken image evidence.

### P2 — Pure rename could restate an old feature and satisfy the product-note gate (closed)

Initially every nonremoved `docs/changes/*.md` diff was rendered from current source without checking baseline contents. A pure rename of an unchanged old entry could both repeat prior features and satisfy `product_changes_need_notes` for an adapter code change. A read-only fake reproduced acceptance.

Fix readback: `scripts/record_release.py:455` reads modified/renamed entries against the fixed baseline path, including `previous_filename`, and ignores unchanged text. The product-change gate requires an actually changed fragment. Regression: `test_renaming_unchanged_old_note_cannot_claim_a_new_product_update` rejects adapter changes plus an unchanged renamed note.

### P2 — Frozen baseline metadata was reused without revalidation (closed)

A read-only fake created a valid owned record, changed only `meta.baseline.source_sha` to `not-a-commit`, kept the body text/hash intact and reencoded the marker. The initial `record(..., apply=False)` accepted that invalid baseline; `verify_record` also lacked a baseline check. This violated the fixed-marker and revalidation contract.

Fix readback: `scripts/record_release.py:323,360` validates exact baseline schema, commit identity, strict ancestry, historical pin, true first-parent semantics or prior stable tag/owned record as applicable. An unavailable baseline requires genuinely no parents. The existing baseline is validated and reused rather than reselected. Regression: `test_tampered_frozen_baseline_refuses_record_and_readiness_without_reselection` rejects both writer and readiness paths without writes.

## Cross-workflow evidence

- `original_run` uses original attempts/{attempt} run and jobs APIs; validates source/event/workflow/repositories, all prerequisite jobs and Actions app 15368 verify check/run/job linkage. In-progress original runs are allowed only after prerequisites and publisher complete.
- `read_receipt` matches the exact run/attempt/source/version artifact name, refuses missing/expired/duplicate or oversized artifacts, and reads one bounded JSON member in memory. No candidate archive is extracted or executed.
- `verify_images` independently validates both index digests, exactly amd64/arm64, architecture tag/descriptors/config SHA256 and OCI source/revision/version. Official stable pin/tag resolution is independently checked.
- `record` uses explicit absence only for HTTP 404, rereads exact source tags, never sets target_commitish or moves tags, preserves manual surroundings and handles lost write responses by readback. Baseline and note text freeze after creation.
- `is_latest` requires stable/promoted, current main/pin and both actual latest digests. Writer, publisher and retention share the publication lock. Beta, skipped and failed alias states cannot be newly marked latest.
- Direct CI recorder uses a fresh runner and trusted main checkout with persist-credentials false, no candidate artifact checkout/download, and minimal repository-write/read permissions. Publish remains without contents:write.
- `release-only.yml` has no build/push or executable artifact download. `repair_proof` revalidates original evidence and trusted successful main repair; other job/verify/publish failures remain blocking. All-success original runs with a now-missing record may be repaired without bypassing any failed gate.
- Updater suppresses duplicate pending builds/repairs and explicitly dispatches trusted beta-control reevaluation after a proved successful repair, so workflow_run is not the only path. Controller still checks draft, current PR/head/base, protection and expected head before its preexisting merge endpoint.
- Main direct finalizer includes release-record failures; notify stage/job whitelist includes the bounded Release category. Test notifications use fake/loopback only.
- Bootstrap missing-main writer fails with bootstrap_not_enabled rather than executing candidate writer. Tag/release write permission failures have fixed stage categories; no new token/PAT/App, tag retargeting or workflow permission expansion was introduced.

## Limits and remaining external gates

No remaining product-code blocker identified after the three fixes. Static/fake validation does not prove native GITHUB_TOKEN permission for workflow-changing exact-source beta tags/Releases, trusted-main bootstrap enablement, actual dual-architecture cloud publication or anonymous pulls. Those remain explicitly unverified and require the separately authorized reviewed enablement/publication path. This review does not authorize merging the current task; any task PR must remain draft until user review.

## Validation

Independent results: 85 focused cases passed (18 record, 26 controller, 10 updater, 5 image-context, 19 publisher, 7 notification). The first namespaced unittest invocation passed the 67 non-record cases but could not import the record module because its documented discovery convention imports a sibling by top-level name; corrected invocation `PYTHONPATH=tests python3 -m unittest test_record_release -q` passed the remaining 18. No product change was needed for this invocation issue. `git diff --check` passed. No remote writes were executed.
