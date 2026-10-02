# 验证与发布

使用 Python 标准库实现和 unittest，优先直接函数与 SQLite 约束。非平凡逻辑留下能复现实际失败的测试；mock 使用虚构公共地标坐标，禁止生产数据。覆盖 reverse/lookup 身份闭环、重启、TTL、语言、并发、境外、错误与超时；真实本地 HTTP 测试验证 JSON/status/log 隐私。

真实 Key 联调须有用户授权，只读提取所需单个变量，经 stdin 写入独立测试容器的0600 tmpfs文件，不把值放入argv、环境或日志。使用公共地标、独立网络和临时数据卷，无host port；只对测试库过期缓存、只断开测试网络，结束删除资源。保存脱敏断言结果，不提交响应或数据库。高德、百度当前不传语言参数，语言切换只断言身份/坐标与刷新闭环，不能要求英文翻译；health成功不能替代真实provider检查。

用户明确要求真实库核对时，可在 `BEGIN READ ONLY` +有界statement/lock timeout中抽样已结束事件的原始位置及关联地址；原记录仅留内存和隔离临时卷，不输出坐标/地址字符串、不作为fixture、不提交Git。先比较事件坐标与旧address坐标；不同点和不同provider的文字差异不能直接判错，同点地点名退化成道路需单列。省市区/道路、地点名和身份闭环分别验证；查后复读生产对照字段并清理临时资源，不写回或迁移旧身份。

固定 `upstream.json` 中稳定 tag 和解引用 commit，下载到临时/忽略目录；先校验 commit 再 `git apply --check`，任何失败停止。保留上游 LICENSE/NOTICE。GitHub release 检测自动创建仅 pin 变更的上游分支与 PR，并显式触发双架构构建；影响镜像的 main push 通过全部校验后发布正式版本；同仓 PR 和受控分支 publish dispatch 先发布 beta。仅文档、agent/Paseo/Trellis 设置改动运行轻量检查，手动 dispatch 始终完整构建。上游分支必须与 main 相比仅改 upstream.json，并匹配稳定 tag；可信 main 控制器仅按下述 beta 契约条件合并。首次启用本流程的任务 PR 仍须用户明确审阅合并。两架构都检查成功才从已测试产物发布索引，保留单名 verify 汇总检查，不得绕过测试。发布范围仅 GHCR 正式镜像与 latest，不更新运行容器，不 force push。

共享 prepare 路径仅校验固定 tag/commit 并严格应用两个地址补丁；上游应用保留 TeslaMate 名称、UI、翻译、图标、法律文件与原 Dockerfile。不比对上游法律原文快照、不审核视觉资源、不做名称扫描、不复制品牌资产或追加 Dockerfile 指令。GeoRelay 是仓库/镜像/地址服务项目名，镜像为 georelay 和 georelay-adapter，旧包保留但不再发布新版本。独立 adapter 保留自身许可与修改通知包装。地址模块、数据库和 MQTT 数据契约不借此改动。

用户已授权维护两镜像的 `latest`。所有发布任务共用 publish job concurrency group；先验证两个版本索引，再复制已测试索引至 latest，不重新构建。推广前校验当前 pin 对应官方稳定 release/tag/commit 并回读源码状态，过期 main 跳过推广，网络/校验失败停止；latest 跟随 main 已审阅 pin，尚未合入的官方新版本不阻断推广。GitHub 队列不保证 FIFO，不能仅凭串行认为版本不会倒退。每个 latest 必须回读为对应版本的同一双架构内容。两个 package 没有原子更新，任一推广或回读失败使 workflow 失败，不能报告双镜像完成。保留固定版本/digest用法；latest本身不会拉取或重建运行容器。

改动最少的必要文件，不引入框架/ORM/插件层。构建流程本身要有失败测试。新增测试路径必须与 workflow 和 README 命令一致。

统一补丁的空白上下文行必须保留单个空格前缀；`.gitattributes`只对此类文件关闭blank-at-eol检查，实际应用后的上游源码仍由prepare脚本执行git diff --check。

公开文档以固定上游 README 为基础，保留来源、官方功能和许可；保留本项目独立维护的来源说明，不将上游徽章或发布指标当作本仓库结果。截图链接固定官方 commit，配置与构建细节集中在 `docs/AMAP.md`。修改后检查相对链接、锚点、截图可访问性及配置一致性；公开前覆盖可达 Git 历史、PR、CI 日志和产物的敏感信息审查。文档必须区分已验证、已发布和已部署状态。

