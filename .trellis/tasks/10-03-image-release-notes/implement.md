# 实施计划

## 进入实施前

- 最新总规划摘要经用户后续消息明确批准后才 task.py start；不把创建/继续当作合并批准。
- 任务 contexts 校验通过，使用当前隔离分支，保留 README 删除。
- 当前任务如创建 PR，保持 draft 等待审阅；首次 main writer enablement 合并需当前任务明确授权。

## 执行顺序

1. **合同与小型探针**：固定 version/receipt/body marker/基线/状态 schema，设计 native-token exact tag/Release 验证用例。先 fake API 测试；真实探针仅在可信 writer 合入并获发布验证授权后执行，不能为了先测而提升候选权限。
2. **发布结果**：扩展 publisher 原子 receipt，覆盖固定成功早退、alias部分失败、timeout/缺输出；原 tested artifacts/双索引门禁不变。保存独立有界JSON数据artifact供原run/attempt补录，明确retention/缺失边界，禁止执行候选产物。真实 shell fake registry 回归。
3. **只读证明与内容**：复用 registry/Actions 验证，实现同 attempt 前置完成校验、原attempt专用API（不读latest rerun）、可信 pin、祖先基线、Markdown 条目/PR/compare 的有界读取，保持 updater pin-only。
4. **幂等 writer**：实现 exact ref/tag readback、owned block、只404 absent、冲突停止、响应不确定读回、保留人工内容、固定首次baseline并排除自身，以及显式 latest 判定。fake API 断言写入顺序、错误零写、正文安全与运行代码/补丁变更必须有可读条目。
5. **直接 CI 及补录入口**：独立 main checkout release-record job，不执行候选内容；共享 publication lock。增加 trusted release-only dispatch，重核已完成原 run/attempt/indexes，零 build/push。实现 bootstrap_not_enabled，不能把缺 main script当作 ready。
6. **完整完成门禁**：controller/updater/直接main收尾/通知有限白名单同步；正在构建/补录不重复调度，仅release-record失败的原run可通过绑定原run/attempt的可信成功补录与Release回读重评ready；扩展beta-control受限入口与updater轮询后显式dispatch（不单靠workflow_run），其他检查/publish/alias失败不豁免；复读current PR/head/base/draft/保护/expected-head原合同。当前任务合并门禁不扩张。
7. **文档/spec 与交叉审查**：首次启用、版本说明维护、补录、浮动失败、精确源码及权限限制同步；父任务破坏性迁移/回滚作为独立可读条目。独立 reviewer 检查跨工作流和信任边界。
8. **有条件线上验收**：本地/CI mock 和原镜像 checks 后报告分支/PR/结果等待审阅；仅在用户明确要求合并当前 enablement 后启用可信 main writer，且在发布验证获授权时验证 native token、正式/beta双包/双架构、每份 Release/readback/匿名拉取。任何未取得证据保持待验证，不提前归档为完整验收。

Release 自动化可以先独立交付；父任务架构改动可在独立分支并行实现，但正式发布前应已启用 writer。任务树本身不授权 merge、真实发通知或部署。

## 必要检查

- python3 -m unittest discover -s tests -v；git diff --check。
- bash -n scripts/publish_images.sh；所改 workflow 的语法和权限/门控回归，包含 checks:read 和可信 main checkout。
- 聚焦矩阵：双包/双架构/OCI/digest/source、same attempt provenance、in_progress直接记录、alias早退与部分失败、baseline祖先/beta/首版/排除自身/首次冻结、receipt数据artifact来源与过期/大小边界、pin-only、幂等/错误tag/人工body/响应丢失、有界文本/分页、release-only零重建、updater补录恢复、controller缺记录拒绝/仅记录失败修复重评/无observer仍重评/其他失败不豁免、main/beta/no-op失败收尾、bootstrap和token权限分类。
- 测试通知只用 fake/loopback；不发送真实 Bark、不触碰生产数据库/容器。
- 真实 GitHub 写入、云端 native amd64/arm64、匿名拉取另留准确运行证据；mock不得冒充这些结论。

## 风险与回滚点

主要风险：workflow 修改目标的默认token权限、首次main尚无writer、旧run/attempt误认、固定成功与alias失败混淆、陈旧流程抢latest、记录失败被updater误视为完成。权限或证据不足停止记录；只补录不得改源码tag或固定镜像。暂停workflow可阻止新记录，不移动已有tag或删除Release。未经当前任务明确要求不得合并main或启用auto-merge。

## 当前验证状态

2026-10-03 用户已确认实施，task status=in_progress。实现完成后经过源码、fake/loopback与隔离镜像检查，具体执行结果和最终修正见 research/verification.md。规划复核记录属于实施前历史，不代表当前仍在 planning。任务继续保留 in_progress，以便审阅后完成首次可信 main 启用、native-token和云端发布验证；不提前归档为完整线上验收。
