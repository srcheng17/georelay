# Beta 发布链路验证记录

最终状态：全部验收通过。[PR13](https://github.com/srcheng17/georelay/pull/13) head `9e6ab09` 已由 GitHub Actions bot 自动合并至 `11e2e9d`；beta `37081881736`、控制器 `37082367599`、自动正式发布 `37082388229` 成功。原生 amd64/arm64 均通过主应用真实启动/HTTP200/105迁移/adapter34，正式版本与 latest 深验通过；真实 bot main 失败 `37083060335` 已验证独立收尾通知、零产物与 latest 不变。完整证据见文末及 [cloud-validation.json](cloud-validation.json)。下方旧本地/bootstrap/PR12记录保留为历史，不是当前未完成项。

历史整合状态：用户已明确授权“合并，验证”。main c8a6e83（PR9）已整合，保留地址-only共享prepare与原Dockerfile；启动门禁已移除品牌/法律端点检查。整合后的完整130/130通过（85.830秒），Trellis复核通过。下面旧arm64三补丁/品牌镜像结果仅为历史验证；本次最终镜像以新PR云端native amd64/arm64结果为准，不能复用旧镜像声明整合启动成功。云端结果将记录在cloud-validation.json。

日期：2026-10-03。分支 `feat/beta-review-release`，本地基线 `da6cc08`。用户已批准实施和未来条件合并；本次 bootstrap PR 仍须明确审阅合并。本地验证结束时尚未提交；未push、创建 PR、调用真实 merge/dispatch、发布镜像、发送真实 Bark 或操作运行服务。

## 改动与门禁

- CI 检出实际 PR head，原生 amd64/arm64 分别执行完整源码检查、共享 prepare/ExUnit、镜像内 adapter suite、主应用默认入口/迁移/HTTP/许可/编译后地址契约，然后才保存产物。两架构与 verify 全通过才发布同一已检查产物，publisher 不重建。
- main 发布正式版本及 latest；同仓 PR/受控分支 publish dispatch 发布 beta/beta-pr-N，不触碰 latest。官方稳定 tag→commit 检查保留，latest 跟随 main 已审阅 pin。
- 可信 main 控制器认证 run/jobs/verify/registry OCI，当前 PR head/main 祖先与公开 protected/enabled/everyone/verify app15368 摘要均有效才普通 expected-head merge；现有 strict 保护由 GitHub 合并端原子执行；单次回读确认后 expected-main-SHA/source-PR dispatch。来源/保护读取失败拒绝合并，不新增 PAT。
- 失败通知与成功合并门禁独立：无产物 beta 失败、已合并 PR 的 main 失败仍通知；轻量、check-only、fork与正常陈旧成功候选不通知。Bark endpoint 仅发送步骤可见，固定脱敏 payload、先 dry-run、有界重试、响应 code200验证；terminal uncertain 不盲目重发。
- 修复最终审查发现的轻量跳过被误报为 beta 失败，以及保护摘要检查须显式要求 protected/enabled/everyone 与 verify app15368。README中英、AMAP与spec已同步。

## 品牌收窄前的本机运行证据（历史）

通过共享 `scripts/prepare_upstream.py` 准备的当前固定源码：TeslaMate v4.3.0 / `33d200b2fba9d5138803916a788cef5eae31b1aa`；最新再核对 prepared HEAD、当前三份补丁 reverse-check、法律/MODIFICATIONS一致。未使用过期 `/tmp/teslamate-amap-prepared-check`，未改其他worktree的prepare/branding责任文件。

本地 orbstack 原生 linux/arm64，主镜像 `georelay-main-smoke:checked-01a0fe28`，ID `sha256:5a73784a17f8349662ea2e7c8634c0f29c8abd05f8dc08aa7d1b0141bff1f123`；默认 ENTRYPOINT `tini -- /bin/dash /entrypoint.sh`，CMD `bin/teslamate start`未覆盖。Probe/adapter 镜像 `georelay-adapter-main-smoke:checked-01a0fe28`，ID `sha256:554bb4d9265a0e19e24e1f826bdbd7e7a1dbf539eaacdccb7d492b88fbc8a9b8`。

最终主应用脚本实际输出：

```text
Main image smoke passed: /sign_in HTTP 200, login HTML verified; migrations=105; core tables present; /notice and /license verified; compiled address checks passed
```

| 实际场景 | 退出码 | 秒 | 清理独立回读 |
| --- | --- | --- | --- |
| 默认入口、新 PostgreSQL、最终RPC契约 | 0 | 3.700 | 容器/网络0 |
| 默认入口损坏 /bin/false | 1 | 0.968 | 容器/网络0 |
| PORT4001、3秒就绪上限 | 1 | 5.556 | 容器/网络0 |
| 仅向Bash PID发TERM | 143 | 1.002 | 容器/网络/临时文件0；信号至清理0.430秒 |

等待边界包含probe及清理时间，所以总耗时可略高于就绪上限。所有场景使用独立internal网络和新tmpfs PostgreSQL，无host port/生产卷/真实地图Key/车辆账号。坏入口仅输出状态/退出码，超时仅输出固定原因；不输出原始应用日志。记录见 [runtime-results.json](runtime-results.json)，历史启动子任务证据见 [validation.md](../10-03-main-image-smoke/validation.md)。

最终编译地址RPC实际验证 Locations → Finch → fixture → 新PG，包含负身份创建与文字刷新、身份/坐标/历史正身份/行程充电关联保留，缺身份与502明确失败、无Unknown写入、无reverse fallback；RPC只输出固定标记，不输出bindings。已构建adapter中的真实suite另执行34/34，16.062秒；只挂tests、network none、断言server.__file__为/app/adapter/server.py，容器已移除。此为镜像运行证据，未用源码mock/ExUnit成功冒充。

## 离线与静态检查

- 最终完整 `python3 -m unittest discover -s tests -v`：131/131，86.132秒，总86.203秒，退出0；见 [test-results.json](test-results.json)。覆盖controller14组、Bark6组、publisher/updater/retention/source/runtime回归。
- Bark真实loopback POST/JSON code200回读、dry-run零网络、拒绝/重试/脱敏/畸形report测试通过；未发送真实设备通知。
- `bash -n scripts/publish_images.sh scripts/test_main_image.sh`、scripts/tests全部Python语法、actionlint v1.7.12两工作流（`-shellcheck=`）、git diff --check通过。
- Trellis full-scope checker审查所有受影响层与任务契约；发布相关53项、controller/Bark20项独立复核通过，无剩余阻塞代码问题。仓库无静态typechecker，未执行shellcheck，不将语法检查说成typecheck。
- 只读GitHub实例 run37064970725与其verify check-run111032105672的head_sha一致（实际PR head），check来自Actions app15368且details URL指向本run/job，支持PR provenance设计。已有本地gh身份回读main GraphQL严格保护有效；这不证明Actions token权限。

## 本地交付时的待验证边界（历史）

| 项目 | 状态 |
| --- | --- |
| 本机arm64最终主应用、迁移、地址/许可、故障/取消 | 已实际通过 |
| 本机arm64已打包adapter suite | 已实际通过 |
| 云端原生amd64 / arm64 / verify / beta双索引 | 尚无本次PR结果，待提交并经用户授权push/PR |
| Actions GITHUB_TOKEN读取保护、受保护merge与main dispatch | 待控制器首次审阅合入后云端验收；读取失败拒绝merge |
| 真实Bark送达 | BARK_URL尚未配置；hosted可达性与真实delivery待验收 |
| 正式GHCR/latest发布、运行容器部署 | 未执行；发布范围仅GHCR，运行容器不在任务范围 |

任务保持in_progress；本地实现及必要检查完成，用户已回复“行”确认Trellis3.4具体计划，本次执行一个本地新提交。bootstrap实现不自动合并自身，不启用当前PR auto-merge。push/PR后应报告分支、PR、云端验证并等待用户审阅。

## Final-head CI and packaged test timing (2026-10-03)

Run 37070822103 tested 66b9001. arm64 adapter 34/34 and actual default main startup passed: HTTP 200, 105 migrations, core tables and compiled address contract. amd64 packaged adapter slow-drip test failed before main startup: its 300 ms subprocess budget expired before the first HTTP request. verify failed and publish was skipped. This run provides no amd64 main startup result.

An isolated Linux arm64 container with a controlled 400 ms child startup delay reproduced the old assertion while 504, wall-clock bound and child termination passed. The test-only fix uses a 5 s simulated drip, 2 s total subprocess deadline and 3 s wall-clock bound. Under the same delay, the child reached real HTTP, returned 504 and was killed (SIGKILL) in 2.138 s. The packaged adapter suite passed 34/34 in 13.522 s with no external network and no container left behind. Production adapter deadlines are unchanged. The new pushed head still requires cloud validation on both architectures.

## Bootstrap cloud acceptance and merge (2026-10-03)

Exact head 4dce3a8 passed run 37071951401: native amd64 and arm64 each passed packaged adapter 34/34, default main release startup, HTTP 200 login HTML, 105 migrations, core tables and compiled address checks. verify and publish passed. Both beta indexes and their manifest/config digests and OCI labels were read back; beta-pr-10 matched the fixed version and latest remained unchanged. The read-only controller returned candidate_ready.

Under the user’s explicit merge-and-verify authorization, PR10 was normally merged with expected head into 5727c65; no bypass or auto-merge was used for bootstrap. Main push run 37072746968 is validating formal GHCR publication. Temporary branch qa/georelay-bark-failure-37071951401 points only to the previously known failing fixture commit; run 37072800085 exercises trusted early-failure notification without image publication. The remaining late-head race regression will be a candidate for actual default-token controller merge/dispatch acceptance. These latter live checks are not yet reported as completed.

## Formal bootstrap and live failure delivery (2026-10-03)

Main run 37072746968 at merge 5727c65 passed both native main startup checks (HTTP 200, 105 migrations, core tables, compiled address) and adapter 34/34, verify and publish. Both stable indexes and OCI/manifest/config digests were verified, and both latest indexes exactly matched v4.3.0-georelay-5727c65a9eda47869bfea1b79679e6899ce829a5.

The early-failure test run 37072800085 had zero artifacts and skipped publication. Trusted controller 37073005011 correctly classified beta_validation and sent Bark after dry-run: one attempt, HTTP 200 and response code 200 verified by the sender. Its temporary branch was deleted and absence verified. API acceptance does not independently prove handset receipt.

PR11 run 37073109247 at 9fa79ae revealed another old success-test timing assumption: fifty cold baidu lookups exceeded a 1 s fixture budget; production default is 20 s. amd64 main startup was skipped, arm64 startup passed, verify failed and publication was blocked. Trusted controller 37073595194 accurately associated PR11/run/commit, sent Bark in one HTTP 200 attempt and did not merge or dispatch main.

Controlled 30 ms lookup-connection delay reproduced the original 1 s failure on isolated Linux arm64 in both providers (2.021 s total). The positive fixture now allows 5 s and retains fifty complete results, provider counts, ordering, coordinates and identities, wall-clock bound and 1 < peak <= 4. Under the same delay it passed (3.125 s total); a single-worker mutation returned all results within 5 s but was rejected by peak=1 in both providers (4.689 s total). Provider delays and production deadlines were unchanged, and independent failure-deadline/queue-cancel cases remain. Linux packaged suite passed 34/34 in 13.603 s; reviewer focused tests passed 5/5. New exact-head cloud verification remains required.

## Hosted token protection capability and native enforcement (2026-10-03)

PR11 exact head c12b7e6 passed beta run 37074314019 on native amd64 and arm64: packaged adapter 34/34, default main HTTP 200, 105 migrations, core tables and compiled address contract; verify/publication and registry/OCI/alias checks passed, latest stayed at the verified main 5727 indexes. Trusted controller 37074994812 failed closed at branch_protection, did not merge/dispatch and sent a verified failure Bark.

A separate check-only probe run 37076000025 used the same Actions token permissions and only GET/GraphQL queries. `branches/main` returned protected=true, protection.enabled=true, enforcement_level=everyone and verify app15368. The REST required-status detail returned HTTP 403; full and four separate GraphQL rule-field queries all returned FORBIDDEN at repository.ref.branchProtectionRule. Active rules were empty because the repository uses legacy branch protection. The probe intentionally failed after its safe summaries, and controller 37076023220 skipped notification (notify=false, Bark step skipped); no images/artifacts were produced. Its remote/local branch and temporary worktree were removed after verifying the expected SHA.

Owner-authenticated readback still confirmed the existing main rule: strict=true, enforce_admins=true and verify app15368. Settings were unchanged. The minimal controller fix reads the accessible summary and rejects absent/disabled/admin-exempt/wrong-app checks, then uses ordinary expected-head merge. GitHub atomically enforces the existing strict rule at the merge endpoint; the controller does not claim to independently read the unexposed strict flag and never requests an administrator credential or bypass. Fixture first reproduced the old Forbidden failure and then passed 15/15 after the native fix. New exact-head beta checks, installation to trusted main and actual default-token merge/dispatch remain required.

## Native protection correction installed (2026-10-03)

Exact head172f855 passed beta37077079430: native amd64 and arm64 actual default main startup, login HTTP200, 105 migrations, core tables and compiled address checks; packaged adapter34/34 (14.088s amd64, 15.172s arm64), verify and publication succeeded. Both fixed beta indexes/child manifests/config digests/OCI source/revision/version and beta-pr-11 were verified; latest stayed at main5727.

The default-token controller on old main still used the forbidden GraphQL rule query. Under the user's existing merge-and-verify authorization, PR11 was ordinarily merged with exact expected head to02c426233bd972506f5149810afa96fab6388fb3; no bypass or auto-merge switch was used. Main push run37077752055 is pending formal checks/publication. This installer merge does not prove default-token automatic merge/dispatch: a subsequent related late-base regression candidate will provide that cloud acceptance.

Late-base regression uses the existing controller fixture: main moves after the protection summary while PR head remains tested. Without the simulated server strict rejection the test observed an unwanted dispatch and failed; with ordinary merge rejection it passed (one exact-head PUT, PR open/unmerged, no dispatch, merge failure notification). Independent controller+Bark22/22, AST/JSON/diff passed. Only fixture/test changed; no production controller, workflow or protection settings changed. Real default-token automatic acceptance remains pending.

Main installer run37077752055 at02c4262 completed successfully: both native main runtime/adapter suites and verify/publication passed. Both stable indexes/child/config digests/OCI labels were verified; each latest exactly matched v4.3.0-georelay-02c426233bd972506f5149810afa96fab6388fb3. This was the installer’s user merge/push run; automatic merge/dispatch remains a separate pending acceptance.

## PR12 automatic acceptance (historical, 2026-10-03)

PR12 exact head64074c219810b581bd8334b142ba0d1a25346d3c passed beta37078535617 on native amd64 and arm64: default release startup, login HTTP200, 105 migrations, core tables, compiled address contract and packaged adapter34/34. Both fixed beta indexes/child/config size+digests/OCI labels and beta-pr-12 were verified, with latest unchanged at main02c.

Installed main controller37079096065 returned merged_dispatched/main_publication_requested/notify=false. GitHub independently confirmed PR12 merged by github-actions[bot] to0d1be28afe08d0fd43dc028c207d76c7a826d538, and explicit workflow_dispatch37079115614 bound source_pr12 plus expected/actual mergeSHA. No manual candidate merge/dispatch was used for this acceptance. Success Bark was skipped.

That automatic main run completed both native default-startup checks: HTTP200 login HTML, 105 migrations, core tables and compiled addresses. Packaged adapter34/34 passed in15.099s amd64 and14.931s arm64; verify and publish succeeded. Both formal version indexes and latest exactly matched v4.3.0-georelay-0d1be28afe08d0fd43dc028c207d76c7a826d538; complete child/config size+digest/OCI checks passed. Owner readback after automatic merge still confirmed strict=true/enforce_admins=true/verify app15368 and current main0d1be28. This owner readback is distinct from the controller’s readable summary, which has no strict field.

Historical PR12 checkpoint: runtime/publication/automatic-merge acceptance passed; the absent downstream workflow_run observer then prompted investigation of automatic-main failure notification. The following requirements had implementation/local coverage, while formal failure delivery was not yet accepted at that checkpoint: exact-source beta/stable channels, two native runtime suites before save/publication, reuse of checked artifacts, current-head ordinary protected auto merge and explicit dispatch, real failure Bark API acceptance plus mock main-failure/closed-PR coverage, publisher/updater/retention/spec/document consistency, and final cloud proof. The late-base rejection is a unit simulation of GitHub strict behavior; it is not reported as a live raced-main experiment. Bark API code200 acceptance is not independent handset receipt. No running container or production data was changed; all temporary probe/failure resources were removed.

## Automatic-main failure notification correction (2026-10-03)

The successful bot main dispatch37079115614 produced no observer at least6m39s after completion. Human main push37077752055 and human check-only dispatch37076000025 each produced an observer in2s. Default workflow remains active with unchanged trigger/name. This is consistent with documented GITHUB_TOKEN event suppression; there is no API suppression reason and no established excess of the documented workflow_run chain limit. Formal failure notification could not be accepted from mock observer tests.

The correction uses one always CI finalizer: native boolean decision always succeeds for beta/no-op, and only main image publication failure loads checked main code and readonly report, then existing Bark dry-run/verified send. Dry-run uses a fixed placeholder without a Secret; only real sender sees BARK_URL. Optional PR GET matches actual main merge SHA/repository/ref/merged facts, else basic PR0 run notification persists; valid expected SHA still diagnoses stale dispatch. Stable observer relinquishes main notification before PR API reads, preventing duplicate or late API-error notification. Publisher hard timeout and checkout failure are covered by the independent job; forced whole-run termination still depends on platform scheduling. Targeted controller23/Bark6/context5/CI7, AST/actionlint/diff passed. The independent full suite and real bot-failure acceptance were subsequently completed below.

Independent final review of the correction passed the full suite139/139 in88.019s and actionlint v1.7.12(-shellcheck=), AST, JSON/diff checks; no code/design blocker. No static typechecker is configured. The report/notification path passed the subsequent real bot-failure cloud acceptance below.

## PR13 最终成功与真实失败验收（2026-10-03）

[Beta 37081881736](https://github.com/srcheng17/georelay/actions/runs/37081881736) 精确对应 PR13 head `9e6ab09a5a1d82a07ca621b437cbb8e02ae82098`。原生 amd64/arm64 保留主应用默认 ENTRYPOINT/CMD，以全新临时 PostgreSQL 实际完成 105 项迁移、核心表及 compiled 地址契约检查，`/sign_in` HTTP200 登录表单通过；adapter 均 34/34（14.865s / 14.894s）。verify、beta 发布和双索引/子 manifest/config digest/OCI 深验成功，beta-pr-13 精确匹配固定版本，beta 未改 latest。通知收尾 job 成功且 notify=false，checkout/report/dry-run/send 均 skipped。

[控制器 37082367599](https://github.com/srcheng17/georelay/actions/runs/37082367599) 返回 merged_dispatched/main_publication_requested/notify=false，用默认 GITHUB_TOKEN 自动将 PR13 合并至 `11e2e9d521347edbccbdb2a3691aba79eae43a00` 并显式派发 [正式 run 37082388229](https://github.com/srcheng17/georelay/actions/runs/37082388229)。expected/actual SHA 与 sourcePR13 绑定；两原生架构再次实际完成 HTTP200、105 迁移、核心表与地址检查，adapter 34/34（15.219s / 14.788s），verify/publish 全通过。成功通知 notify=false，Secret 步骤 skipped。两包 latest 精确对应 `v4.3.0-georelay-11e2e9d521347edbccbdb2a3691aba79eae43a00`：

- georelay：`sha256:4647bf8e2e6ce4a470df51b19165e6f7651c4b151733fda99dc254906e56d04a`。
- adapter：`sha256:50cb3128ba2fee378b53b6fe2dbec50653e7352f2775ffbec56c232876a14ced`。

最后用无 PR 的临时 check-only probe `37083052408` 及其 GITHUB_TOKEN 派发真实 main，传入已确认过期的 expected SHA。派生 [bot main run 37083060335](https://github.com/srcheng17/georelay/actions/runs/37083060335) actor/triggering_actor 均为 github-actions[bot]，actual `11e2e9d` / expected 旧 `0d1be28` / sourcePR13。在 Bind source 阶段非零退出，build/publish skipped、artifacts=0。独立 main-failure-notification job `111087605573` 成功，report 为 failed/main_publication/notify=true，actual/expected/sourcePR13 和失败 jobs checks/verify 正确；dry-run 0 次网络发送，真实 Bark sent/1 次/HTTP200，sender 验证 JSON code200。没有依赖不存在的 main observer；API 接受不代表独立确认手机收件。

失败后独立重新深验两包 latest/固定版本的双架构、子 manifest/config size+digest 与 OCI 标签，仍精确等于上述 baseline；main ref 也未变。probe 自身 controller `37083065040` skipped/untrusted_or_unrelated_run/notify=false，Bark skipped。临时远端与本地分支在核对 SHA 后删除，worktree 和临时文件移除，所有路径/refs 不存在已独立回读。保护 strict=true、enforce_admins=true、verify app15368 仍有效，设置未改。

全部需求与父子任务 AC 完成；质量门禁为独立 139/139（88.019s）、actionlint v1.7.12 `-shellcheck=`、AST/JSON/diff 通过。无配置静态 typechecker，未执行 shellcheck；整个 run 被强制终止时通知仍依赖 GitHub 调度收尾 job。发布范围仅 GHCR 正式镜像/latest，运行容器和生产数据未更新。
