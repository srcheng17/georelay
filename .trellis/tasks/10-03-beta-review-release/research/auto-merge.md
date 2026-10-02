# Beta 成功后的自动合并与 main 正式发布

## 授权与研究边界

用户最新要求 beta 成功且 PR commit 未变化时自动合并，失败才通过 Bark 通知。本文件只研究最小合并与正式发布链路；用户现已确认部署仅指 GHCR 正式镜像/latest，不更新运行容器。没有启用仓库设置、合并 PR、推送分支、触发线上 workflow 或更新容器。

## 当前仓库的只读证据

2026-10-03 通过 `gh api` 读取 `srcheng17/georelay`：

- 默认分支为 `main`；`allow_auto_merge=false`。
- `allow_merge_commit`、`allow_squash_merge`、`allow_rebase_merge` 均为 true；没有 required linear history。
- main branch protection 要求 `verify`，expected app ID 为 15368（GitHub Actions）；`required_status_checks.strict=true`。
- `enforce_admins.enabled=true`；required approving review count 为 0；没有 push actor restrictions。
- `.github/workflows/ci.yml:8-13` 已支持 `workflow_dispatch` 和 `publish` boolean 输入；当前 publication 权限仅有 contents read/packages write，自动合并控制器需要单独声明其权限。

这些是研究时的状态，不代表将来不能漂移。实施不能通过放宽保护或启用管理员 bypass 来实现自动合并。

## 最小方案：完成后调用普通 REST merge

GitHub 的仓库 `allow_auto_merge` 开关控制平台“等待 reviews/status 后合并”的 auto-merge 功能，不是所有 API merge 的总开关。当前 beta workflow 成功后已经满足条件，可信 main 控制器可以直接调用：

```text
PUT /repos/{owner}/{repo}/pulls/{number}/merge
body: {"sha": "<已测试的 PR head SHA>", "merge_method": "merge"}
```

官方接口的 `sha` 明确要求 PR head 必须匹配；不匹配返回 409。接口返回 200 后，仍须检查 `merged=true`、有效 merge commit SHA，并回读 PR 的 merged 状态。API 的成功请求/HTTP 200 本身不能替代这些检查。403、405、409、422 都不应被当成成功。

因此不需要启用 repository auto-merge，也不需要 `gh pr merge --auto`、新 PAT 或 GitHub App。当前仓库允许普通 merge，可以沿用该方法避免新增策略选择；如果将来保护要求 merge queue/stacked PR，则该同步接口不适用。GitHub 当前文档推荐 async merge，但当前无队列/stacked PR 需求，轮询 async 状态没有必要加入本任务。

### 必需的合并门控

可信 main 上的独立 `workflow_run` 控制器只读取 API/registry 元数据，不 checkout/运行 PR 代码，也不执行候选 artifact 中的脚本。

合并前必须同时确认：

1. 触发 run 来自预期 workflow、同一仓库与可信同仓分支；不是 fork。关联 PR 的 head/base repository 都是目标仓库，base ref 是 main；PR open、非 draft。
2. 两个原生架构的镜像运行测试、汇总 `verify` 与 beta publication/两个 package 索引回读全部成功。只检查 workflow conclusion 或任意名为 verify 的成功 check 都不足；需要对应已测试 run/head、GitHub Actions 来源和实际 job。verify 必须明确 success，即使 GitHub branch protection 允许 skipped/neutral，也不能当作本任务的测试成功。
3. 当前 PR `head.sha` 等于 beta 的 tested SHA；源码 checkout、OCI revision、beta 版本与实际测试 SHA 一致。
4. mergeability 已确定且允许合并；unknown/pending 应有界重新读取，不能默认通过。冲突、blocked、draft 或其他未满足保护的状态停止合并。
5. 读取当前 main SHA，核对 PR 分支包含当前 main（例如 compare 的 merge base 等于当前 main SHA），保留现有 strict verify protection。若 main 在测试后更新，重新测试最新 base/head，不自动 update/rebase 后沿用旧 beta 成功结论。
6. 在共享的仓库合并 concurrency group 中最后一次重读 PR head/main 与条件，再发送带 expected head SHA 的 REST merge。

REST merge 只支持 expected head，不支持 expected base SHA；读取 base 与调用之间仍可能有竞态。当前服务器端 strict status protection 是 base freshness 的最终原子门控，不能把客户端 compare 当成完全消除竞态。REST保护设置读取需要管理权限；实现使用固定只读GraphQL ref.branchProtectionRule 查询 requiresStatusChecks、requiresStrictStatusChecks、isAdminEnforced 与 requiredStatusChecks 的 verify/Actions app来源。当地既有gh身份已回读通过；Actions GITHUB_TOKEN权限仍需云端验证，读失败拒绝merge并通知，不新增管理员凭据。独立compare仍检查base freshness。

若其他用户已合并或 API 返回结果不确定，先回读 PR 和 merge commit，不盲目再次合并，也不能把“当前 head 已变”解释成旧候选仍可合并。

## GITHUB_TOKEN 合并后需要显式 dispatch main

官方说明：GITHUB_TOKEN 导致的普通 push 不会创建新 workflow run。REST merge 对 main 的更新也属于这一限制，因此不能依赖现有 `on: push: branches: [main]` 接着构建正式镜像。

