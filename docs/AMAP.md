# GeoRelay 地址适配指南

本指南介绍高德、百度和 OSM 地址服务的配置与维护。项目介绍和官方功能见[中文首页](../README.zh-CN.md)，修改范围见 [MODIFICATIONS.md](../MODIFICATIONS.md)，构建使用的官方版本见 [upstream.json](../upstream.json)。

## 架构与范围

```text
固定官方源码 + 地址 URL 与刷新补丁
  → 私有 Docker 网络中的 adapter
    → 高德 regeo / 百度逆地理编码 / 官方 Nominatim
    → 独立 SQLite 永久身份与响应缓存
```

补丁同时修改 Geocoder 的 BaseUrl 和专用 Finch pool，保留 pool size=3 与 proxy 配置。未配置自定义 URL 时，TeslaMate 仍使用官方 OSM。Sidecar 无需 Tesla token、ENCRYPTION_KEY 或生产 PostgreSQL 权限。

适配器改变地址文字来源，原 PostgreSQL 继续由 TeslaMate 管理。数据库、轨迹、SQLite 和适配器响应均保留原始 **WGS84**；高德大陆查询临时转换为 **GCJ-02**；百度使用 `coordtype=wgs84ll` 直接接收原坐标。

TeslaMate 在行程结束解析起终点、充电开始解析地址，启动及定时任务补修缺失地址，语言切换通过 lookup 刷新地址；普通 GPS 点不会逐点逆向解析。

## 路由与名称

`GEOCODER_PROVIDER` 设置默认策略；`/reverse`、`/lookup` 的 `provider=amap|baidu|osm` 可覆盖单次请求。TeslaMate 使用默认配置，地址供应商选择不改变 Web 底图。

| 配置 | 地址服务 |
| --- | --- |
| `GEOCODER_PROVIDER=auto`，`MAINLAND_PROVIDER=amap` | 默认：大陆高德、境外 OSM |
| `GEOCODER_PROVIDER=auto`，`MAINLAND_PROVIDER=baidu` | 大陆百度、境外 OSM |
| `GEOCODER_PROVIDER=amap` / `baidu` / `osm` | 固定使用指定服务 |

自动策略不依赖高德或百度海外权限。常见 GCJ-02 矩形仅用于快速排除，不能当作国界：

1. 框外或已由自动策略确认境外的坐标，直接使用 OSM。
2. 框内先请求选定大陆服务，仅接受明确的大陆地址。
3. 大陆服务失败、缺少凭据或无法确认地区时，由 OSM 确认。只有明确非大陆才接受 OSM；普通 `country_code=cn` 保留大陆服务错误。
4. OSM 港澳结果可能使用 `country_code=cn`，通过 `ISO3166-2-*` 中的 `CN-HK` / `CN-MO` 识别。

显式指定 OSM 的大陆查询不会改变该坐标的自动路由。真实 OSM 对象来源与地区确认分别保存；各策略的文字缓存相互隔离。

固定百度的海外解析需要相应权限。高德通过 `AMAP_API_REGION` 明确选择服务：`mainland` 使用国内接口和 GCJ-02，仅接受明确大陆地址；`global` 使用海外接口和 WGS84，需要对应海外服务 Key。境外固定使用高德时，同时设置 `GEOCODER_PROVIDER=amap`；仅更改 API region 不会改变 auto 的境外 OSM 策略。默认不把国内 Key 自动发送到海外域名。自动策略的境外地址仍使用 OSM，覆盖范围不依赖高德海外权限。

百度 SN 使用对应 AK 的 SK 签名，接口直接接收 WGS84；返回地点、道路和行政区组件。高德浏览器 JSAPI 的 `securityJsCode` 与服务端签名密钥不同，本服务不使用它。

高德使用 `extensions=all`，名称优先级如下：

```text
首条 AOI 名称 → 首条 POI 名称 → 建筑 → 小区 → 道路 → 完整地址
```

仅取供应商排序的首项，不遍历任意周边地点。空数组、缺失名称和错误结构会安全回退，`name` 与 `namedetails.name` 保持一致。已有响应缓存到期后自然刷新，永久身份不变。

