# 验证与发布

使用 Python 标准库实现和 unittest，优先直接函数与 SQLite 约束。非平凡逻辑留下能复现实际失败的测试；mock 使用虚构公共地标坐标，禁止生产数据。覆盖 reverse/lookup 身份闭环、重启、TTL、语言、并发、境外、错误与超时；真实本地 HTTP 测试验证 JSON/status/log 隐私。

真实 Key 联调须有用户授权，只读提取所需单个变量，经 stdin 写入独立测试容器的0600 tmpfs文件，不把值放入argv、环境或日志。使用公共地标、独立网络和临时数据卷，无host port；只对测试库过期缓存、只断开测试网络，结束删除资源。保存脱敏断言结果，不提交响应或数据库。高德、百度当前不传语言参数，语言切换只断言身份/坐标与刷新闭环，不能要求英文翻译；health成功不能替代真实provider检查。

用户明确要求真实库核对时，可在 `BEGIN READ ONLY` +有界statement/lock timeout中抽样已结束事件的原始位置及关联地址；原记录仅留内存和隔离临时卷，不输出坐标/地址字符串、不作为fixture、不提交Git。先比较事件坐标与旧address坐标；不同点和不同provider的文字差异不能直接判错，同点地点名退化成道路需单列。省市区/道路、地点名和身份闭环分别验证；查后复读生产对照字段并清理临时资源，不写回或迁移旧身份。

固定 `upstream.json` 中稳定 tag 和解引用 commit，下载到临时/忽略目录；先校验 commit 再 `git apply --check`，任何失败停止。保留上游 LICENSE/NOTICE。GitHub release 检测自动创建仅 pin 变更的上游分支与 PR，并显式触发双架构构建；影响镜像的 main push 或受控上游分支 dispatch 通过全部校验后自动发布版本镜像。仅文档、agent/Paseo/Trellis 设置改动运行轻量检查，手动 dispatch 始终完整构建。上游分支必须与 main 相比仅改 upstream.json，并匹配稳定 tag；不自动合并 PR。两架构都检查成功才从已测试产物发布索引，保留单名 verify 汇总检查，不得绕过测试。不自动部署、不自动提升 stable、不 force push。

共享prepare路径在应用补丁前逐字核对LICENSE/NOTICE/TRADEMARK.md与仓库复核原文；缺失或变化停止，人工复核后更新随附文件。修改通知含相关日期并进入两个镜像，发布检查验证可读。GeoRelay是独立公开名称，镜像为georelay和georelay-adapter，保留旧包但不向其发布新版本；上游命名/图标变化需重新审查品牌补丁，不能静默跳过。修改版保留内部模块、数据库和MQTT兼容标识，不借重构改动数据契约。

用户已授权维护两镜像的 `latest`。所有发布任务共用 publish job concurrency group；先验证两个版本索引，再复制已测试索引至 latest，不重新构建。推广前回读官方最新稳定版和源码状态，旧 pin 或过期源码跳过推广，网络/校验失败停止；GitHub 队列不保证 FIFO，不能仅凭串行认为版本不会倒退。每个 latest 必须回读为对应版本的同一双架构内容。两个 package 没有原子更新，任一推广或回读失败使 workflow 失败，不能报告双镜像完成。保留固定版本/digest用法；latest本身不会拉取或重建运行容器。

改动最少的必要文件，不引入框架/ORM/插件层。构建流程本身要有失败测试。新增测试路径必须与 workflow 和 README 命令一致。

统一补丁的空白上下文行必须保留单个空格前缀；`.gitattributes`只对此类文件关闭blank-at-eol检查，实际应用后的上游源码仍由prepare脚本执行git diff --check。

公开文档以固定上游 README 为基础，保留来源、官方功能和许可；首页显著保留 TRADEMARK.md 要求的非官方声明，不将上游徽章或发布指标当作本仓库结果。截图链接固定官方 commit，配置与构建细节集中在 `docs/AMAP.md`。修改后检查相对链接、锚点、截图可访问性及配置一致性；公开前覆盖可达 Git 历史、PR、CI 日志和产物的敏感信息审查。文档必须区分已验证、已发布和已部署状态。

README 按使用者需要组织用途、功能和使用入口，验收数字、PR 进度与内部任务记录留在维护材料中。项目介绍不将当前构建版本写成长期定位，具体 tag/commit 链接 `upstream.json`；上游 release 检测、版本更新、CI 构建和镜像发布分别写明触发条件。

`README.md` 默认英文，`README.zh-CN.md` 提供中文；两版顶部互相链接，功能、配置、来源与发布条件同步更新。中文指南返回中文首页，英文首页链接中文指南时标明语言。排版可参考真实开源项目的导航和截图布局，不复制其品牌或徽章；首页只点名 TeslaMate 本身及本项目服务，不介绍第三方客户端。

开始使用提供并入现有 stack 的局部 Compose 配置和对应镜像取得方式，注明保留原有设置；官方镜像的 URL 补丁要求不能省略，未发布镜像不能写成可直接拉取。片段用假基础配置验证 Compose 合并后的原环境、网络和持久卷，不读取或启动生产 stack。

镜像使用入口以公开 GHCR 镜像与统一版本变量为主；首次发布需要核对 package public 和实际匿名拉取，不能以公有 repo 或 authenticated push 代替证明。每六小时轮询为 GitHub 尽力调度，不承诺实时触发。自动更新分支/PR/dispatch 应可重试恢复，禁止 force push 或覆盖异常来源。

## Scenario: CI gating and grouped image retention

### 1. Scope / Trigger

适用于 ci.yml 的改动范围判断、verify 汇总和 GHCR 保留工作流。普通任务分支 push 不发布；main 的镜像相关 push 和受控 publish dispatch 保留既有发布边界。

### 2. Signatures

- `python3 scripts/ci_changes.py`：从 GitHub 事件与实际 checkout 判断 `image_required=true|false`；缺少比较基线时要求构建。
- 输入环境为 `GITHUB_EVENT_NAME`、`GITHUB_EVENT_PATH`、`GITHUB_SHA`；事件 JSON 使用 `pull_request.base.sha` 或 push 的 `before`。有效基线和目标必须是非零 40 位小写 hex。结果追加到 `GITHUB_OUTPUT` 并打印。
- `python3 scripts/retain_images.py --repository OWNER/REPO [--output PATH] [--apply]`：默认只读预览；显式 apply 才删除。
- GitHub Packages 的 user/org container versions 分页 GET 和 version DELETE；GHCR manifest 按 digest 读取。publisher 与 retention 固定使用 `georelay`、`georelay-adapter`，由仓库 owner 决定命名空间；仓库 basename 改名不改变包名，OCI source/revision 仍跟随真实源码仓库。
- 清理 workflow 手动输入 `dry_run` 默认为 true；只在 main 执行，每周定时 apply。

### 3. Contracts

- Python/空白 checks 必须成功。verify 总是出现；image_required=true 只接受 build success，false 只接受 build skipped。缺失/非法输出或失败/取消都拒绝。
- 只有确认全为轻量路径的变更可跳过；运行代码、补丁、pin、测试、构建/发布和未知路径完整构建。`MODIFICATIONS.md` 与 `TRADEMARK.md` 是镜像或法律验证输入，必须完整构建。删除/重命名的旧新路径都计入。dispatch 始终构建。
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
