# 设计：Beta 候选、条件自动合并与失败 Bark

部署范围已确认：只发布 GHCR 正式镜像与 latest。父任务已获批准进入 in_progress，主镜像子任务已完成本地实现/验证；本设计复用现有成果。

## 行为与修改边界

发布/测试链路决定 stable 与 beta；不改 adapter 业务代码、官方依赖或 prepare/功能/品牌补丁。shared prepare 继续由对应责任 agent 维护。

预期修改 ci.yml、publish_images.sh、update_release.py 和已有测试；复用 test_main_image.sh/test_main_image.py，在隔离检查上补 adapter 镜像 suite与小型 stub/RPC 地址断言。新增一个可信 main 控制工作流与最小 Python 控制/通知脚本；不引入发布框架。README 两种语言、docs/AMAP.md 与质量规范同步。

## 来源、标签与源码

| 来源 | 版本/浮动标签 | 成功行为 | 失败行为 |
| --- | --- | --- | --- |
| main 镜像相关 push / main publish dispatch | vX.Y.Z-georelay-40hex / latest | 正式发布 | Bark |
| 可信同仓 PR / 受控分支 publish dispatch | vX.Y.Z-georelay-beta-40hex / beta-pr-N（当前 PR 才更新） | 有符合门控的 PR 时自动合并 | Bark，可无 PR |
| upstream/tag 候选 dispatch | 同上 beta | 同上 | 同上 |
| fork / 轻量 / 不要求发布的 dispatch | 检查，无镜像标签 | 无发布/合并 | 不发 Bark |

- 复用 PR 与 dispatch 触发，不增加所有分支 push 的重复构建。无关联 PR 的分支可受控生成固定 beta，但不自动合并或更新 PR 别名。
- beta checkout、OCI revision/version、测试与记录统一用真实 PR head/分支 commit，区分事件的临时 merge SHA；保留 required verify。
- publisher 只 load 当前 run 已测试的两架构 artifacts，验证两个 package 版本索引/digest 后推广浮动标签。main/PR 陈旧来源跳过浮动标签与自动合并。
- strict tag/commit 验证保留；latest 跟随已审阅 main pin，不要求它等于尚未合入的最新官方 release。beta 未纳入正式保留正则，保留额度不变，清理延期（research/beta-retention.md）。

## 构建后测试

1. 保留 Python/地址 ExUnit、架构、非 root 与 adapter自身许可检查。
2. 复用已实现的 test_main_image.sh 默认入口 + PostgreSQL 18 tmpfs + 登录 HTTP/迁移检查及可中断等待/残留回读，不重写启动或清理层。本机 arm64 已实测，证据见 ../10-03-main-image-smoke/validation.md；云端两架构待验证。
3. adapter 最终镜像执行现有 test_adapter.py，只挂 tests，保留镜像自带 /app/adapter，不挂宿主源码；无 Key/外网/新依赖。
4. 在现有隔离网络加公共 fixture stub 与只读 Elixir RPC 断言；验证 compiled Locations → Finch HTTP → 新 PostgreSQL 的负数身份、刷新文本/坐标/历史引用，以及服务/缺失身份失败不破坏原数据。HTTP就绪验证上游实际登录表单，不检查品牌或定制法律端点；不把 ExUnit 放进 release。
5. 两原生架构共用入口；所有检查早于 docker save。失败阻断 artifact/候选发布，成功后发布相同产物；main 合入后的正式 run 独立重新构建并验证其 merge commit。

## 可信控制器与自动合并

- 独立 workflow_run 控制器来自可信 main，不 checkout/执行 PR 代码或候选脚本；只读取 API/registry 元数据。fork 的候选不接触写 token/Bark Secret。
- 成功路径逐项校验预期 workflow/run/event、同仓 PR/base main、open/non-draft、tested head、有效 main 基线、两个原生 job、明确 success 的 verify 与双 package beta 索引。不能用 skipped/neutral 或其他 run/app 的 verify 当成功。
- 共享 merge concurrency 下最后重读条件；普通 REST merge 带 expected head sha，并依赖 strict protection 防 base 竞态。unknown mergeability 有界重读，冲突/blocked 停止。无需打开 repository allow_auto_merge，不 rebase/update branch 后沿用旧 beta 结论（research/auto-merge.md）。
- 回读 merged=true/merge commit 后显式 workflow_dispatch main；输入 expected_main_sha 与 source_pr。正式 run 开始核对 commit，latest 推广前再读 current main。稳定 run 不重新触发 merge，避免递归。
- 成功但 head/base 已变化、PR closed/draft 的候选仅跳过；不冒充失败，也不合并。合并结果不确定先回读，dispatch 失败报告“已合并，正式发布触发未确认”，不再次 merge 或承诺回滚。

## 失败通知独立门控

- beta 构建/测试失败可以没有 artifacts/index；通知只要求可信来源及实际失败阶段，不能先要求成功发布。合并/dispatch 实际失败也通知。
- main 正式发布失败按可信 dispatch 的 source_pr/expected_main_sha 和实际 run 关联，回读 PR merge commit；此时不要求 PR open。普通 main push 没有 source_pr 时使用 run/commit 链接。
- 成功不发 Bark；过期候选正常跳过与 fork 不通知。失败 payload 包含阶段、可用 PR/beta 标签、commit、架构/失败结果和经过验证的 GitHub run 链接，字段缺失不得阻止早期失败通知。
- BARK_URL 只作为发送步骤 Secret，不进入 argv、日志或文档。优先复用 notification-hooks 标准库 sender 能力：dry-run、模拟接收、有界重试与响应验证；稳定事件标识便于追踪，但不承诺 Bark 服务端幂等或重跑绝不重复。
- Secret 缺失明确记未配置，传输结果不确定不盲目重发；通知 job 失败可见，不能把它或 dispatch 发出说成正式发布成功。

## 生效与回退

本任务 bootstrap PR 仍由用户审阅并明确授权首次合入，控制器不合并自身。真实流程/Bark 验收依赖 main 中工作流已生效与 BARK_URL；不修改运行容器。回退本任务源码/工作流，保留已发布固定镜像，不线上删除或回滚生产服务。

2026-10-03最终整合：用户明确回复“合并，验证”，已授权本次bootstrap分支/PR合入并验证GHCR。整合main c8a6e83（PR9）地址-only修改，保留共享prepare、两个地址补丁与原生Dockerfile；删除品牌词/法律端点额外门禁，以真实登录表单、迁移和compiled地址RPC验收。旧品牌镜像测试记录仅为历史结果；最终以本次云端运行结果为准。
