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
