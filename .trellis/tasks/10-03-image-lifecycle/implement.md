# Execution plan

1. Read release specs and confirm isolated baseline: 62 Python tests pass on Python 3.13.
2. Implement change detection/checks/verify gating; test real Git transitions and actual workflow verification logic.
3. Implement conservative grouped retention and weekly/manual workflow with fake APIs/manifests. No live deletes.
4. Parent updates READMEs, release guide, and executable release spec.
5. Run targeted/full unittest, git diff --check, shell/workflow syntax checks, and read-only public registry inventory.
6. Dispatch Trellis check reviewer; fix concrete findings and rerun affected checks.
7. Commit scoped Conventional Commits; archive/record only this task. Push independent branch, open PR with summary and Test plan, inspect actual checks. Never merge/enable auto-merge.

Ownership: implement agent owns .github/workflows/ci.yml, .github/workflows/image-retention.yml, new scripts and tests. Parent owns README.md, README.zh-CN.md, docs/AMAP.md, .trellis/spec/backend and task artifacts. Both share the isolated worktree; do not revert each other's changes.

8. Concurrent main advance: sync only into this feature branch, preserve GeoRelay runtime/branding changes, align retention with current publisher names/tags, and require legal/modification input builds. Repeat affected full-scope review and CI before PR completion.
