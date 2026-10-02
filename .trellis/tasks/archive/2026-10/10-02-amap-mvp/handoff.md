# TeslaMate 高德适配项目交接

## 用户指令与授权
用户要求继续 TeslaMate 高德适配项目，先落实项目约定和任务计划，再实施可验证的最小版本，并同步到现有私有 GitHub。当前最新指令是“那这个会话归档交给对应agent”，因此你是正确 TeslaMate 工作区中的接手 agent，请直接接续，中文反馈。原会话 agent ecbdef6e-99fb-41ef-938f-4c6a0217ae61 会归档，不再负责开发。
这是一项代码项目开发任务，不是生产迁移授权。不要修改现有 TeslaMate 服务、数据库、Dockhand stack，也不要自动替换生产镜像。无需用户先提供真实高德 Key。
用户不喜欢重复询问已批准范围。交接已明确要求“先落实项目约定和任务计划，然后实施可验证的最小版本”；先完成计划材料并按现有授权推进，仅就真正缺失的产品决定问具体问题。

## 正确工作区（已创建，禁止再创建重复工作区）
- cwd: /Users/ryancheng/.paseo/worktrees/0tgkxtk7/amap-adapter
- workspaceId: wks_ba179d5056a1d023
- projectId: prj_30098d883e8aa89b
- branch: feat/amap-adapter
- 主仓库: /Users/ryancheng/project/teslamate
- origin: https://github.com/srcheng17/teslamate.git （私有）
- main/HEAD 起点: 729fbc1f8841db24fa4035e9e976e02bbd79b898；上一个 43ce1ab。
- 原会话 cwd /Users/ryancheng/.paseo/worktrees/0tgkxtk7/silent-beaver 是无关仓库，不能在那里实现。

## 当前进度（2026-10-02 已现场核对）
1. 主仓库初始化、Trellis 初始化、GitHub 建仓早已完成，main 当时与远端一致且工作区干净。
2. 本轮用 Paseo create_workspace 从正确主仓库 main 建立上述隔离工作区，已核对 git common-dir 指向 /Users/ryancheng/project/teslamate/.git。
3. 已创建 .trellis/tasks/10-02-amap-mvp/，title“TeslaMate 高德适配最小版本”，status=planning，base_branch=main。
   仅有默认 PRD（TBD）、空 implement/check jsonl 和 task.json；尚未写 design.md/implement.md 或完成约定。
   创建时用 TRELLIS_CONTEXT_ID=teslamate-amap-root；新 agent 应使用自己的会话身份，按需要重新激活正确 task，不要误认为已开工。
4. .trellis/tasks/00-bootstrap-guidelines/ 仍 in_progress；spec/backend 与 spec/frontend 仍是模板。开发者 ryancheng。
5. 仓库只有 Trellis 生成文件、简短中文 README、.gitignore。没有 adapter、补丁、workflow，也没有 upstream 完整源码。
6. 本轮无产品代码、无新提交、无 push、无任何生产操作。唯一未跟踪目录是新建的任务目录（现附本交接记录）。
7. gh 登录 srcheng17，git 身份已配置。Python3=/usr/bin/python3，gh=/opt/homebrew/bin/gh，trellis=/opt/homebrew/bin/trellis。
8. 本机未发现 elixir/mix；Docker client/server 都是 29.4.0。若用 Docker 做隔离测试，不要连接生产容器/卷。
9. 原会话已读 AGENTS.md、.trellis/workflow.md、get_context 的 phase/packages、trellis-start/before-dev/spec-bootstrap/brainstorm/channel 与 using-git-worktrees/ponytail 技能。你应读项目所需约定与当前任务后继续；不必重复环境探索。

## 项目目标与背景
用户用 HedgieMate 看 TeslaMate 数据。官方 OSM 在中国地址不足，当前私人 mytesla/teslamate 镜像让用户担心长期升级与安全。用户希望维护官方版本的小补丁，尽量把高德做成独立服务，避免完整 fork。
已确认官方镜像目前没有可配置 geocoder Base URL 插件。因此必须诚实说明需要补丁；NOMINATIM_BASE_URL 是本项目新增能力，非官方现有变量。
地址 sidecar 不会切换 HedgieMate/Grafana 底图。底图/UI 能力研究与历史数据迁移是后续独立工作。

