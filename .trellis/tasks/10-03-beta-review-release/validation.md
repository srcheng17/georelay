# Beta 发布链路验证记录

当前云端进度见文末及 [cloud-validation.json](cloud-validation.json)；前面的本地/bootstrap记录按当时状态保留，不能作为当前未完成项列表。

最新状态：用户已明确授权“合并，验证”。main c8a6e83（PR9）已整合，保留地址-only共享prepare与原Dockerfile；启动门禁已移除品牌/法律端点检查。整合后的完整130/130通过（85.830秒），Trellis复核通过。下面旧arm64三补丁/品牌镜像结果仅为历史验证；本次最终镜像以新PR云端native amd64/arm64结果为准，不能复用旧镜像声明整合启动成功。云端结果将记录在cloud-validation.json。

日期：2026-10-03。分支 `feat/beta-review-release`，本地基线 `da6cc08`。用户已批准实施和未来条件合并；本次 bootstrap PR 仍须明确审阅合并。本地验证结束时尚未提交；未push、创建 PR、调用真实 merge/dispatch、发布镜像、发送真实 Bark 或操作运行服务。

## 改动与门禁

- CI 检出实际 PR head，原生 amd64/arm64 分别执行完整源码检查、共享 prepare/ExUnit、镜像内 adapter suite、主应用默认入口/迁移/HTTP/许可/编译后地址契约，然后才保存产物。两架构与 verify 全通过才发布同一已检查产物，publisher 不重建。
- main 发布正式版本及 latest；同仓 PR/受控分支 publish dispatch 发布 beta/beta-pr-N，不触碰 latest。官方稳定 tag→commit 检查保留，latest 跟随 main 已审阅 pin。
- 可信 main 控制器认证 run/jobs/verify/registry OCI，当前 PR head/main 祖先与公开 protected/enabled/everyone/verify app15368 摘要均有效才普通 expected-head merge；现有 strict 保护由 GitHub 合并端原子执行；单次回读确认后 expected-main-SHA/source-PR dispatch。来源/保护读取失败拒绝合并，不新增 PAT。
- 失败通知与成功合并门禁独立：无产物 beta 失败、已合并 PR 的 main 失败仍通知；轻量、check-only、fork与正常陈旧成功候选不通知。Bark endpoint 仅发送步骤可见，固定脱敏 payload、先 dry-run、有界重试、响应 code200验证；terminal uncertain 不盲目重发。
- 修复最终审查发现的轻量跳过被误报为 beta 失败，以及保护摘要检查须显式要求 protected/enabled/everyone 与 verify app15368。README中英、AMAP与spec已同步。

## 最终镜像实际运行证据

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

## 待验证与交付边界

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
