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