README 按使用者需要组织用途、功能和使用入口，验收数字、PR 进度与内部任务记录留在维护材料中。项目介绍不将当前构建版本写成长期定位，具体 tag/commit 链接 `upstream.json`；上游 release 检测、版本更新、CI 构建和镜像发布分别写明触发条件。

`README.md` 默认英文，`README.zh-CN.md` 提供中文；两版顶部互相链接，功能、配置、来源与发布条件同步更新。中文指南返回中文首页，英文首页链接中文指南时标明语言。排版可参考真实开源项目的导航和截图布局，不复制其品牌或徽章；首页只点名 TeslaMate 本身及本项目服务，不介绍第三方客户端。

开始使用提供并入现有 stack 的局部 Compose 配置和对应镜像取得方式，注明保留原有设置；官方镜像的 URL 补丁要求不能省略，未发布镜像不能写成可直接拉取。片段用假基础配置验证 Compose 合并后的原环境、网络和持久卷，不读取或启动生产 stack。

镜像使用入口以公开 GHCR 镜像与统一版本变量为主；首次发布需要核对 package public 和实际匿名拉取，不能以公有 repo 或 authenticated push 代替证明。每六小时轮询为 GitHub 尽力调度，不承诺实时触发。自动更新分支/PR/dispatch 应可重试恢复，禁止 force push 或覆盖异常来源。

## Scenario: CI gating and grouped image retention

### 1. Scope / Trigger

适用于 ci.yml 的改动范围判断、verify 汇总和 GHCR 保留工作流。普通任务分支 push 不发布；main 的镜像相关 push/main publish dispatch 发布正式镜像，同仓 PR/受控分支 publish dispatch 发布 beta。fork/check-only 和轻量改动不发布。

### 2. Signatures

- `python3 scripts/ci_changes.py`：从 GitHub 事件与实际 checkout 判断 `image_required=true|false`；缺少比较基线时要求构建。
- 输入环境为 `GITHUB_EVENT_NAME`、`GITHUB_EVENT_PATH`、`TESTED_SHA`（缺省 GITHUB_SHA）；事件 JSON 使用 `pull_request.base.sha` 或 push 的 `before`。有效基线和目标必须是非零 40 位小写 hex。结果追加到 `GITHUB_OUTPUT` 并打印。
- `python3 scripts/retain_images.py --repository OWNER/REPO [--output PATH] [--apply]`：默认只读预览；显式 apply 才删除。
- GitHub Packages 的 user/org container versions 分页 GET 和 version DELETE；GHCR manifest 按 digest 读取。publisher 与 retention 固定使用 `georelay`、`georelay-adapter`，由仓库 owner 决定命名空间；仓库 basename 改名不改变包名，OCI source/revision 仍跟随真实源码仓库。
- 清理 workflow 手动输入 `dry_run` 默认为 true；只在 main 执行，每周定时 apply。

### 3. Contracts

- Python/空白 checks 必须成功。verify 总是出现；image_required=true 只接受 build success，false 只接受 build skipped。缺失/非法输出或失败/取消都拒绝。
- 只有确认全为轻量路径的变更可跳过；运行代码、补丁、pin、测试、构建/发布和未知路径完整构建。不新增上游法律或品牌门禁；未知路径仍按完整构建处理。删除/重命名的旧新路径都计入。dispatch 始终构建。
- 保留 publisher 当前使用的两个 package（`georelay`、`georelay-adapter`）都完整的最新十组 `vMAJOR.MINOR.PATCH-georelay-<40hex>`、latest 与其全部引用。旧 teslamate-amap 包不再发布新版本，本策略保留原状。完整组的两个索引必须各含且仅含 linux/amd64、linux/arm64，digest 匹配相应架构标签和版本记录。
- 以完整发布组的创建时间排序；latest 单独保护，不能用其更新时间替代版本排序。其他保留标签、共享子镜像、不完整/未知组及未关联无标签记录同样不得误删。
- 两个 package 的全部读取与计划验证完成后才允许 DELETE；先删旧索引再删不再被保留引用的子镜像。读取/解析失败在写入前停止，DELETE 失败停止后续删除。
- 清理 JSON 报告含 `mode`、`repository`、`keep_releases=10`、`complete_releases`、`incomplete_releases`、`retained_releases`、`candidate_releases`，以及每个 package 的 `versions/protected/latest/delete`；delete 条目是 `id/digest/kind`。REST 清单每页 100 条，最多 200 页，重复 id/digest/tag 或无时区创建时间均拒绝。
- 清理与发布共用 job concurrency `ghcr-publication-${{ github.repository }}`，防止清理上传中的版本。GITHUB_TOKEN 须有 package write/admin 权限；不增加用户凭据，不输出 token/远端响应错误体。
- 工作流提供 `GH_TOKEN` 给 gh API，`GITHUB_TOKEN` 给 registry token 请求；缺省仓库来自 `GITHUB_REPOSITORY`。gh API 输出沿用 command 的 1,048,576 字符限制，registry HTTP 响应限制 1 MiB；按 digest 读取的 manifest 必须通过 SHA256 内容校验。
- 本任务只读验证，不执行线上 apply。合并必须获得针对当前 PR/分支的明确用户授权。

