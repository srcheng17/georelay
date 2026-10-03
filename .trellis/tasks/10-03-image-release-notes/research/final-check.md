# Final independent workflow and Release check

- Date: 2026-10-03
- Reviewer: integration_check (trellis-check role; separate from the Release implementer)
- Active parent: 10-03-application-owned-geocoding; child: 10-03-image-release-notes.
- Scope: parent/child PRD, design, implementation plans and check manifests; CI, repair and beta-control workflows; publisher receipt, recorder, controller/updater completion gates; permissions, bootstrap and trust boundaries. App/adapter and compiled fresh/legacy validation remain with the other reviewer/root to avoid duplicated work.
- Authorization: implementation approved. No GitHub writes, real notifications, image publication, merge or production operations performed.

## Findings (fixed)

None. No new mechanical product issue required an edit in this review. The previous independent review's stale-PR, unchanged-renamed-note and frozen-baseline fixes are present in the actual code paths and regression cases.

## Findings (not fixed)

No newly confirmed code blocker in the reviewed scope.

The following are explicit external acceptance gates, not locally fixed code defects: native GITHUB_TOKEN exact-source tag/Release writes for workflow-changing beta and stale formal sources; reviewed trusted-main writer enablement; actual cloud native amd64/arm64 publication and anonymous package pulls. This review did not exercise them and does not claim they passed.

Task artifact planning-era status paragraphs still describe work as not implemented. Root was notified to append the current authorization, in-progress status and actual verification evidence during final task reconciliation. Root is synchronizing the specs and final test evidence concurrently; this reviewer did not overwrite those files.

## Behavior verified against code

- `ci.yml` executes the recorder on a fresh runner with main checkout and persist-credentials false. Candidate publication remains contents:read; writer gets contents:write and explicit actions/checks/packages/PR reads. No candidate checkout, executable artifact, cache or module is loaded into the writer. Candidate workflow changes still require repository review: trusted Python checkout does not independently make an editable same-repository workflow trusted.
- Missing trusted-main recorder fails bootstrap_not_enabled; there is no privileged candidate fallback. 401/403 during exact-ref or Release writes produces tag_permission/release_permission, without a PAT/App or retargeted source.
- Recorder validates original attempts/{attempt} run/jobs APIs, repository/event/source/title/workflow, completed predecessor jobs and the Actions app15368 verify check/run/job linkage. The direct original run may still be in_progress without creating a completed-run dependency cycle.
- Receipt uses an exact run/attempt/source/version artifact name, bounded archive and single bounded JSON member, expiry/source/identity checks and in-memory text reading. Both fixed indices, architectures, manifests/config SHA256, OCI identities, architecture tags and official pin/tag are independently verified. Receipt alone is not publication authority.
- Exact tags are resolved, reread and never moved. Existing owned records preserve manual surroundings, validate frozen baseline schema/ancestor/pin/tag/previous stable record, and freeze note text. Unknown API failures are not absence; lost write responses use readback. PR links are optional when current association becomes unprovable.
- Stable GitHub latest eligibility rereads current main/pin and both actual latest digests. Beta, skipped and failed aliases cannot newly become latest. Publisher, writer and retention use the shared publication concurrency group; fixed and floating results remain separate.
- Controller includes release-record and rereads current PR/head/base/draft and protection before its preexisting expected-head merge endpoint. Main direct finalizer and notification finite allowlists include recording failures; beta/no-op finalizer success remains intact.
- `repair_proof` binds a successful main release-only run to original run/attempt/source/version and actual Release/index evidence; every original non-record job must be completed/success. Build, verify, publisher/alias or other failure cannot be repaired into readiness. All-success originals with a now-missing record can be restored without bypassing a failed gate.
- Updater suppresses pending publication/repair duplicates and polls repair history. After proven repair it explicitly dispatches restricted trusted beta-control reevaluation, so no workflow_run observer is required. Release-only has no build, push, candidate executable download, alias promotion or deployment.
- Maintenance documentation matches writer/repair CLI inputs, 90-day requested artifact retention and repository-limit caveat, bootstrap boundary, fixed/floating outcomes, and native-token limitation.

## Verification

- Lint/syntax: pass. Independently ran git diff --check, bash -n scripts/publish_images.sh, and AST parsing of record_release/release_control/update_release/image_context/notify_bark.
- Workflow syntax/dependencies: pass. Parsed all five workflows with YAML BaseLoader and checked each job needs reference; explicit on/jobs structures are present. No actionlint executable is configured locally, so this is YAML/dependency validation rather than a live Actions run.
- TypeCheck: not applicable; this standard-library Python repository has no configured type-check command. No type-check success is inferred from syntax parsing.
- Tests: full repository and compiled-image runs are owned by root and were not repeated here. Earlier independent focused evidence is recorded in implementation-review.md: 85 cases (18 recorder, 26 controller, 10 updater, 5 image-context, 19 publisher, 7 fake/loopback notification), including the three fixes. Root must attach the current final full-suite/image results separately.

## Conclusion

No new code blocker found within the assigned publication/workflow scope. Local implementation readiness and actual external acceptance remain separate. This report does not authorize main merge or claim an online Release or production migration exists.