## 架构与确定的接口约定
官方 TeslaMate 源码 + 最小 URL 补丁 -> Docker 私有网络的 Nominatim 兼容高德 adapter -> AMap 官方 API。
adapter 独立 SQLite：永久身份映射 + 可过期响应缓存。原 PostgreSQL 继续由 TeslaMate 管理，HedgieMate/Grafana/API 读取原数据。

1. 新增 NOMINATIM_BASE_URL，默认 https://nominatim.openstreetmap.org。
   修改 Geocoder 的 Tesla.Middleware.BaseUrl，同时 TeslaMate.HTTP 专用 Finch pool key 使用同一经过 HTTP/HTTPS 校验的 URL，保留 size=3 和 proxy 配置。只改 geocoder 会落入 default pool，不能漏掉。
   NOMINATIM_PROXY 只是 CONNECT HTTP proxy，不能当自定义 geocoder 接口。
2. Sidecar 实现 /reverse 和 /lookup，另设健康检查。Key 仅在 sidecar，无需 Tesla token、ENCRYPTION_KEY、生产 DB 权限。
3. 将 WGS84 转 GCJ02 后请求 https://restapi.amap.com/v3/geocode/regeo；响应 lat/lon 保留原 WGS84。必须有境外 guard。
   规范化高德空数组/字符串；映射 name、road、city、county、state 等。
4. TeslaMate 官方按 (osm_id, osm_type) 去重。v4.3.0 signed bigint/changeset 接受负 osm_id。
   使用负数单调 ID + osm_type="node" 作为适配器私有身份（非标准 OSM 对象）。要留下兼容性测试。
   /lookup 接收 N-10001 形式，本地解析，返回原 type/id，绝不能返回未请求的身份。
5. 原始规范化 WGS84 坐标 -> 负 ID 映射必须永久存储、可备份。重启、语言变化、TTL 到期不能换 ID；禁止坐标 hash 代替映射。
   /lookup 用永久坐标刷新文字并保留身份；事务/唯一约束处理并发。
6. 真正 OSM 正数 N/W/R 可代理 OSM，但私人版可能产生正数 hash，不能把所有正数当可信 OSM。
   历史兼容导入/迁移要独立研究，在恢复副本验证后再申请生产执行授权。
7. 超时/重试有界；高德失败先用有效缓存，无可用结果就明确失败，供官方缺失地址修复稍后重试。
   禁止合成永久 Unknown 掩盖上游失败（官方把 "Unable to geocode" 特殊转为 Unknown，应避免误触）。
8. Sidecar 不公开 host port，不记录 Key 或精确位置，不提交运行配置/车辆数据/数据库备份。
9. 优先 stdlib/native 最小实现，复用现有能力，不新增 speculative abstractions。非平凡逻辑保留可运行检查。
10. 保留官方许可/来源。不要复制整份 upstream 或原始研究数据到 wrapper 仓库。

## “实时”的边界
官方 v4.3.0 行程结束同步解析起终点，充电开始解析地址；启动/每小时补修缺失地址；语言切换批量 /lookup。
普通 GPS 点仅记坐标/围栏，没有每点 reverse geocode；Summary/MQTT 主要坐标/围栏，HedgieMate 还取决于刷新。
历史行程/充电/Grafana/API 地址受益；实时底图地名由客户端地图提供者决定。

## 官方版本跟进与构建
跟进稳定 release，不跟 main 浮动 commit。
检测 release -> 固定 tag/commit -> 应用补丁 -> 有意义测试 -> 构建版本标签镜像。
补丁冲突或测试失败必须停止发布/提升 stable，不能静默跳过补丁。若上游原生支持再评估删补丁。
无需复制整个 upstream 到 wrapper 仓库；继续使用现有 Dockhand 做上线管理，不新增 GitOps 部署系统。
自动发布镜像不等于自动部署生产。开发变更保留可审查提交/PR，不 force push；核实实际检查结果后交付。

## 已核对的上游事实
2026-10-02 GitHub API releases/latest:
- tag v4.3.0
- published_at 2026-09-29T14:58:14Z
- https://github.com/teslamate-org/teslamate/releases/tag/v4.3.0
- annotated tag object cf1380d3c1a57dc8ee3c204366ea2dd8e3e1902d
- dereferenced commit 33d200b2fba9d5138803916a788cef5eae31b1aa