### 4. Validation & Error Matrix

| 条件 | 行为 |
| --- | --- |
| 仅轻量文件且 checks 成功 | build skipped、verify success、无 publish |
| 运行/未知路径、零 before SHA、无法读取基线或 dispatch | 完整构建 |
| 检查失败、构建失败/取消、缺失判断 | verify failure、无 publish |
| 超过十组且旧组未被保留引用 | 预览候选；显式 apply 才删除 |
| latest 指向更旧的完整组、架构 digest 被共享 | 仍保留对应版本 |
| 不完整/未知发布或未关联无标签记录 | 保留供人工复核 |
| 清单权限不足、分页/元数据错误、缺失引用 | 失败、零 DELETE |
| 删除 API 失败 | 停止后续删除，不声称回滚已删除记录 |

### 5. Good / Base / Bad Cases

- Base：README 改动仍有 verify，通过后不发布镜像。
- Good：两 package 各十二组完整版本，latest 指向第二组；保留最新十组及第二组和其引用。
- Bad：按 REST version 记录数保留十条，误删仍在多架构索引中使用的 amd64 子镜像。

### 6. Tests Required

真实 Git 仓库验证轻量/混合路径、删除/重命名、缺失基线和 dispatch；执行实际 verify shell 检查失败/跳过/取消。Fake API/manifest 验证分页、十组排序、old latest、共享引用、不完整记录、preview 零写入、apply 顺序和读失败零删除。现有 publisher/updater 回归必须通过；实际 PR checks 核对两架构和 verify，不能以本地 mock 代替 CI 构建结论。

### 7. Wrong vs Correct

错误：workflow 级 paths-ignore 跳过必需检查；正确：workflow 总触发，只跳过 Docker job，verify 判定有意跳过。

错误：保留 latest 索引却按时间删除它引用的子镜像；正确：先计算所有保留索引的依赖，再删除整组历史。


## Scenario: Main image startup gate

### 1. Scope / Trigger

每个原生 amd64/arm64 CI job 构建完成后、`docker save` 前验证主应用 release；同一已检查镜像用于发布。

### 2. Signatures

`bash scripts/test_main_image.sh <app-image> <adapter-probe-image>`；`MAIN_IMAGE_TIMEOUT_SECONDS` 缺省 120，只接受 1..600 整数。CI 使用 `exec bash scripts/test_main_image.sh ...`，step timeout 为 5 分钟。

### 3. Contracts

- 主镜像保留默认 ENTRYPOINT/CMD；连接新建 PostgreSQL 18 tmpfs，入口真实等待数据库并迁移，不预装 schema。
- 独立 internal 网络与命名容器、虚构测试凭据，无 host port/生产卷；probe 复用已构建 adapter 的 Python 标准库。
- `/sign_in` 必须 HTTP 200、无跳转、`text/html`，含实际 access/refresh token 登录表单，不耦合上游显示名称；`schema_migrations` 非空且 cars/addresses/positions/drives/charging_processes/settings 表存在。上游 UI、法律端点及 Dockerfile 不新增定制检查；adapter 保留自身许可验证。
- 同网络 fixture 无外部 provider/Key，挂载的 RPC 检查调用最终 release 编译后的 Locations → Finch → fixture → 新 PG。验证负身份创建/刷新、坐标及行程充电关联保留、历史正身份不变；缺身份/502 明确失败，不写 Unknown、不做 reverse fallback。只输出固定成功标记。adapter suite 在已构建镜像内运行并断言模块来自 /app，只挂 tests、关闭外网。
- Docker 操作有界且等待可中断；EXIT 清理容器、自动生成的卷和网络，回读确认没有容器残留，三项清理操作各限 2 秒；INT/TERM 先停止当前子进程。只有清理成功才输出通过，诊断只给固定原因与状态/退出码，不输出原始日志或配置。