公共 Nominatim 请求必须标识调用者并遵守[使用政策](https://operations.osmfoundation.org/policies/nominatim/)。服务使用缓存与本地文件锁串行化请求，每次完成后至少间隔一秒；仅运行一个实例并使用本地持久卷，不用于批量采集。OSM 响应保留数据 attribution。

## 接口

服务监听容器端口 `8080`，返回 JSON；仅面向受信任的私有网络。

| 接口 | 参数与行为 |
| --- | --- |
| `GET /reverse` | `lat`、`lon` 为原始 WGS84；返回 Nominatim 兼容地址 |
| `GET /lookup` | `osm_ids=N-1,N-2`，最多 50 个身份；返回请求的本地负数 node 身份，跳过来源未确认的正数身份 |
| `GET /health` | 检查本地 SQLite 就绪，成功为 `{"status":"ok"}` |

reverse / lookup 支持 `format=jsonv2`（也接受 `json`）和 `provider=amap|baidu|osm`。`Accept-Language` 区分缓存并传给 OSM；当前高德、百度查询不传语言参数，使用服务默认语言，因此英文请求也可能得到中文地址。

| 条件 | 状态码 |
| --- | --- |
| 参数非法、坐标越界、重复参数、超过 50 个身份 | `400` |
| 本地身份或端点不存在 | `404` |
| 非 node 的负数身份 | `422` |
| 上游失败、非法响应或身份不匹配 | `502` |
| 缺少所需配置或本地存储不可用 | `503` |
| 网络、限流锁或整批请求超时 | `504` |

有效缓存可直接返回；过期缓存刷新失败时明确报错，不合成永久 `Unknown`。`/health` 成功不代表 Key、配额或外网可用。

合法的正数 `N/W/R` 身份会被跳过，全正数批次返回 `[]`，不请求 OSM。混合批次中的本地负数身份仍正常刷新；不存在的本地负身份仍返回 `404`。这允许已有地址与新地址共存，但不导入或更新旧地址身份。

大陆冷查询使用最多4个并行任务，整批仍共享同一截止时间；超时返回 `504`，供应商配额或权限错误返回 `502`。可信 OSM 来源继续批量查询，并保留串行限流。

## 配置

### 补丁版 TeslaMate

`NOMINATIM_BASE_URL` 是**本项目新增变量，官方镜像本身不支持**：

```dotenv
NOMINATIM_BASE_URL=http://georelay-adapter:8080
NOMINATIM_LOCAL_IDENTITIES_ONLY=true
```

仅接受 HTTP/HTTPS origin，可含端口；不能包含账号、路径、query 或 fragment，末尾 `/` 会规范化。默认值为 `https://nominatim.openstreetmap.org`。`NOMINATIM_PROXY` 是 CONNECT proxy，不能替代自定义 geocoder URL。

`NOMINATIM_LOCAL_IDENTITIES_ONLY=true` 让修改版在语言刷新时跳过没有 lookup 结果的正数历史身份，避免上游逐条 reverse 回退。仅连接本适配器时启用；缺省 `false` 保留官方或自托管 OSM 的原行为，其他值拒绝。

### Sidecar

| 变量 | 默认值 / 用途 |
| --- | --- |
| `GEOCODER_PROVIDER` | 默认 `auto`；可选 `auto`、`amap`、`baidu`、`osm` |
| `MAINLAND_PROVIDER` | 默认 `amap`；自动策略大陆服务可选 `amap`、`baidu` |
| `BAIDU_AK` / `BAIDU_AK_FILE` | 百度服务端 AK；同一项两种来源互斥 |
| `BAIDU_SK` / `BAIDU_SK_FILE` | 与 AK 匹配的百度 SN 签名 SK；同一项两种来源互斥 |
| `AMAP_API_REGION` | 默认 `mainland`；`global` 显式选用海外 `sg-restapi.opnavi.com` 接口，请配套该服务的 Key |
| `AMAP_KEY` | 高德 Web 服务 Key，仅提供给 sidecar |
| `AMAP_KEY_FILE` | 可替代 `AMAP_KEY`；两者不能同时设置，文件须让容器 UID 10001 可读 |
| `NOMINATIM_USER_AGENT` | OSM 请求必填，包含应用名和实际联系方式；未配置时 OSM 请求返回 `503` |
| `ADAPTER_DB` | `/data/adapter.sqlite3`，必须永久保存 |
| `CACHE_TTL_SECONDS` | 默认 `86400`，最大 `31536000`；只影响响应缓存 |
| `UPSTREAM_TIMEOUT_SECONDS` | 单次上游默认 `8` 秒，最大 `20`；无自动重试 |
| `LOOKUP_TIMEOUT_SECONDS` | 整批 lookup 默认 `20` 秒，最大 `25` |

只需配置实际使用的服务凭据；缺少凭据的查询返回 `503`。所有 `_FILE` 文件需让容器 UID 10001 可读，通过只读挂载或 Compose secrets 提供，不与对应环境变量同时设置。

时间配置必须为大于零的有效数值。reverse 总预算为 `min(25, 2 × UPSTREAM_TIMEOUT_SECONDS + 1)` 秒，默认 17 秒，包含必要的地区确认；lookup 共享整批预算。单次上游响应读取上限为 1 MiB。

### Compose 示例

#### 接入现有 stack

现有 TeslaMate stack 的配置片段和镜像取得方式见[开始使用](../README.zh-CN.md#开始使用)。需要新增 `georelay-adapter`，同时将现有应用的 `image` 换成 GeoRelay 镜像并设置 `NOMINATIM_BASE_URL` 和 `NOMINATIM_LOCAL_IDENTITIES_ONLY=true`。保留其他环境变量、数据库、MQTT、Grafana 服务及原有卷；自定义网络下将适配器加入应用所在网络，并保留外网出口。早期适配器升级可保留 `amap-adapter` 服务名和对应 Base URL，只更换镜像引用；不要因项目改名新建身份卷。

#### 独立开发示例

在仓库根目录参照 [.env.example](../.env.example) 准备本地 `.env`。填写所选服务的凭据和调用者标识，保留该文件在 Git 忽略范围内。示例通过 `AMAP_KEY` 传值；选择 `AMAP_KEY_FILE` 时，需在 Compose 中添加对应环境变量及只读文件挂载，并清空 `AMAP_KEY`。

[compose.example.yaml](../compose.example.yaml) 仅运行适配器，用于独立开发和调试：

```sh
docker compose -f compose.example.yaml config --quiet
docker compose -f compose.example.yaml up -d --build
docker compose -f compose.example.yaml exec -T georelay-adapter python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/health").read().decode())'
```

示例使用非 root 用户、只读根文件系统和独立持久卷，不开放 host port。补丁版 TeslaMate 必须加入同一网络才能通过服务名访问适配器。网络使用保留外网出口的普通 bridge；`internal: true` 会阻断上游访问。示例不是完整 TeslaMate stack，也不是现有生产 stack 的替换文件。

## 开发与构建

在仓库根目录执行；自动测试不需要真实 Key：

```sh
python3 -m unittest discover -s tests -v
git diff --check
python3 scripts/prepare_upstream.py /tmp/georelay-build
bash scripts/test_upstream.sh /tmp/georelay-build
docker build -t georelay:local /tmp/georelay-build
docker build -t georelay-adapter:local adapter
bash scripts/test_main_image.sh georelay:local georelay-adapter:local
```

`prepare_upstream.py` 的目标目录必须不存在或为空。脚本核实 tag 解引用后的 commit，再严格应用两个地址补丁并检查空白；任何一步失败立即停止。

准备只修改地址集成需要的 HTTP、Locations 和 Geocoder 生产源码及对应测试。上游页面、名称、翻译、图标、法律文件和 Dockerfile 保持原样；这些内容变化或缺失不会触发本项目的额外审核门禁。应用仍显示 TeslaMate，仓库与镜像名为 GeoRelay。

上游检查脚本创建独立 Elixir/PostgreSQL 容器、随机网络和临时存储，无 host port，退出时清理。它执行官方编译、格式检查、原 Geocoder/HTTP 测试，以及新增 URL 配置和负数 signed bigint 数据库兼容测试。

`test_main_image.sh` 保留主镜像默认入口和启动命令，在独立 internal 网络连接全新临时 PostgreSQL，验证真实迁移及登录页面 HTTP 就绪。探测使用 adapter 镜像里的 Python，不映射 host port；成功、失败和超时均清理测试资源。CI 的两个原生架构在保存待发布镜像前执行此检查，失败阻止发布。

上述命令验证当前源码的模拟接口、身份持久化、批量预算和上游数据库刷新契约。实际构建和发布结果见仓库的 [Actions](https://github.com/srcheng17/georelay/actions)，核对运行对应的源码 commit。自动测试无需真实地图凭据，不能证明个人 Key 的权限、配额或生产迁移可行性。

## 永久身份与备份

同一规范化原始 WGS84 坐标始终对应同一个负数 `osm_id`，`osm_type=node`。它是适配器私有身份，不是真实 OSM 对象。重启、供应商切换、语言切换、TTL 到期和文字刷新均不改变身份；lookup 接受例如 `N-10001`。

成功从官方 OSM 请求获得的真实对象来源保存在 SQLite。使用 OSM 的语言刷新按可信来源批量调用官方 `/lookup`，严格核对返回身份集合，再还原每条本地负 ID 和原坐标；同一 OSM 对象对应多个本地坐标时也分别保留本地身份。外部传入的任意正数身份不会被盲目转发。

升级时自动迁移缓存的策略维度，保留旧身份映射。升级前备份 SQLite；回退代码时旧版无法理解新的缓存键，应在离线恢复副本中处理文字缓存，不能删除永久身份表。

SQLite 保存永久身份，不能当作可随意删除的缓存。丢失或回退映射库可能让新分配 ID 与已有地址冲突。使用 SQLite 在线 backup API，输出路径必须不存在。在实际 stack 目录执行，使用与运行该 stack 相同的 `-f` / `-p` 参数：

```sh
snapshot="adapter-snapshot-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
docker compose exec -T georelay-adapter python -m adapter.server --backup "/data/$snapshot"
docker compose cp "georelay-adapter:/data/$snapshot" "./$snapshot"
chmod 600 "./$snapshot"
```

仅当使用仓库的独立开发示例时，才在两条 Compose 命令中添加 `-f compose.example.yaml`。备份包含位置隐私，应与应用数据库备份一起受控保存到主机以外；验证副本后清理 `/data` 内快照。不要直接复制活动数据库文件。恢复时先停止 sidecar，恢复与 TeslaMate 数据一致的完整映射库，确认身份后再启动。`.osm.lock` 只保存限流时间，无需作为身份备份。

sidecar 的缓存 TTL 不会自动更新 PostgreSQL 里的已有地址。应用切换地址语言时，本地负数身份通过 `/lookup` 刷新，修改版将地点名、道路、门牌、行政字段和原始响应写回已有行，保留身份、坐标和关联。日常 reverse 仍复用同身份的已有数据库行。正数旧身份跳过刷新，保留原文字；不能通过切换语言自动迁移。

私人版本可能使用正数 hash，无法仅凭数值判断它是否为真实 OSM ID。旧地址身份导入、历史关联修复和 TeslaMate 数据库升级均属于独立迁移工作，需在恢复副本验证后另行执行。仅回退应用镜像不等于回滚已升级的数据库。

## 版本跟进与发布

自动流程只发布 GHCR 镜像，不更新运行容器。

1. [Check upstream release](../.github/workflows/upstream-release.yml) 每六小时检查官方稳定 release，也可在 main 手动触发。GitHub 定时调度可能延迟。
2. 新版本创建 upstream/tag 分支与 PR，只修改 upstream.json。草稿、预发布、降级或移动 tag 停止处理；共享 prepare 只应用严格地址补丁；不重写或比对上游 UI、翻译、图标与法律文本，不追加 Dockerfile 指令。
3. [Validate and build](../.github/workflows/ci.yml) 检出实际 PR head commit，原生 amd64/arm64 分别运行源码检查、共享 prepare/地址 ExUnit、镜像架构/用户与 adapter 许可检查，以及最终镜像内 adapter suite 和应用启动/迁移/地址闭环。应用保留上游 TeslaMate 界面，HTTP 就绪以实际登录表单为准。无需账号或真实地图 Key，使用独立临时资源。
4. 两架构通过后，复用相同已测试产物发布两个 package 的 beta 版本并验证索引；当前 PR 可更新 beta-pr-N，不能改写 latest。
5. [Beta release control](../.github/workflows/beta-control.yml) 从可信 main 读取 run、PR 与 registry 元数据。两架构/verify/beta 索引成功，PR 同仓且 open/non-draft、head 仍为 tested SHA、main 基线有效且服务器保护允许时，带 expected head SHA 普通 merge。fork、过期或被新提交替代的成功候选只跳过；控制器不执行候选脚本、不自动重写分支、不合并自身首次启用 PR。
6. 合并回读成功后显式 dispatch main，绑定 expected_main_sha 与 source_pr；GITHUB_TOKEN 合并的 push 本身不会触发新 CI。main 对 merge commit 重新构建/测试，发布正式版本与 latest；推广前回读 current main。main 的镜像相关 push 或 main publish dispatch 也可正式发布，latest 跟随已审阅 main pin，无需等待尚未合入的新官方版本。

成功、轻量检查和 check-only 不发通知。可信镜像构建、测试、合并操作、dispatch 或发布实际失败时发 Bark，含失败阶段、commit 与 PR/run 链接。beta 早期失败没有产物也能通知；合并后的 main 失败不要求 PR 仍 open。fork 和正常过期跳过不通知。

### 标签与运行服务更新

包名固定为 georelay 与 georelay-adapter，命名空间随 owner，源码仓库改名不改变包名。两个镜像使用相同版本：

- 正式：`<upstream-tag>-georelay-<完整源码commit>`，浮动别名 `latest`。
- beta：`<upstream-tag>-georelay-beta-<完整PR head commit>`，当前 PR 浮动别名 `beta-pr-N`。
- 每个版本索引都支持 linux/amd64 与 linux/arm64，架构标签使用 -amd64/-arm64 后缀。

```text
ghcr.io/srcheng17/georelay:<version>
ghcr.io/srcheng17/georelay-adapter:<version>
```

首页 Compose 和 .env.example 默认 latest；控制升级时机可设置同一 GEORELAY_VERSION 或分别锁定两个镜像 digest。版本标签本身不受 registry 强制不可变保证。两 package 无原子推广，任一上传/回读失败都会使 workflow 失败；若浮动标签暂不一致，使用已验证的相同固定版本。

latest 发布不会自动替换运行容器。更新服务时，先备份 TeslaMate 数据库和适配器身份库，再从现有 stack 目录执行：

```sh
docker compose pull teslamate georelay-adapter
docker compose up -d teslamate georelay-adapter
```

数据库迁移不能靠仅回退镜像撤销；本项目自动发布链路不执行这些生产操作。

### GitHub 配置与首次生效

在仓库 Settings → Secrets and variables → Actions 添加 repository secret `BARK_URL`，保存 HTTPS Bark endpoint；真实地址/设备 key 不进入代码、PR 或日志。GitHub hosted runner 必须能访问该 endpoint。先完成 payload dry-run、模拟接收及响应验证；Secret 缺失时明确报告未配置，不报告通知成功。请求有界重试，结果 uncertain 时不盲目重复发送；跨 workflow 重跑不承诺服务端幂等。

首次控制器 PR 仍须维护者明确审阅/合并，进入 main 后 workflow_run 自动化才生效。保留 strict verify 分支保护与 Actions 来源，不启用管理员 bypass 或新增 PAT。updater 创建 PR/dispatch；独立控制器完成已授权的条件合并与 main dispatch。异常 pin/分支来源停止处理，已运行或成功发布的同提交不重复触发。Bark 配置及首次生效后的实际自动链路需单独验收。

首次发布 package 需设置 public 并实际核验匿名拉取；公开 repo 不代表 package 自动公开。OCI source/revision/version 对应实际 tested commit；共享 prepare、pin 与补丁可重建镜像。

### 构建触发与镜像保留

普通分支 push 不增加重复构建；同仓 PR 更新触发 beta CI，未开 PR 的分支可手动 publish dispatch。fork 只验证，不持发布/Bark 写凭据。main push 只有镜像相关变更才完整构建和发布；README/docs/agent/Trellis/Paseo 元数据走轻量 Python/空白检查，required verify 仍出现。运行/未知路径、补丁、pin、测试及发布流程完整构建；删除/重命名计入。dispatch 始终完整构建，publish 默认关闭。

[镜像保留工作流](../.github/workflows/image-retention.yml) 每周 main 清理，手动默认预览。正式两个 package 都有正确双架构镜像/索引才算完整组，保留最近 10 组、latest 及其引用；按组而非 version 记录数排序。beta 不占正式额度，当前作为未知标签受保护；beta 历史会增长，自动清理延期。

清理与发布共用串行锁；两个 package 全部清单和依赖验证后，先删旧索引再删无保留引用的子镜像。读取/解析或权限失败停止，不完整/未知/未关联记录保留，不构成 registry 总记录硬上限。需要长期拉取旧镜像请自行镜像保存。

```sh
python3 scripts/retain_images.py --repository srcheng17/georelay
```

此命令只读；只有 --apply 或清理 workflow 关闭 dry_run 才删除，需两个 package 的管理员权限。本次引入自动化的首次合入仍由维护者明确授权；后续候选只在本节定义的成功/当前 SHA/分支保护条件下自动合并。

## 来源与许可

官方 [TeslaMate](https://github.com/teslamate-org/teslamate) 的 [LICENSE](../LICENSE)、[NOTICE](../NOTICE)、[TRADEMARK.md](../TRADEMARK.md) 原样保留；代码按 AGPL-3.0-or-later 提供，修改说明见 [MODIFICATIONS.md](../MODIFICATIONS.md)。准备脚本保留上游原生文件和 Dockerfile；应用镜像中的许可文件按该版本官方 Dockerfile 打包。适配器镜像保留自身代码许可与修改说明。

[高德逆地理编码文档](https://lbs.amap.com/api/webservice/guide/api/georegeo)、[百度逆地理编码文档](https://lbs.baidu.com/faq/api?title=webapi/guide/webservice-geocoding-abroad-base)、[Nominatim 使用政策](https://operations.osmfoundation.org/policies/nominatim/)与 [OpenStreetMap 数据许可](https://www.openstreetmap.org/copyright)分别约束对应服务和数据。
