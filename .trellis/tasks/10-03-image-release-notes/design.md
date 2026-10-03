# 技术设计：镜像发布记录

## 1. 最小结构与版本

保留 scripts/image_context.py 的 stable/beta 固定版本，两个包使用同名版本，不引入 VERSION 文件或另一套 SemVer。Git tag 名等于镜像固定版本，Release 链接该 tag；tag 必须解引用为 exact source SHA，不能依赖 Release.target_commitish 的显示值。

扩展现有 publisher 输出结构化 publication receipt；新增 Python 标准库记录器及 CI 独立 release-record job。记录器执行 main checkout，persist-credentials:false、新 runner，无候选模块/缓存/可执行产物。候选 upstream.json、变更条目与 commit/PR 信息通过 exact SHA 的 API 读取为有界文本。最小 job 权限为 contents:write、actions:read、checks:read、packages:read，需要 PR 来源时加 pull-requests:read。publish/build 权限保持不变。

本设计采用独立 job + 可信 main checkout，与现有 controller 的信任模型一致，不新增 pull_request_target 路径。同仓 workflow 仍需审阅，不能声称只固定 Python checkout 即消除了候选 workflow 本身的权限风险。若后续改为 main-qualified reusable workflow，必须先让其存在于 main，再启用调用，不能让 bootstrap PR 引用不存在的远端文件。

## 2. Publication receipt 与实际校验

receipt 只包含 schema version、source SHA、upstream tag/commit、channel、固定 version、两个包的 index digest、fixed_verified、floating tag/status/reason，以及 run/attempt 绑定。不含 token、远端原始错误或运行配置。

双固定索引全部回读成功后立即留下 fixed_verified；无 alias/来源陈旧的早退仍产出 receipt。浮动状态采用 promoted/skipped/failed；进入推广前先留下保守失败状态，成功回读两包才更新 promoted，避免中途退出丢失固定发布事实。receipt 保存需原子替换；step/job 失败后仍传递有限文本结果，超时/缺结果不猜测成功。

除当前 needs 输出外，always 上传独立 publication-receipt 数据 artifact，名称绑定 run/attempt/source/version，请求保留 90 天（实际受仓库 retention 上限约束，文档写明有效补录窗口）。补录只按原 run/attempt 回读唯一匹配 artifact；限 archive 1 MiB、单个 JSON成员64 KiB，核验 artifact来源/重复/成员/大小后仅在内存读文本，不解压执行、导入模块或读取 build archives。数据仍不可信，必须独立重核发行证据。缺失/过期/损坏 receipt 明确失败，不猜测原 alias状态、不重新 build/push；readiness 不能因此成功。

记录器 always 进入判定，但只为合法完整固定组写入。按原 run 的 attempts/{attempt} 及其 jobs API 读取，禁止用 filter=latest 将后续 rerun 混入；重核 run/repository/workflow/event/source SHA/attempt、同 attempt 的 checks/build-amd64/build-arm64/verify、verify 的 Actions app 15368 和关联 job/check 来源、可信 pin 与 exact tag；重用或抽取现有 registry 只读校验，验证两包各恰含 amd64/arm64、manifest/config SHA256、OCI source/revision/version、索引与架构引用。receipt 是索引线索，不能成为授权证据。

run 此时可以 in_progress；禁止使用必须等整个 run completed 的 controller 入口造成循环等待。前置 checks/build/verify 必须成功；publish 可以 success，或在完整固定发布后仅 alias 阶段失败。缺失/不可信 receipt、不完整组或不明失败停止写入；alias failed 的完整事实可记录但不能让总流水线变绿。

## 3. 内容与基线

在新建 docs/changes/ 中保留普通 Markdown 变更条目，按本地任务/PR 一条，不建框架。标题与正文描述用户可感知的行为、兼容性/迁移及回滚限制。条目在有实际变更的 source diff 中被识别；删除/重命名/修改按真实变更处理，已有条目不能反复算新功能。运行代码/地址补丁的本地改动必须有对应可读条目；纯构建/验证/发布维护可用经验证的 PR/commit 摘要，不能空泛声称功能更新。条目校验归入现有 Python checks；只改条目继续属于 docs 的轻量构建判断，不新增为文案重建镜像的要求。

每份 Release 包含：更新说明；当前/上一可证明上游；两镜像固定 tag/digest/platform；exact source、可验证 PR、Actions run/attempt；fixed 与 floating 状态。pin-only diff 经校验后说明跟随官方 vOLD → vNEW、本项目未新增功能，并提供官方 Release/compare。自动分支仅改 upstream.json，说明由记录器计算。same-upstream 明示上游未变并列本地条目；混合更新分开写明。

首次生成正式记录时，基线从 recorder-owned stable Release 中选 source 为当前源码严格祖先且最近的有效发布，排除当前 version/source 的自身记录，不以 API 创建时间最新作为基线；beta 使用同候选流可证明前版或 main/merge-base，并标明基线语义。所有列表/compare 分页有界，truncation/重复/不一致拒绝。不存在可证明基线时明确“首个有发布记录的版本/无可证明上一发布”，列当前版本与可验证条目，不虚构上次发布。只可把父 commit pin 作为源码变化基线，不能声称它已发布。

创建时将选定 baseline、其语义和已生成说明绑定到 owned marker；幂等更新/补录只重核并复用此基线，不随之后新发布重算。已有 marker缺失/不可信停止，不能借补录重写更新历史。tag-only尚无Release时按严格祖先规则首次计算，并在写入后固定。