本地研究根目录：
/var/folders/0g/bsmpgt_x26z50l2w874_8k_h0000gn/T/mytesla-static-research-ad6q0vtp
- frontend-research/latest-4.3.0/ 完整官方 v4.3.0（本轮已读取确认存在）
- source-official/ 官方 v4.0.1
- source-fork/ 私人精确 fork
- source-diff.patch、findings.json、beam-evidence.json、official-releases.json、official-comparison.json、frontend-research/summary.json
这些只做本地研究；不要整包复制日志/镜像内容到新仓库。

关键官方文件：
elixir/lib/teslamate/locations/geocoder.ex
elixir/lib/teslamate/http.ex
elixir/lib/teslamate/locations.ex
elixir/lib/teslamate/locations/address.ex
elixir/config/runtime.exs
Dockerfile
elixir/test/teslamate/locations/geocoder_test.exs
elixir/test/teslamate/http_test.exs

本轮已读 Geocoder/HTTP/Address/Dockerfile：
- Geocoder.client 写死 BaseUrl，Finch receive_timeout=30_000。
- reverse_lookup 请求 /reverse，query 含 format=jsonv2/addressdetails/extratags/namedetails/zoom19/lat/lon，Accept-Language header。
- details 构造首字母大写 type + osm_id 字符串（所以 N-10001 会原样生成），/lookup 返回列表后 into_address。
- query 200 body 直接成功；非200 JSON error 则 {:error, reason}。
- into_address 若收到 {"error":"Unable to geocode"} 会建 Unknown（osm_type=unknown/id=0/坐标0）。适配器故障不能走此路径。
- address changeset required display_name/osm_id/osm_type/latitude/longitude/raw，并无正数校验；unique index 组合身份。
- HTTP.pools 硬编码 Nominatim origin => [size:3] ++ proxy opts。
- Dockerfile builder elixir:1.20.3-otp-29，安装 Node22，assets npm ci，MIX_ENV=prod；app debian:trixie-slim 非 root。
- Dockerfile COPY 上游 NOTICE/LICENSE 到镜像。检查补丁镜像必须保留。

## 私人 fork / 生产迁移背景（仅背景，禁止执行迁移）
私人来源 https://github.com/yekk-me/teslamate，mytesla/v4.0，
commit ed1a089fcecebca2eb450a0ed08af5a2e8779bc9；
parent 官方 v4.0.1 46a755b7ae45f818fce11db4df6cdccc16d8f9b5。
确实存在公开源码，别再说找不到源码。
fork reverse 用高德，前端标 OSM 却走作者 osm-proxy.mytesla.cc，details 仍走作者 OSM lookup。
已发现 phash2 参数范围/合成身份碰撞刷新问题、故障回退缺失、境外 guard 缺失，不能照搬。
历史生产静态观察 recorder=mytesla/teslamate:latest /4.0.1、Grafana 官方4.3.0、API1.25.0；不必重读生产凭据。
4.0.1->4.3.0 有5个迁移及历史充电能量重算；只恢复旧镜像不能回滚DB。生产迁移另需可恢复备份/副本还原验证和独立审批。

## 验收
- 可审查项目约定/任务材料，区分源码补丁、地址适配、底图、历史迁移边界。
- 固定官方版本可应用补丁；默认OSM/自定义URL都有测试，拒绝无效配置，调用方与pool一致。
- adapter reverse/lookup、转换、稳定身份、重启/TTL/语言切换、超时失败边界有无真实Key的模拟测试。
- GitHub 跟进流程 fail closed，清楚区分 build/publish 与生产 deploy。
- 中文 README 准确列出已完成/未完成、配置、验证方法、来源许可。
- 同步到现有私有 GitHub，真实验证提交与checks后报告；始终不改生产。

## 下一步建议
从现有 10-02-amap-mvp planning task 接续，完成 bootstrap 约定与 PRD/design/implement/context 后开始代码。独立交付部分可按 Trellis 创建子任务并行分工（adapter、上游补丁、release workflow）；不要覆盖他人编辑。当前没有其他开发 worker，也没有后台编译/测试进程。
