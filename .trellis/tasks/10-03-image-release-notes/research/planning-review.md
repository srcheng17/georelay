# Research: Release 规划静态复核

- Query: 子任务是否完整满足每次双镜像发布的可读 Release、上游 old → new、可信写入和可恢复完成门禁；父任务集成是否一致。
- Scope: internal / existing external research
- Date: 2026-10-03
- 状态: planning；本复核只读产品源码，仅写本研究文件。
- 最终结论: 本次规划发现已在文档闭环，无剩余阻断规划问题；实施/线上能力仍待后续真实证据。

## Findings

### 审查范围与已收敛部分

审阅子任务 `prd.md`、`design.md`、`implement.md` 和 `research/release-records.md`，并定点核对父任务及现有 CI/controller/updater/轻量路径代码。固定版本不另建人工版本号；同源 Git tag、双包双架构、正式/beta、上游 old → new、pin-only 分支、alias 失败事实与整体失败、main 直接失败收尾、通知有限白名单和当前任务手工合并边界均已有明确合同。GitHub native token/workflow-target 权限和首次 main 无 writer 被明确列为待实测门禁，没有把文档推断当作实测。

### P1: release-only 完成后缺少 controller 的可恢复合同与触发入口

- 证据: 子任务 `design.md:41-43` 要求成功补录进入完成判断，即使原 run 因 release-record 失败而失败；现有 `scripts/release_control.py:172-177` 对原 run failure 提前退出，`:189-199` 又要求每个原 job 都 success。`.github/workflows/beta-control.yml:3-6` 只观察 Validate and build；另一个 repair workflow 成功本身不会重新触发原 ci run 的完成事件。
- 影响: updater 可不再重复构建，但合法上游更新 beta 仍无法进入既有 ready；若粗暴接受 failed run，又可能豁免 build/verify/publish 或 alias 失败。
- 最小修正: 统一定义 effective publication readiness。仅当原 checks/build/verify/publish 及必要非记录 gate 已成功，可信 main 修复 run 与原 run ID/attempt/source/version/digests 一致，且 exact Release 回读一致，才以修复成功替代唯一失败/缺失的 release-record gate。保留其他失败、source freshness、draft/current PR、expected-head 与现有合并授权判断。补录完成后提供可信重评 ready 的入口；recorder 自身不新增 merge 能力或范围。增加“仅 release-record 失败可恢复，alias/verify 失败不可恢复”的回归。

### P1: 原 publication receipt 的持久读回合同未定

- 证据: `design.md:13-19` 将 receipt 用作 direct job 的索引和 outcome 线索；`:43` 的 repair 只输入 run/attempt/source/version。现有 `scripts/update_release.py:154-158` 能读取 jobs 清单，REST jobs 不提供原 job outputs。计划当前未说明仅补录如何取回原 receipt、保留多久，以及原 receipt 缺失后的行为。
- 影响: 原发行组的 alias 历史可能不可证；过期/缺失 receipt 后补录容易猜测 promoted/skipped/failed，或回退同 tag 重建。
- 最小修正: 明确 receipt 的有限数据持久通道和保留期限（例如独立、小型 JSON artifact，只按原 run/attempt/精确名称读取且有大小/schema/来源界限，永不执行候选内容），以及 API 缺失/过期/篡改时停止或只记录独立证据可证明的当前事实的具体合同。receipt 仍不能替代 Actions/registry 校验；不得猜测历史 alias，也不得重新 build/push。加入原 outputs 不可访问、artifact 缺失与错误 attempt 的 repair 回归。

### P2: same-version 幂等需要冻结已发布基线

- 证据: `design.md:27` 选当前源码最近 ancestor stable Release；`:35` marker 绑定 baseline，但未明确排除自身，也未明确补录/重跑是否重新选择基线。
- 影响: 创建后的当前 Release 本身可成为最近 ancestor；较旧祖先版本晚到也可能改变基线。于是重跑可能将已有功能重新描述、把 old → new 变为无变化，或因 marker baseline 不同而错误拒绝。
- 最小修正: 新记录选择严格前驱并排除当前 tag/source；首次成功写入后固定经过证明的 baseline（含 unavailable 语义），重跑验证并复用 marker 中的 baseline，不重新择优。若最邻近祖先存在不可排序并列，明确有界拒绝或无可证明上一版。加入自身 Release、晚到祖先及相同 version 反复 repair 的文案稳定性回归。

### P2: recorder 最小权限遗漏 checks:read

- 证据: `design.md:7` 权限列 contents:write/actions:read/packages:read/按需PR read，但 `:17` 要读 verify check-run。现有 `scripts/release_control.py:201-208` 通过 Checks endpoint 核验 Actions app 15368；`.github/workflows/beta-control.yml:31` 已明确 checks:read。
- 最小修正: direct recorder 与 release-only writer 的权限表同步列 checks:read，并以 workflow 权限测试验证；不要把公共可读或 endpoint 恰好成功当作省略权限合同的依据。无额外凭据或 Workflows:write 扩张。

### 非阻断实现提醒: 可读本地条目不能只校验格式

- 证据: PRD R2/R3 和 `design.md:23-29` 要求 local updates 可读，但没有说明非 pin image-affecting diff 缺少变更条目时的行为。
- 最小建议: 在实现时明确本地产品变更缺说明会停止，或只能按可证明 source diff 标明维护/验证无产品行为变化；不能仅列 SHA/PR 链接却声称已满足可读更新。现有 `scripts/ci_changes.py:15` 把 docs/ 作为轻量路径，因此仅补条目不应强行重建镜像。

