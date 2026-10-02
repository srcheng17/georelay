# Validation

## Isolated baseline

- Branch: feat/image-lifecycle, based on origin/main add92b0.
- Primary checkout's pre-existing AGENTS.md/paseo.json are untouched.
- Python 3.13 full baseline: 62 tests passed (40.595 seconds). Existing fake patch-failure output and SQLite ResourceWarnings do not change the successful result.

## Read-only live GHCR preview

Anonymous registry GET requests confirmed both srcheng17/teslamate-amap and srcheng17/teslamate-amap-adapter have 7 public tags and 2 complete release groups. Both latest indexes contain linux/amd64 and linux/arm64. At keep=10 there are no older complete groups to delete.

The local GitHub credential cannot access the package-version inventory endpoint. This preview covers public tags/indexes, not untagged package records or the full REST deletion plan. Fake API coverage will validate package-version planning. No live DELETE or production operation was performed.

## Local implementation checks

- Full Python 3.13 suite: 78 tests passed (40.776 seconds): 62 existing, 6 CI gating, 10 retention.
- Real Git transitions and actual verify shell cover lightweight, runtime/mixed/unknown, deletion/rename, absent baseline, dispatch and success/failure/cancellation.
- Fake package/manifest APIs cover pagination, newest-ten selection, differing old latest groups, shared children, unknown/incomplete/unassociated protection, preview zero writes, index-first apply, read failure zero DELETE and deletion failure stop.
- actionlint v1.7.7 passed all three workflows; shellcheck integration disabled. Ruby YAML and existing shell syntax checks passed. Python compilation and git diff --check passed.
- All local links in both READMEs and docs/AMAP.md resolve.
- New retention CLI was run without --apply. It returned a sanitized access/metadata error with the local limited credential; no apply was attempted.

## Full-scope reviewer

Trellis check reviewed all changed code, tests, documentation and specs; no findings or fixes. Independent full suite: 78 tests passed (42.157 seconds). Whitespace, actionlint, bash syntax and Python compilation passed; no configured Python type checker.

Actual native amd64/arm64 and ExUnit results will be checked and reported on the final PR. No live retention apply is part of this validation.

## Concurrent main advance

Main advanced from add92b0 to 3e6cbfa while this isolated optimization was being implemented; another session renamed the repository and publication artifacts to GeoRelay. The earlier two-group preview covers legacy packages. Retention now targets georelay/georelay-adapter and -georelay- tags; legacy packages stay untouched. Root legal/modification inputs require full builds. The alias-based CLI preview did not produce a package plan; local package REST access is separately unavailable.

- GeoRelay integration full suite: 87 tests passed (45.585 seconds): 68 current baseline, 7 CI, 12 retention.
- Added cross-boundary regression executes the actual publisher with the existing fake Docker harness and compares its package/tag outputs with retention. Legal-file Git transitions and legacy preservation pass.
- Fresh anonymous GET preview: both GeoRelay packages have 4 public tags and 1 matching complete release group. Both latest indexes match their version index byte-for-byte; amd64/arm64 architecture tags match the index's child digests. No group is eligible at keep=10.
- Concurrent main run 37043924235 passed both native builds, verify and publish. This proves the imported main baseline; our optimization still requires its own PR run.
- Fresh full-scope integration review: no findings/fixes; independent 87-test suite passed (45.766 seconds), actionlint/whitespace/compile/bash checks passed.
- Canonical GeoRelay retention CLI was also run in default preview mode and stopped safely without a REST plan under the limited local credential. No live apply.
- Final native PR CI will be reported on the PR.

## PR #6 and latest main integration

- PR: https://github.com/srcheng17/georelay/pull/6; feat/image-lifecycle into main; open, auto-merge disabled.
- Initial native PR run 37046507508: checks and arm64 full validation succeeded; amd64 failed only the inherited fifty-cold-mainland-lookup test (baidu) at its one-second test deadline; verify correctly failed and publish was skipped. The actual failure is being investigated, not described as passed.
- Concurrent main advanced to d581c24 through documentation and architecture-task archival only. Synced it into the feature branch, retaining both tasks and every journal session. Git's automatic journal merge interleaved sections; restored complete chronological sections from their source commits.
- No runtime or adapter-test changes made during this integration. Primary checkout remains untouched; no live deletion, deployment or main/PR merge.

- Evidence-first timeout investigation: original adapter/test blobs match origin/main. Five isolated repetitions passed, retaining the unchanged one-second budget, 50 calls, peak concurrency >1 and <=4, and ordered identity assertions. AMap elapsed 0.605–0.644 s; Baidu 0.620–0.651 s. These macOS/Python 3.13/arm64 results do not reproduce or diagnose the amd64 runner timing. No runtime/test modification is justified by one runner failure; fresh native validation will test the synced branch.

- Main advanced once more to eb63e20 with only Paseo commit/PR metadata refinements. Imported those exact settings as well; retained imperative scoped commits, 72-character limit, Summary/Test plan and explicit manual merge policy. No lifecycle-specific settings rollback.
- Fresh full-scope reviewer: all 87 tests passed (46.036 s), including both fifty-cold-mainland subtests, with no timing-budget changes. Static scope/spec, actionlint, compilation, shell/whitespace checks and documentation links passed. Journal integrity confirmed: all main sessions preserved verbatim, complete chronological 1–12, unique fingerprints and accurate index.
- Spec review: existing CI/retention executable contracts remain current; this docs/settings-only integration introduces no new runtime or API contract.