### 4. Validation & Error Matrix

| 条件 | 结果 |
| --- | --- |
| 真实 HTTP 与迁移回读通过、清理成功 | 退出 0，允许保存镜像 |
| DB/app 退出、探测或迁移失败、超时 | 非零退出，清理并阻断保存/发布 |
| 清理失败 | 非零退出，不声称无残留 |
| 入口 PID 收到 INT/TERM | 及时中断等待、清理，退出 130/143 |

### 5. Good / Base / Bad Cases

Base：无账号/地图 Key 的新库启动并返回登录页面。Good：损坏入口或错误端口被拒绝且无测试资源残留。Bad：仅 container running 或源码 ExUnit 通过就保存发布。

### 6. Tests Required

`tests/test_main_image.py` 覆盖默认入口/隔离参数、真实 probe 断言、退出/SQL/HTTP/超时/清理失败与阻塞 Docker 时取消；验证 workflow 两架构门禁早于 artifact 保存。实际构建镜像运行及故障检查单独记录，云端结果未取得时明确待验证。

### 7. Wrong vs Correct

错误：外层 Bash 启动前台子脚本，或在前台 Docker 包装进程结束后才处理信号。正确：CI `exec bash`、可中断等待并回收子进程后清理。源码测试不能替代最终镜像启动证据。


## Scenario: Beta candidate merge and formal GHCR release

### 1. Scope / Trigger

同仓 PR 镜像改动或显式分支 publish dispatch 产生 beta；可信 main 的 workflow_run 控制器只对完成的 Validate and build 做判定。首次启用 PR 不自动合并自身，任务分支合入仍须用户明确授权。运行容器不在部署范围内。

### 2. Signatures

- `python3 scripts/image_context.py [--json]`：绑定实际 checkout、PR head、channel/version/source_pr/expected_main_sha；PR 不使用临时 merge SHA。
- `bash scripts/publish_images.sh <checked-artifacts-directory>`：消费相同已测试 amd64/arm64 artifacts，不重建。
- `python3 scripts/release_control.py --output PATH [--apply]`：缺省只读；workflow 从 main 显式 apply。
- `python3 scripts/notify_bark.py --report PATH [--dry-run]`：仅可信失败 report；BARK_URL 只进发送步骤，不打印 endpoint/Key/响应原文。
- CI run-name：`images/event/PR-or-0/tested-SHA/publish-or-check/expected-main-SHA-or--`。

### 3. Contracts

- 正式标签 `<upstream-tag>-georelay-<40hex>`，beta `<upstream-tag>-georelay-beta-<40hex>`；两 package 同标签，架构后缀 -amd64/-arm64，当前 PR alias 为 beta-pr-N。beta 不改 latest、不挤占正式保留十组；未知/beta 记录继续保护，清理延期。
- publisher 严格校验官方稳定 release 的 tag→commit，OCI source/revision/version 与实际 source一致。浮动标签推广前回读 current PR/main，复制同版本索引并验 digest；任一 package失败则流程失败，不能声称原子双推广。
- 成功候选必须同仓 open/non-draft、当前 head等于tested SHA、当前 main为head祖先；checks/build-amd64/build-arm64/verify/publish全成功，verify来自 Actions app15368和本run。两 beta索引各恰含linux/amd64、linux/arm64，manifest/config digest与OCI来源一致。
- 固定只读GraphQL main ref.branchProtectionRule必须requiresStatusChecks=true、requiresStrictStatusChecks=true、isAdminEnforced=true且required verify由Actions app15368提供；读取失败拒绝merge，Actions token实际读取能力须云端验收，不新增管理员凭据。控制器不执行候选代码、不加载候选artifacts、不绕过保护。merge前再次回读head/base，用普通REST merge携带expected head SHA；正常过期成功候选静默跳过。
- merge响应丢失先回读，不重复merge；已合并回读后dispatch main，携带expected_main_sha/source_pr。main检出/测试SHA必须等于expected；GITHUB_TOKEN合并push不触发CI，显式dispatch负责正式发布。普通main成功run不递归dispatch。
- 失败通知独立于成功合并门禁：可信beta早期失败无artifacts也通知；main失败可关联已closed/merged PR，expected与actual不一致的失败仍通知。fork/check-only/metadata-only/正常过期成功候选不通知。metadata-only以本run checks中的精确step名 Python checks for metadata-only changes 已执行且非skipped来证明；CI用always()+image_required=false保证前序失败后仍执行。不得仅按build/publish skipped判轻量，因为镜像早期失败也可能跳过。仅固定阶段、SHA、PR/run链接和允许的job名进入payload。
- Bark先dry-run，HTTP仅loopback测试可用；真实URL须HTTPS，禁止redirect。有界timeout/retry/backoff，2xx且JSON code200才算送达；缺Secret明确not_configured，terminal uncertain不得盲目再发。稳定key不保证Bark服务端去重，跨workflow重跑可能重复。