### 父任务集成复核

首次复核时父 `prd.md` 为 R1—R8/AC1—AC8，Release 集成由主会话并行添加；不得把该中间状态误报为最终规划遗漏。最终应复读 R9/R10、AC9/AC10、任务地图、执行依赖与父任务迁移/回滚变更条目合同。子任务 writer 实际启用须早于父任务破坏性架构发布，任务树不推导 merge 授权。

## Files found

| 文件 | 本次使用 |
| --- | --- |
| `.trellis/tasks/10-03-image-release-notes/{prd.md,design.md,implement.md}` | 需求、信任边界、恢复与首次启用合同 |
| `.trellis/tasks/10-03-image-release-notes/research/release-records.md` | 已完成当前代码与官方只读研究；信任现有结论，不重复全仓探索 |
| `.trellis/tasks/10-03-application-owned-geocoding/{prd.md,design.md,implement.md}` | 父范围、迁移 Release 依赖及当前 planning 状态 |
| `.github/workflows/ci.yml:162-225` | publish 候选权限与 main 直接失败 finalizer |
| `.github/workflows/beta-control.yml:3-40` | ci-only completion observer、可信 main checkout 与 checks 权限 |
| `scripts/release_control.py:19,75-112,115-219` | required jobs、main report、原失败 run 和 all-job gate、verify 来源 |
| `scripts/update_release.py:140-169` | 历史 run 和 publish-only 完成判断 |
| `scripts/publish_images.sh:118-193` | 完整固定组、合法 early exits 与 alias 部分失败 |
| `scripts/ci_changes.py:15` | docs 轻量构建分类 |

## Related specs

- `.trellis/workflow.md` Phase 1：最新总结后仍需实施 review gate，规划不授权 start/合并。
- `.trellis/spec/backend/index.md` 与 `contracts.md`：标准库、最小变更、禁止生产操作与泄密。
- `.trellis/spec/backend/quality-guidelines.md`：测试产物发布、双架构/索引/source 身份、共享 publication lock、可信 controller、direct main finalizer 和通知界限。
- `.trellis/spec/guides/cross-layer-thinking-guide.md`：失败边界和构建/实际验证区别。

## External references

沿用 `research/release-records.md` 已读官方 REST Releases、Refs、Actions workflow_run/GITHUB_TOKEN 文档；本次没有新增线上查询或写探针。Workflows:write 限制和“先 exact ref 再 existing-tag Release”仍须真实 native-token 验证，不能假定绕过成功。

## Caveats / Not Found

- 以上为静态规划审查，未实现产品代码、运行任务 start、做 Git 操作、GitHub 写入、发布、真实通知、合并或部署。
- 4 项修正是合同完整性，不要求新框架、版本服务、PAT/App 凭据或扩大自动合并权限。
- 子任务及父任务仍由主会话并行维护；发现是否已修正以最终文件复读为准。

## 修正复读（同日）

- 已关闭 receipt 持久读回缺口：子 design §2 明确独立 JSON artifact 的精确 run/attempt/source/version 名称、请求90天/实际保留窗口、archive 1 MiB/单JSON 64 KiB、内存读取与缺失失败。数据不代替发行证明，不重建。
- 已关闭 same-version 基线缺口：子 design §3 使用严格祖先、排除自身，首次 marker 固定 baseline/说明，后续复用；tag-only尚无Release时首次计算。祖先并列仍应在实现时有界处理而不猜测。
- 已关闭 checks 权限缺口：子 design §1 增加 checks:read。
- controller 恢复合同已明确：子 design §5 仅原非记录 jobs 全成功、唯一 release-record 失败时，可信 repair 同源证明和实际 Release 可替代该记录 gate；其他失败及 current PR/base/head/保护不豁免。updater 采用相同定义，当前 PR draft。
- 父集成已复读：父 prd R9/R10、AC9/AC10、任务地图及 design §8 / implement 的 Release检查一致；发布架构前先启用可信 writer，本地可并行，含迁移/配套升级/回滚说明，未扩大 merge/线上/生产权限。

### 已关闭补充: bot-dispatched repair 不仅依赖 workflow_run

原研究已记录 GITHUB_TOKEN-dispatched main CI 可没有 workflow_run observer，因此子 design §5 的 repair完成重评也不能只寄望 beta-control observer。最小补充是可信 updater 轮询确认 repair完成后，显式触发同一受限 beta-control 重评入口（复用既有 actions:write与main控制代码），或等价直接可信收尾；仍执行既有current candidate/授权合同，不由recorder自行merge。增加“repair成功、无workflow_run事件仍能完成重评”的回归即可，不需要新通知渠道/凭据。最终复读 `design.md:51` 与 `implement.md:16,26` 已明确 updater 轮询后以 main ref 显式 dispatch 重评及无 observer 回归，该点关闭。

### 最终复读结论

子 `design.md:19` 已要求 attempts/{attempt} 专用 API，禁止 latest jobs 混入后续 rerun；`:25` 已要求运行代码/地址补丁可读条目，纯维护仅用经过验证的摘要；`implement.md:16` 明确重评保留 current PR/head/base/draft/保护/expected-head。本次发现和提醒均已写入可执行规划，无未关闭规划阻断。父子任务仍 planning，本复核不批准实施、合并或真实发布。

后续关键验收门禁仍为 native GITHUB_TOKEN 对精确 workflow变更源 tag/Release 的真实写能力，以及用户审阅后 trusted main bootstrap；这是显式待验证风险，不能用静态复核通过代替 AC/线上证据。
