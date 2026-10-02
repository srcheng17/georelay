# 提交计划

分支：`feat/beta-review-release`。本批全部为本会话及协作agent负责的任务改动；未发现未识别脏文件，不包含另一worktree的prepare/branding改动。

计划一个完整功能提交：

`feat(ci): verify beta images before merge and formal publication`

文件清单：

- `.github/workflows/ci.yml`
- `.trellis/spec/backend/quality-guidelines.md`
- `README.md`
- `README.zh-CN.md`
- `docs/AMAP.md`
- `scripts/ci_changes.py`
- `scripts/publish_images.sh`
- `scripts/update_release.py`
- `tests/test_ci_changes.py`
- `tests/test_publish.py`
- `tests/test_retain_images.py`
- `tests/test_update_release.py`
- `.github/workflows/beta-control.yml`
- `.trellis/tasks/10-03-beta-review-release/check.jsonl`
- `.trellis/tasks/10-03-beta-review-release/commit-plan.md`
- `.trellis/tasks/10-03-beta-review-release/design.md`
- `.trellis/tasks/10-03-beta-review-release/implement.jsonl`
- `.trellis/tasks/10-03-beta-review-release/implement.md`
- `.trellis/tasks/10-03-beta-review-release/prd.md`
- `.trellis/tasks/10-03-beta-review-release/research/auto-merge.md`
- `.trellis/tasks/10-03-beta-review-release/research/beta-retention.md`
- `.trellis/tasks/10-03-beta-review-release/research/runtime-testing.md`
- `.trellis/tasks/10-03-beta-review-release/runtime-results.json`
- `.trellis/tasks/10-03-beta-review-release/task.json`
- `.trellis/tasks/10-03-beta-review-release/test-results.json`
- `.trellis/tasks/10-03-beta-review-release/validation.md`
- `.trellis/tasks/10-03-main-image-smoke/check.jsonl`
- `.trellis/tasks/10-03-main-image-smoke/design.md`
- `.trellis/tasks/10-03-main-image-smoke/implement.jsonl`
- `.trellis/tasks/10-03-main-image-smoke/implement.md`
- `.trellis/tasks/10-03-main-image-smoke/prd.md`
- `.trellis/tasks/10-03-main-image-smoke/runtime-results.json`
- `.trellis/tasks/10-03-main-image-smoke/task.json`
- `.trellis/tasks/10-03-main-image-smoke/validation.md`
- `scripts/image_context.py`
- `scripts/notify_bark.py`
- `scripts/release_control.py`
- `scripts/runtime_geocoder_stub.py`
- `scripts/runtime_locations.exs`
- `scripts/test_main_image.sh`
- `tests/test_image_context.py`
- `tests/test_main_image.py`
- `tests/test_notify_bark.py`
- `tests/test_release_control.py`

验证：完整131/131；真实本机arm64主应用默认入口、新PG105迁移、HTTP/许可/compiled地址契约，以及坏入口、超时、TERM均符合预期且零残留；已打包adapter34/34；actionlint/Bash/Python语法/diff/Trellis全域审查通过。详细证据见validation.md。

待验证：云端native amd64/arm64、beta双索引、Actions token保护规则读取/受保护merge/main dispatch、真实Bark（缺BARK_URL）。本次没有外部写入，不将本地fixture与dry-run说成线上验收。

确认后只执行本计划的git add与新git commit，不amend、不push、不合并、不启用当前PR auto-merge。后续push/创建PR须报告分支、PR与验证并等待用户审阅；本次bootstrap PR仍需明确合并授权。

Trellis来源：[trellis-continue/SKILL.md](../../../.agents/skills/trellis-continue/SKILL.md)要求按workflow必需步骤顺序执行；workflow3.4第5项明确“Present the plan once, ask for one-shot confirmation”。回复“行”或“ok”执行；回复“我自己来”则停止自动提交。

用户已回复“行”确认本计划（2026-10-03）；本次仅执行一个本地新提交，云端与通知验收继续待办。
