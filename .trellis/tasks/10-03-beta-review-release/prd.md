# Beta 镜像测试、条件自动合并与失败 Bark 通知

## 目标与授权

稳定镜像对应 main，分支先提供已测试的 beta；beta 成功且仍对应当前 PR commit 时自动合并，失败发 Bark。

用户已授权创建任务及定义未来的条件自动合并流程，最新确认“部署”仅指合并后发布 GHCR 正式镜像与 latest，不更新运行容器。用户已回复“开始”，授权实施本次收敛规划；本任务实现 PR 的首次合入仍需明确用户审阅/合并授权，不由尚未生效的自动化合并自身。独立主镜像启动交办的现有授权和成果保留。

## 已核验背景

- 当前尚无 beta 通道；发布入口允许 main push 和受控 upstream/<tag> dispatch 更新版本与 latest：scripts/publish_images.sh:26、.github/workflows/ci.yml:141。
- Python 测试和隔离 ExUnit 在构建前执行：.github/workflows/ci.yml:64、scripts/test_upstream.sh:45；tests/test_adapter.py:103 有 34 项 adapter 测试。
- 旧流程构建后只检查架构、非 root、许可文件和 adapter 健康（.github/workflows/ci.yml:75）。子任务 main-image-smoke 已增加 scripts/test_main_image.sh 与 CI:106 门禁；本机原生 arm64 实证默认入口启动、HTTP 200、105 项迁移和正常/故障/超时/TERM 清理，98 项全套及最终 9 项专项通过。证据见 ../10-03-main-image-smoke/validation.md，云端 amd64/arm64 尚待验证。
- 发布复用已检查的 amd64/arm64 产物，不在 publisher 重建：scripts/publish_images.sh:77。
- 2026-10-03 再次只读核验 srcheng17/georelay：main 默认分支，服务器 strict verify（GitHub Actions app 15368）、enforce_admins=true；允许普通 merge，allow_auto_merge=false。Actions Secrets 列表仍为空，BARK_URL 尚需在 GitHub 配置；不提取或记录真实值。

## 需求

- R1：main 的镜像相关改动经完整检查后发布正式版本与 latest；文档/元数据改动保留轻量检查。可信同仓 PR/受控分支只发布 beta，不改写 latest；latest 跟随 main 已选定 pin，未合入的新官方版本不阻止当前 main 发布。
- R2：beta 标签包含上游版本与实际测试的完整 PR head commit，可关联 PR；两个 package 使用同一版本且都有 linux/amd64、linux/arm64。PR 临时 merge SHA 不得冒充已测试 head SHA。
- R3：保留构建前源码测试；复用 main-image-smoke 已实现的默认入口/迁移/HTTP 门禁，每架构再运行 adapter 镜像内的现有测试及 GeoRelay 地址创建/刷新、历史身份和失败处理检查。任一检查失败阻止候选发布成功。
- R4：运行测试用临时数据库、模拟地址服务和公共 fixture，不需要 Tesla 账号、地图 Key 或生产凭据；无 host port/生产卷，成功、失败、超时与取消均清理。
- R5：两架构测试、verify 与两 package 的 beta 发布/索引回读全部成功，可信同仓 PR 仍 open、非 draft、head SHA 等于 tested SHA 且 main 基线仍有效时，用 expected head SHA 普通 merge，遵守服务器分支保护。成功回读 merge 后显式 dispatch main 正式构建/测试/发布；携带 expected_main_sha 与 source_pr，因 GITHUB_TOKEN 合并的 push 不会自动触发 CI。
- R6：beta 构建/测试/发布、条件满足后的合并操作、正式 dispatch/发布实际失败时发 Bark；成功不发通知。失败门控独立于成功合并门控：无 beta artifact/index 的测试失败仍通知，已合并 PR 的 main 失败仍通知。fork 不通知；过期/关闭/draft/被新 head/base 替代的成功候选只跳过合并，不当作测试失败。BARK_URL 只在 GitHub Secret，通知含阶段、PR（若有）、commit 与 run 链接；不输出 Bark endpoint/设备 key/凭据、原始日志或车辆数据，先 dry-run/模拟接收，再有界重试与结果验证。
- R7：每次发布直接使用该 run 的已检查产物；保留 official tag/commit 一致性、main/PR 陈旧源码保护与正式十组保留策略。beta 不挤占正式额度；浮动 beta 别名只由当前 PR head 更新。main dispatch 开始核对 expected_main_sha，推广 latest 前回读当前 main，不能将过期来源冒充当前正式版。

## 验收标准

- AC1（R1/R2）：分支只生成 beta，main 生成正式版本/latest；fork、轻量、失败或不要求发布的 dispatch 不改写 latest，版本/OCI revision 对应 tested commit。
- AC2（R3/R4）：两个原生架构复用启动门禁并跑镜像内 adapter suite；实际登录表单页面可用，新库真实迁移；地址刷新保持 ID/坐标/历史关联，模拟失败不造 Unknown 或损坏数据，资源清理有实证。
- AC3（R3/R7）：缺架构、检查失败、错误 OCI 来源/版本或索引回读失败阻止候选成功；保存和发布同一已测试产物。
- AC4（R5/R6）：成功且 current head/base 的可信候选只合并一次，回读合并成功后 dispatch；fork、draft、过期/关闭 PR、旧 base、verify skipped/neutral 均零 merge。测试失败没有产物也通知；main 发布失败在 PR 已合并时仍关联 source_pr/expected_main_sha 通知；Bark gating、脱敏、dry-run/模拟接收有回归，真实 delivery 依赖 Secret。
- AC5（R1/R7）：publisher/updater/轻量/保留回归通过，beta 不挤占十组正式版；README 中英文、发布指南和 executable spec 一致。
- AC6：报告实际云端 amd64、arm64、verify、beta 发布及 main 正式发布结果，区分 mock、本机与云端。本任务 bootstrap PR 提交/push 后报告分支/PR/验证，等待用户审阅；首次合入后才能验收自动流程与真实 Bark。

## 范围外、风险与依赖

- 不更新任何运行容器、生产数据库或服务配置，不绕过分支保护/使用管理员 bypass，不合并本任务自身 PR，不引入真实车辆/地图数据。
- 不为 fork 发布/合并，不新增 beta 自动清理；beta 暂由现有保留逻辑保护，历史会增长。
- BARK_URL 尚未配置，配置与可达性是实际 Bark 验收依赖，规划与离线验证可继续。两个 package 无原子推广，任何一方失败不得报告双镜像完成。
- 父任务已由 planning 转 in_progress，实施批准与部署范围已明确。主镜像子任务现有代码/证据保持，不回滚或重写；品牌解耦由 enhanced-hedgehog 负责，继续使用共享 prepare 路径，不引入目录全等或任意 TeslaMate 词扫描。

2026-10-03最终整合：用户明确回复“合并，验证”，已授权本次bootstrap分支/PR合入并验证GHCR。整合main c8a6e83（PR9）地址-only修改，保留共享prepare、两个地址补丁与原生Dockerfile；删除品牌词/法律端点额外门禁，以真实登录表单、迁移和compiled地址RPC验收。旧品牌镜像测试记录仅为历史结果；最终以本次云端运行结果为准。