GitHub generated notes 可作有来源的 PR/commit 补充；无需复制官方长篇正文，不用模型猜测更新功能。Markdown/PR title/官方响应均通过结构化 JSON 传递，仅作文本，禁止嵌入 shell 或 run expression。

## 4. Latest、并发与幂等

默认显式 make_latest:false。beta 为 prerelease；无 alias、来源陈旧、alias 部分失败均不能 GitHub latest。只有当前 main/pin/source 仍符合推广条件，且两 GHCR latest 此刻都等于该固定索引时才可 make_latest:true。publisher、recorder、retention 使用既有 ghcr-publication 仓库锁；两 job 之间可能有其他 publisher 插入，因此 recorder 必须在锁内再次回读 current main 与两个 aliases，先前 promoted flag 不足以证明当前 latest。

Release body 使用 recorder-owned block 和结构化 provenance marker，绑定 source/upstream/channel/index digests/基线及报告版本。仅更新该块，保留人工补充；块被人工修改、归属错误或 immutable 限制时明确停止，不能覆盖。相同固定身份/digest 的重跑复用记录，可修复缺失记录或有限状态，不能换镜像内容。

exact tag GET 只有明确 404 才视为不存在。创建精确 ref 前后都回读；annotated tag 有界解引用。既有 tag 指错 source、Release marker 错误/foreign 或 digest 冲突拒绝，禁止 force 移动。POST/PATCH 超时或 422 collision 先回读确认结果；无证据不重复写。errors 使用固定分类，不打印 API body。

## 5. 完成判断与仅补录

release_control.JOBS、ready、main-failure needs/判断、notify_bark 的有限 stage/job 白名单同步加入 release-record；不改 branch protection，不扩大既有 merge/dispatch 授权。Beta最终 ready 需记录器成功且 provenance 匹配；bootstrap skip 不计完整。

updater 区分 queued/in_progress、固定镜像已验证、Release 已记录。已有完整固定组但记录失败时走可信 main 的 release-only workflow_dispatch，输入原 run ID/attempt/source/version，重新验证原完成门禁和 registry，再调用同一记录器。仅补录不能下载 build executable artifacts、调用 build/push 或改固定内容；无法证明原发行组时拒绝并保留失败，而不是复用同 tag 重建来补文案。正在运行的构建/补录继续抑制重复调度；成功补录进入完成判断，即使原 run 曾因记录失败而失败，也不因此无限重建。若 alias 失败，补录不能掩盖其失败或擅自重做推广。

记录补录后的 ready 使用一个严格限定的替代证明：原 Validate and build run 已 completed，原 checks/build-amd64/build-arm64/verify/publish 及其他非记录 jobs 全为 success，唯一失败项为 release-record（包括明确记录步骤失败的 failure/cancelled），可信 main 的 release-only run 已 completed/success，并绑定原 run ID/attempt/source/version/双索引；最后回读精确 Release 与 marker。仅该记录门禁可被修复结果替代，不更改原 run 的 failure 事实，build/verify/publish或alias失败与其他失败一律不豁免。修复来源不匹配、陈旧PR/current base变化仍按原控制规则拒绝。

beta-control 增加受限 release-only 完成观察/重评入口；workflow_run仅是快捷路径，不能作为唯一触发。可信 updater轮询其发起的repair run，确认completed/success后以main ref显式workflow_dispatch重评入口，绑定原run/attempt与repair run，处理GITHUB_TOKEN派生流程可能没有observer的情况；重复触发由原身份与实际PR状态幂等判定。重评入口严格验证repair workflow/main来源及原run证据；复用现有 ready/保护判断，不由 recorder 自行合并或新增 dispatch授权。updater使用同一“原门禁成功+可信记录证明”完成定义，避免各自以不同结果判定。当前任务PR保持draft，不因修复入口自动合并。

main 的直接失败收尾覆盖 Release 失败；beta/no-op 保持 success finalizer 合同；旧 main observer 仍提前退出防重复通知。通知只扩展既有授权流程中的固定类别，本阶段仅 fake/loopback 验证。

## 6. 首次启用、权限与回滚

首次 PR 中 main 还没有 recorder。CI 仅做离线/模拟及原镜像门禁，trusted job 检测未启用时报告 bootstrap_not_enabled，不退回候选代码、不宣布完整发布；缺失/失败记录阻断 controller ready。当前任务 PR 保持 draft 供用户审阅。用户明确要求合并 enablement 后，main 才拥有可信 writer，之后验证首次正式发布与 beta；不把首次 beta 未记录包装成已验收。

第一项发布实测检查 default GITHUB_TOKEN 对 exact source tag + existing-tag Release 的写能力，包含 workflow 修改的 beta 和陈旧 formal source。官方 Workflows:write 注记不能通过文档推断消除；先建精确 ref 再写 Release 只是待验证路径。无当前任务合并/发布授权时只执行 fake/local 检查，线上验收保留待验证；权限失败明确 tag/release_permission、阻断 ready，不换 PAT/App、不改 tag到main、不删beta要求。

关闭记录器/恢复工作流只影响后续记录，不能移动/删除已有 tag/Release。保留固定镜像与旧包；Release补录优先，既有镜像保留策略不变，不承诺所有历史镜像永久可拉取。失败文案与实际镜像发布状态分别显示，不把发行记录视为生产部署。

## 7. 文件边界

scripts/publish_images.sh、共享 registry/provenance 校验与新 record_release.py；ci.yml 与 release-only workflow；release_control.py、update_release.py、notify_bark.py 的必要完成判断；对应 tests；docs/changes/、维护文档及 backend 发布规范。image_context.py 仅在现有身份校验需要时调整，不改变版本算法。只做必要标准库扩展，不新增 ORM/外部服务/凭据。
