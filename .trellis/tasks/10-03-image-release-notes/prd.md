# 镜像版本信息与 GitHub Release 更新说明

## 目标与价值

用户追加要求：维护版本信息，使 Releases 能看到每次发布镜像的更新内容；跟随上游自动构建时说明上游版本变化。用户可以从一份 Release 判断更新内容、两镜像的精确版本和浮动标签结果，并追溯到实际测试源码。

## 实施前背景与证据

- F1：当前固定版本为 `<upstream-tag>-georelay-<full-source-sha>`，beta 为 `<upstream-tag>-georelay-beta-<full-source-sha>`；两镜像共享版本。见 scripts/image_context.py:48-90。
- F2：publisher 已核验双镜像、amd64/arm64、OCI 标签和索引；只有 Actions summary，没有 GitHub Release。固定版本成功后仍可能无 alias、因来源陈旧跳过 alias，或 alias 更新失败。见 scripts/publish_images.sh:96-193。
- F3：publish 执行候选源码且只有 contents:read；不能直接给候选发布脚本增加仓库写权限。bot dispatch 的 main 流程不能只依赖 workflow_run 观察器。见 .github/workflows/ci.yml:162-225。
- F4：controller、updater 和 main 失败收尾目前不检查 Release 记录；通知器不认识 release-record 阶段。见 scripts/release_control.py:19,87-97,183-208；scripts/update_release.py:140-163；scripts/notify_bark.py:17,54。
- F5：GitHub 官方文档对修改 workflow 的目标源码有额外写权限限制；默认令牌创建精确源码 tag/Release 的可行性尚未实测。当前源码与官方文档证据见 research/release-records.md。

## 需求

- R1：沿用现有固定版本和 OCI 身份，不引入独立人工递增版本。每次实际完成并核验的双镜像固定发布对应同名 Git tag/Release，tag 解引用到精确源码；beta 为 prerelease，正式版本为普通 Release。
- R2：Release 包含用户可读的本项目更新、上游 tag/commit、两镜像固定引用和 digest、平台、源码/可验证 PR/Actions 链接以及发布结果。使用轻量仓库 Markdown 条目维护本项目更新，无新版本服务或文案生成依赖。
- R3：自动跟进准确显示上游旧版本 → 新版本、官方 Release 与 compare 链接；同上游版本说明本项目改动，混合更新分别说明。自动 updater 分支仍只修改 upstream.json，不为了写说明改变其 pin-only 合同。
- R4：基线只能来自可证明的历史/祖先源码；beta 不污染正式基线。首次无历史记录明确注明，无法证明上一发布时不虚构版本变化。不得把已有修改重复写成新功能。
- R5：固定镜像与浮动标签分别记录。无 alias 或来源陈旧仍记录有效固定发布；alias 失败仍可记录已核验的固定镜像事实，但整条发布流程失败。只有实际当前正式 latest 的完整双镜像可标为 GitHub latest。
- R6：由隔离 runner 中的可信 main 记录器写 Release；候选内容只作为文本数据读取。独立重核 Actions 来源/attempt/门禁、immutable pin、双镜像索引与 OCI，不能仅相信候选 job outputs，不执行候选代码/缓存/可执行产物；build/publish 不增加 contents:write。
- R7：重复运行幂等，支持仅补录 Release 而不重建或覆盖固定镜像。tag 错源、版本/digest 冲突、他人 Release 或权限不明明确拒绝；不移动 tag，不覆盖人工补充。
- R8：Release 记录纳入 controller/updater 的完成判断及 main 失败收尾/通知白名单。缺失、失败、bootstrap 未启用均不能视作完整发布；queued/in_progress 仍抑制重复调度；原 run 仅记录失败时，可信补录成功可替代记录门禁，其他检查/发布失败不得豁免。现有通知仅扩展有限阶段，不新增通知渠道。
- R9：首次启用分阶段验证：离线/CI mock 检查 → 用户明确审阅合并可信记录器 → 授权的真实发布验证。beta workflow 变更的 native token 权限必须实测；失败不得偷偷更换凭据、改 tag 到 main 或漏掉 beta。实施批准不等于合并/线上发布批准。

## 验收标准

- AC1（R1、R2、R6）：合法双镜像发行组形成一份精确源码 Release；缺包、缺架构、错误 OCI/digest/source 或失败前置检查零 Release 写入；平台为 linux/amd64 与 linux/arm64。
- AC2（R2、R3、R4）：pin-only、same-upstream、混合更新、首版、beta 与陈旧 run 均给出准确可读说明；自动上游更新仍只改 pin，正式基线可证明且不会选中 beta。
- AC3（R5）：beta、无 PR alias、陈旧来源及 alias 部分失败均不抢 GitHub latest；alias 失败的已验证固定组有真实记录且整体失败；并发新发布插入后回读避免旧记录覆盖 latest。
- AC4（R6、R9）：记录器只执行可信 main 代码，当前 run 尚 in_progress 时也能验证已完成同 attempt 前置 jobs；错误 run/attempt/verify provenance 被拒绝；首次 main 无记录器不能改用候选代码。native token 的 workflow 修改 beta 能力有实际结果后才称该路径可用。
- AC5（R7）：重复运行零重复 Release；tag-only、漏记录和响应不确定可回读补齐；只补录不调用 Docker build/push，复用已固定基线而不把自身当上一版；缺/过期持久 receipt明确失败；错误 tag/marker/digest、人工内容与未知 API 错误不得被覆盖或当作不存在。
- AC6（R8）：成功镜像但缺/失败 Release 不 ready、不误作 updater 已完成；补录可独立重试，并经受限入口重新评估；不得因补录成功忽略原 build/verify/publish/alias失败。main 的 bot dispatch 直接收尾包含 release-record 失败，beta/no-op finalizer 保持原合同；通知测试只用 fake/loopback，无真实发送。
- AC7（R1—R9）：版本格式、权限边界、首次启用、补录和固定/浮动区别写入维护文档和 specs；已有 publisher/controller/updater 回归通过。mock、本地、真实双架构与线上写入证据分别记录，不互相代替。

## 范围边界与依赖

覆盖仓库发布脚本、工作流门禁、版本说明材料、测试和文档。暂不回填全部旧 GHCR 历史，不改变镜像保留策略、不删除旧包/Release，不部署容器、不操作生产数据库，不引入 PAT/App 凭据或扩大自动合并权限。当前任务分支合并 main 仍需用户明确授权；如创建 PR，保持 draft 供审阅，避免既有控制器自动合并当前任务。

本子任务可独立实现和检查。可信记录器启用必须早于依赖它发布父任务的破坏性架构更新；父任务迁移/回滚说明必须作为对应版本的本地更新条目。首次 enablement 合并是另一个用户审阅节点，不能由任务树自动推断授权。

## 当前实施状态

用户已明确确认实施，任务已于 2026-10-03 启动为 in_progress。本地实现及验证持续记录在 research/verification.md；当前未合并 main、未创建线上 tag/Release、未发送真实通知、未发布镜像或操作生产。首次可信 main 启用、默认令牌权限与云端双架构/匿名拉取仍是外部验收门禁；实施授权不等于合并或生产迁移授权。