`workflow_dispatch` 和 `repository_dispatch` 是官方列出的例外，使用同一个 GITHUB_TOKEN 也会创建新 run。最小方案在 merge 成功回读后调用现有 CI：

```text
POST /repos/{owner}/{repo}/actions/workflows/ci.yml/dispatches
body: {
  "ref": "main",
  "inputs": {
    "publish": true,
    "expected_main_sha": "<API 返回的 merge commit SHA>",
    "source_pr": "<已合并 PR 编号>"
  }
}
```

`expected_main_sha` 与 `source_pr` 是建议增加到现有 workflow 的最小输入，不是 GitHub 内置参数；后者用于合并后正式 run 的失败通知关联，必须校验 PR merge commit 与 expected SHA。dispatch 的 `ref` 仅能指定分支/tag，不是原子锁定 merge commit；工作流开始时应核对 `GITHUB_SHA`、实际 checkout SHA 和 expected SHA，并在 latest 推广前再次检查 current main。main 已变时，不把旧 merge 的候选冒充当前 main 正式版本；应明确跳过/失败并报告阶段，后续最新 main 用自己的完整检查发布。

正式 run 从合入后的 main 源码重新构建、运行双架构镜像测试，再发布正式版本和 latest。不要直接把 PR head 的 beta 标签改成稳定标签，因为实际 merge commit SHA 与源码来源不同。发布继续复用该正式 run 经过测试的产物；latest 根据 main pin，而不是尚未合入的新官方 release。

当前官方 REST 文档的 dispatch 成功为 HTTP 200，并返回 workflow_run_id/run_url/html_url；历史 API 版本可返回 204。实现应按项目所用 API 版本处理成功响应，不能仅硬编码最新文档的一个状态码，也不能把“已发出 dispatch”报告成“正式镜像已成功发布”。有 run ID 时直接关联；没有时按 expected commit 与 workflow 元数据确认后续 run。

### 最小权限

可信控制器的 GITHUB_TOKEN 可按 job 声明：

- `contents: write`：普通 REST merge 接口所需权限。
- `actions: write`：workflow dispatch 接口所需权限，并可读取 run/job 元数据。
- `pull-requests: read`：读取 PR 关联与当前 head/base 状态。
- `checks: read`：若直接读取 check runs，以验证 required verify 与来源。
- packages 的读取权限仅在需要验证私有 GHCR 索引时添加；BARK_URL 仅失败通知发送步骤可见。

这不需要新 token。组织/仓库 Actions policy 若限制 write token，仍需实际受保护合并与 dispatch 联调才能确认；403 时报告权限问题，不改用管理员 token 绕过保护。

## 失败通知与幂等边界

- beta/镜像运行测试失败、满足门控后的 merge 操作失败、dispatch 失败或正式发布失败分阶段进入 Bark；成功不通知。只观察 GHCR 发布，不更新生产容器。
- head/base 变化、PR 关闭/draft 的成功候选仅跳过合并，不将过期状态伪装成测试失败或发成功审阅通知。
- PR merge 回读已成功但 dispatch 失败时，报告“已合并，正式发布触发未确认”；不承诺回滚 merge，不盲目重新 merge。
- workflow_run 控制器只对 beta 候选执行 merge；main 正式 run 仅观察发布结果，防止递归合并/派发。
- 初次新增可信 main 控制器仍需用户明确批准 bootstrap PR 合入 main 后才生效，不能由尚未生效的工作流合并自身。
- 失败路径独立于 merge success gates：beta 测试失败没有 artifact/index 仍通知；main 发布失败时 PR 已 merged/closed，按 source_pr/expected_main_sha 关联，不要求 open PR。

## 最小离线回归建议

复用现有 publisher/updater unittest fixture，加一个控制器 API fixture，覆盖：

- beta 当前 head、base 最新、GitHub Actions verify success、双架构/索引成功：只调用一次含 expected SHA 的 merge，并成功回读后 dispatch main。
- changed head、fork、错误 base、draft、unknown/conflict mergeability、旧 base、verify skipped/neutral/failed 或检查来自别的 run/app：零 merge。
- REST 409/405/403、merged=false、无效 merge SHA：零 dispatch，报告对应失败阶段。
- merge 成功但 dispatch 失败：保留 merged 事实并失败通知；不会重复 merge。
- main dispatch 的 expected SHA 不匹配、latest 推广前 main 改变：不推广旧 latest。
- 成功 beta→merge→main 发布不发 Bark；早期失败无 artifact/index 仍通知，closed PR 的 main 失败按 source_pr/expected_main_sha 通知；payload 脱敏，稳定 run 不再派发自己。

## 官方来源

- [Merge a pull request](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request)：contents write、expected head `sha`、错误码、成功 response。
- [Automatically merging a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)：平台 auto-merge 需要仓库开关，区别于直接合并接口。
- [Triggering a workflow from a workflow](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow#triggering-a-workflow-from-a-workflow)：GITHUB_TOKEN 事件防递归规则及 dispatch 例外。
- [Create a workflow dispatch event](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)：actions write、ref/inputs 和最新成功 response。
- [Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run)：workflow_run 的默认分支要求及不可信代码/write token 风险；workflow_dispatch 的 default branch 条件及 SHA/ref。
- [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)：strict 要求分支与 base 最新，以及 branch protection 对成功/skipped/neutral 的默认接受范围。
