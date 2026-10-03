# 实施与验证计划

## 状态与前置条件

- [x] 未来流程授权：beta 成功且仍对应当前 PR commit 时自动合并，失败 Bark。
- [x] 部署范围：合并后发布 GHCR 正式镜像/latest，不更新运行容器。
- [x] 启动子任务已有默认入口/临时 PG/HTTP/迁移/取消清理实现，本机 arm64 实证与离线检查已完成，保留代码与证据。
- [x] 用户回复“开始”批准本次收敛后的最终规划摘要，父任务已转 in_progress；现有子任务实施授权不扩展为 bootstrap PR 合并授权。
- [x] 开始前加载 PRD/design、backend specs 与三份 research；使用 feat/beta-review-release。本次开发不手工合并 main；未来可信控制器按已授权条件合并其他候选。
- [x] GitHub BARK_URL 配置/hosted runner 可达性是实际 delivery 依赖；缺少 Secret 不阻止 mock/dry-run。

## 实施顺序

1. 调整 CI/publisher 的 channel/tested SHA/version：main 正式，可信同仓 PR/受控分支 beta；两个 package 同版本、两架构，beta 不触碰 latest，复用已测试 artifacts。
2. updater 候选改 beta；保留 pin/tag/commit 与 dispatch/idempotency。复用启动子任务门禁，再添加 adapter 镜像内 suite与最小 stub/RPC 地址闭环；两 native job 在保存前完整检查。
3. main 可信 workflow_run 控制器校验成功 run/job/verify/index、PR head/base；共享 concurrency，普通 REST merge 带 expected SHA，回读成功后显式 dispatch main（expected_main_sha/source_pr）。正式 run 绑定 expected commit，latest 前再读 main；不绕过 strict protection或执行候选代码。
4. 单独实现失败通知路径：beta 早期失败无 artifact/index 也通知；合并后的 main 失败在 PR closed 时仍按 source_pr/expected_main_sha 关联。仅失败用 Secret 发 Bark，先 dry-run/模拟接收；有界重试、响应验证与脱敏。不通知成功、fork 或正常过期跳过。
5. 复用现有 unittest Git/registry/GitHub fixture：stable/beta、准确 SHA、fork/draft/changed head/base、verify skipped/neutral、索引缺失、merge 拒绝/不确定、merged 后 dispatch 失败，以及无产物失败/closed PR main失败的通知。补运行闭环真正失败的检查，不重复实现启动 fixture。
6. 同步 README 中英文、docs/AMAP.md 与质量规范；beta 清理延期，记录 bootstrap/Secret/真实联调依赖。

## 验证与交付

- [x] 完整 unittest、git diff --check、相关 Bash/Python/Elixir 语法与 actionlint。
- [x] 最终镜像实际 adapter/address/登录表单闭环；复用启动证据，但新增运行断言必须实际执行。所有测试无生产资源/真实 Key。
- [x] native amd64/arm64 PR checks、verify、beta 与双索引实际结果；mock/本机不替代云端。
- [x] Bark dry-run/模拟接收及脱敏/失败 gating；Secret/工作流生效后才报告真实 delivery。
- [x] current head 才能 merge；main dispatch expected SHA/current main 防陈旧；main 失败通知无需 open PR。正常稳定 run 不递归派发。
- [x] stable/latest 未被 beta 改写，retention 回归确认 beta 不挤占正式十组。
- [x] Trellis full-scope review。提交/push/PR 后报告分支、PR、结果与依赖，等待用户审阅；不借未来自动化授权合并 bootstrap PR。

## 停止与回退

来源不可信、索引不完整、保护拒绝、head/base 变更时停止相应写入；区分正常陈旧跳过与实际失败。合并结果不确定先回读，不重复 merge；dispatch 成功不代表发布完成。只回退本任务源码，不更新运行容器，不删除既有镜像；通知结果不确定不盲目重发。

历史本地结果：131/131、实际arm64整链及故障/TERM通过、Trellis全域审查通过；最终139/139、双原生架构与真实Bark闭环已完成，见validation.md。

2026-10-03最终整合：用户明确回复“合并，验证”，已授权本次bootstrap分支/PR合入并验证GHCR。整合main c8a6e83（PR9）地址-only修改，保留共享prepare、两个地址补丁与原生Dockerfile；删除品牌词/法律端点额外门禁，以真实登录表单、迁移和compiled地址RPC验收。旧品牌镜像测试记录仅为历史结果；最终以本次云端运行结果为准。

## Automatic-main failure notification correction

1. Add one always main-CI finalizer after checks/build/verify/publish; first perform a native boolean notification decision for every run so beta finalizer succeeds without Secret access. Notify only main image publication failures; preserve metadata/check-only/fork exclusions.
2. Reuse release_control readonly report + existing Bark sender; confirm source PR against actual merged main when readable, otherwise preserve basic run notification. Do not add credentials/dependencies or alter runtime checks. Stable workflow_run observer relinquishes main notifications to avoid duplication.
3. Reproduce absent-bot-observer boundary in tests, validate report/condition/ownership and controller/Bark regressions/actionlint. Push same-task candidate and verify beta + installed controller ordinary auto merge/dispatch + final stable/latest.
4. Use isolated check-only probe branch’s GITHUB_TOKEN to dispatch main with a valid stale expected SHA, proving early failure blocks build/artifacts/publication and CI finalizer sends one verified Bark. Remove probe resources and verify latest unchanged. Only then finish/archive.

## 最终验收状态

- [x] PR13 beta37081881736、控制器37082367599自动合并、正式37082388229的双架构真实启动/105迁移/adapter34和stable/latest深验通过。
- [x] 真实bot main失败37083060335早期拒绝stale SHA，build/pub跳过、artifacts0；独立收尾job dry-run通过，Bark sent/1次/HTTP200及JSONcode200。
- [x] 失败后两包latest及main未变；check-only probe不通知，临时分支/worktree/文件已清理并验证不存在。
- [x] 独立139/139、actionlint/AST/JSON/diff通过，文档/spec同步；全部AC满足。收尾证据仅本地任务分支提交，不触发额外正式发布。