### 4. Validation & Error Matrix

| 条件 | 行为 |
| --- | --- |
| 成功且当前PR、base、保护、索引均有效 | apply模式expected-head merge，回读后main dispatch |
| 成功但head/base已变、draft/closed或不可合并 | 无merge/dispatch，正常跳过 |
| 失败beta且无产物；已合并main失败 | 独立Bark门禁，不要求成功索引或open PR |
| 成功但job/verify/索引或保护无效 | 拒绝merge，报告固定失败阶段 |
| merge API响应不确定 | 单次回读，不能重复merge |
| 已merge但dispatch未确认 | 报告merged SHA，通知正式发布触发未确认 |
| Bark缺配置、拒绝、超时或响应未确认 | 非成功结果，不打印敏感值、不声称送达 |

### 5. Good / Base / Bad Cases

Base：同仓PR完整双架构验证后只生成beta。Good：当前候选经可信控制器合并，再重新验证merge commit并发布main正式镜像。Bad：只看run success、不读current head或严格保护即合并；把Bark dry-run/本机arm64说成云端链路完成。

### 6. Tests Required

标准库 fixtures覆盖source SHA/channel、fork/dispatch、stable/beta/latest隔离、同artifact发布、registry digest/OCI、成功/陈旧/保护拒绝、merge读回/dispatch不确定、beta无产物与closed main失败。Bark真实loopback验证POST、dry-run零网络、响应/重试/脱敏。主镜像实际启动和adapter packaged suite单独留证，云端两native job及真实Bark未取得时明确待验证。

### 7. Wrong vs Correct

错误：GITHUB_TOKEN merge后等push触发发布，或main更新latest仍要求未合入的官方最新pin。正确：显式expected-SHA main dispatch，latest跟随main已审阅pin，严格tag→commit检查保留。


## 上游地址准备契约

### Scope / Trigger

适用于 `scripts/prepare_upstream.py`、两个地址补丁及隔离上游测试。

### Contracts

- 入口为 `python3 scripts/prepare_upstream.py DESTINATION`；本地和 CI 共用，固定稳定 tag/commit、严格 `git apply --check` 后应用并执行 `git diff --check`。
- 生产补丁仅改 HTTP pool、Locations 和 Geocoder。UI、gettext、静态资源、法律文本和 Dockerfile 保持上游原样，不作为本项目额外审核门禁。
- 上游测试只验证地址相关 HTTP/Locations/Settings 契约与格式。正常构建仍验证上游工具链、Dockerfile 及其自身输入，不承诺任意上游版本都可构建。

### Validation

| 条件 | 行为 |
| --- | --- |
| 上游名称、UI、翻译、视觉资源、法律文本变化或文件缺失 | 不额外阻止准备，不重写，交给原生构建处理其自身依赖 |
| tag 不匹配 commit、地址补丁冲突 | 明确失败，不继续构建或发布 |
| 目标目录已有工作 | 拒绝覆盖 |
| 地址测试、原生构建、架构或非 root/health 失败 | verify 失败，不发布 |

真实 Git fixture 验证非地址文件原样保留和额外门禁移除，固定 pin/冲突/目录保护回归保持；固定上游实际准备后只应修改 3 个地址生产文件与相应测试。云端验证两架构及 verify 的实际结论。
