# 地址适配指南

本指南介绍高德、百度和 OSM 地址服务的配置与维护。项目介绍和官方功能见[中文首页](../README.zh-CN.md)，修改范围见 [MODIFICATIONS.md](../MODIFICATIONS.md)，构建使用的官方版本见 [upstream.json](../upstream.json)。

## 架构与范围

```text
固定官方 TeslaMate + NOMINATIM_BASE_URL 补丁
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
| `GET /lookup` | `osm_ids=N-1,N-2`，最多 50 个本地负数 node 身份；只返回请求身份 |
| `GET /health` | 检查本地 SQLite 就绪，成功为 `{"status":"ok"}` |

reverse / lookup 支持 `format=jsonv2`（也接受 `json`）和 `provider=amap|baidu|osm`。`Accept-Language` 区分缓存并传给 OSM；当前高德、百度查询不传语言参数，使用服务默认语言，因此英文请求也可能得到中文地址。

| 条件 | 状态码 |
| --- | --- |
| 参数非法、坐标越界、重复参数、超过 50 个身份 | `400` |
| 本地身份或端点不存在 | `404` |
| 正数历史身份或非 node 的负数身份 | `422` |
| 上游失败、非法响应或身份不匹配 | `502` |
| 缺少所需配置或本地存储不可用 | `503` |
| 网络、限流锁或整批请求超时 | `504` |

有效缓存可直接返回；过期缓存刷新失败时明确报错，不合成永久 `Unknown`。`/health` 成功不代表 Key、配额或外网可用。

## 配置

### 补丁版 TeslaMate

`NOMINATIM_BASE_URL` 是**本项目新增变量，官方镜像本身不支持**：

```dotenv
NOMINATIM_BASE_URL=http://amap-adapter:8080
```

仅接受 HTTP/HTTPS origin，可含端口；不能包含账号、路径、query 或 fragment，末尾 `/` 会规范化。默认值为 `https://nominatim.openstreetmap.org`。`NOMINATIM_PROXY` 是 CONNECT proxy，不能替代自定义 geocoder URL。

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

现有 TeslaMate stack 的配置片段和镜像取得方式见[开始使用](../README.zh-CN.md#开始使用)。需要新增 `amap-adapter`，同时将现有 TeslaMate 的 `image` 换成补丁镜像并设置 `NOMINATIM_BASE_URL`。保留其他环境变量、数据库、MQTT、Grafana 服务及原有卷；自定义网络下将适配器加入 TeslaMate 所在网络，并保留外网出口。

#### 独立开发示例

在仓库根目录参照 [.env.example](../.env.example) 准备本地 `.env`。填写所选服务的凭据和调用者标识，保留该文件在 Git 忽略范围内。示例通过 `AMAP_KEY` 传值；选择 `AMAP_KEY_FILE` 时，需在 Compose 中添加对应环境变量及只读文件挂载，并清空 `AMAP_KEY`。

[compose.example.yaml](../compose.example.yaml) 仅运行适配器，用于独立开发和调试：

```sh
docker compose -f compose.example.yaml config --quiet
docker compose -f compose.example.yaml up -d --build
docker compose -f compose.example.yaml exec -T amap-adapter python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/health").read().decode())'
```

示例使用非 root 用户、只读根文件系统和独立持久卷，不开放 host port。补丁版 TeslaMate 必须加入同一网络才能通过服务名访问适配器。网络使用保留外网出口的普通 bridge；`internal: true` 会阻断上游访问。示例不是完整 TeslaMate stack，也不是现有生产 stack 的替换文件。

## 开发与构建

在仓库根目录执行；自动测试不需要真实 Key：

```sh
python3 -m unittest discover -s tests -v
git diff --check
python3 scripts/prepare_upstream.py /tmp/teslamate-amap-build
bash scripts/test_upstream.sh /tmp/teslamate-amap-build
docker build -t teslamate-amap:local /tmp/teslamate-amap-build
docker build -t amap-adapter:local adapter
```

`prepare_upstream.py` 的目标目录必须不存在或为空。脚本核实 tag 解引用后的 commit，再严格应用全部补丁；任何一步失败立即停止。

上游检查脚本创建独立 Elixir/PostgreSQL 容器、随机网络和临时存储，无 host port，退出时清理。它执行官方编译、格式检查、原 Geocoder/HTTP 测试，以及新增 URL 配置和负数 signed bigint 数据库兼容测试。

验证记录包含 32 项 Python 测试、105 项 ExUnit 测试、真实服务隔离联调，以及 AOI/POI 名称回归的只读样本核对。详见[基础验收](../.trellis/tasks/archive/2026-10/10-02-amap-mvp/validation.md)和[名称回归验收](../.trellis/tasks/archive/2026-10/10-02-amap-poi-name/validation.md)。记录同时列出样本局限及固定上游依赖公告；构建通过不等于已完成生产迁移或解决全部依赖风险。

## 永久身份与备份

同一规范化原始 WGS84 坐标始终对应同一个负数 `osm_id`，`osm_type=node`。它是适配器私有身份，不是真实 OSM 对象。重启、供应商切换、语言切换、TTL 到期和文字刷新均不改变身份；lookup 接受例如 `N-10001`。

成功从官方 OSM 请求获得的真实对象来源保存在 SQLite。使用 OSM 的语言刷新按可信来源批量调用官方 `/lookup`，严格核对返回身份集合，再还原每条本地负 ID 和原坐标；同一 OSM 对象对应多个本地坐标时也分别保留本地身份。外部传入的任意正数身份不会被盲目转发。

升级时自动迁移缓存的策略维度，保留旧身份映射。升级前备份 SQLite；回退代码时旧版无法理解新的缓存键，应在离线恢复副本中处理文字缓存，不能删除永久身份表。

**SQLite 不是可随意删除的缓存。** 丢失或回退映射库可能让新分配 ID 与 TeslaMate 已有地址冲突。使用 SQLite 在线 backup API，输出路径必须不存在：

```sh
docker compose -f compose.example.yaml exec -T amap-adapter python -m adapter.server --backup /data/adapter-snapshot.sqlite3
docker compose -f compose.example.yaml cp amap-adapter:/data/adapter-snapshot.sqlite3 ./adapter-snapshot.sqlite3
```

备份包含位置隐私，应受控保存；不要直接复制活动数据库文件。恢复时先停止 sidecar，恢复与 TeslaMate 数据一致的完整映射库，确认身份后再启动。`.osm.lock` 只保存限流时间，无需作为身份备份。

私人版本可能使用正数 hash，无法仅凭数值判断它是否为真实 OSM ID。旧地址身份导入、历史关联修复和 TeslaMate 数据库升级均属于独立迁移工作，需在恢复副本验证后另行执行。仅回退应用镜像不等于回滚已升级的数据库。

## 版本跟进与发布

发布镜像与更新正在运行的服务分开进行。

1. [Check upstream release](../.github/workflows/upstream-release.yml) 每六小时检查官方稳定 release，也可在 `main` 手动触发。GitHub 定时任务可能延迟，不保证官方发布后立即执行。
2. 检测到新版本后，自动创建 `upstream/<tag>` 分支，仅修改 `upstream.json`，并打开更新 PR。tag 解引用到完整 commit；草稿、预发布、降级或移动 tag 会停止处理。
3. 显式触发 [Validate and build](../.github/workflows/ci.yml)。原生 amd64 和 arm64 runner 分别验证 Python、严格补丁、ExUnit、镜像架构/许可及非 root 健康检查。任一失败都会阻止发布，更新 PR 保留供维护者修复，不自动合并。
4. 检查全部通过后，从两份已测试镜像产物发布架构标签和多架构版本索引，不重新构建。`main` 上影响镜像的 push 也会自动发布；仍可在 `main` 手动运行并勾选 `publish`。
5. 两个版本索引都发布并验证后，更新两个 `latest` 并回读核对。发布任务串行执行，过期的官方版本或源码任务不能覆盖 `latest`。两个 package 无法原子更新；任何更新或回读失败都会让工作流失败，此时两个 `latest` 可能暂时不一致，应使用已发布的相同固定版本。

两个公开镜像使用同一版本，标签格式为 `<upstream-tag>-amap-<完整源码commit>`：

```text
ghcr.io/srcheng17/teslamate-amap:<version>
ghcr.io/srcheng17/teslamate-amap-adapter:<version>
```

首页 Compose 片段和 [.env.example](../.env.example) 默认使用 `latest`，无需每次修改版本号。需要控制升级时机时，从两个 package 页面选择相同版本，设置为 stack 的 `TESLAMATE_AMAP_VERSION`。多架构索引支持 `linux/amd64` 和 `linux/arm64`，Docker 会选择对应架构。需要锁定镜像内容时分别使用两个镜像的 digest；版本标签本身不是注册表强制不可变的标签。

`latest` 更新不会自动替换运行中的容器。先备份 TeslaMate 数据库和适配器永久身份库，再在现有 stack 目录拉取并重建两个服务：

```sh
docker compose pull teslamate amap-adapter
docker compose up -d teslamate amap-adapter
```

新版本可能包含 TeslaMate 数据库迁移；仅回退镜像不能撤销迁移。

首次 package 发布后需设置为 public，并实际验证匿名拉取；公有仓库不代表 package 自动公开。updater 使用工作流的 `contents: write`、`pull-requests: write`、`actions: write` 权限，仓库需允许 Actions 创建 PR；它不会审批或合并 PR。已存在的同版本分支和 PR 会复用，异常 pin 或分支修改会拒绝。候选分支建立后 main 发生变化，也会停止并要求维护者复核，不自动重写该分支；运行中的或已成功的同提交构建不重复触发；失败时仅在 main 和候选分支未变的情况下可重试，源分支前进后需维护者处理该 PR。

镜像的 source/revision/version 标签对应本仓库源码 commit，该 commit 的 `upstream.json` 与补丁可重建该镜像。维护者仍需审查更新 PR 并同步 main；自动发布不会变更用户的 stack、数据库或运行镜像。

### 构建触发与镜像保留

普通任务分支的 push 本身不发布镜像；PR 运行验证。`main` 的 push 根据整次改动判断是否需要镜像：仅文档、agent 指令、Trellis 元数据或 `paseo.json` 改动时，只运行 Python 与空白检查，必需的 `verify` 汇总检查仍会完成。运行代码、补丁、`upstream.json`、测试、构建或发布流程，以及无法识别的路径，均执行完整双架构构建。删除和重命名也参与判断；无法确定改动范围时执行完整构建。手动 dispatch 始终完整构建，`publish` 默认关闭；上游更新自动化仍显式开启发布。

[镜像保留工作流](../.github/workflows/image-retention.yml) 每周在 `main` 执行清理，手动运行默认只预览。它按两个 package 都具备版本索引和匹配 amd64/arm64 镜像的完整发布组计算，保留最近 10 组、两个 `latest` 及保留索引引用的子镜像。排序依据发布时间，不能只保留十条 registry version 记录，否则会破坏多架构镜像。

清理与发布共用串行锁，先完成两个 package 的清单和依赖验证，再删除旧索引及不再被保留索引引用的子镜像。读取失败、元数据不完整或缺少被引用的镜像时，停止并保持镜像不变。不完整发布、未知标签和未关联的无标签记录保留供维护者复核，因此策略限制正常完整发布历史，并非 registry 所有记录的硬上限。被删除的旧版本或 digest 无法继续从 GHCR 拉取；需要长期保存的版本请提前同步到自己的仓库。

本地只读预览命令：

```sh
python3 scripts/retain_images.py --repository srcheng17/teslamate
```

读取 package version 清单需要相应权限；清理工作流使用仓库 `GITHUB_TOKEN`，仓库必须拥有这两个 package 的管理员权限，权限不足会停止。脚本默认不删除；只有显式 `--apply` 或手动工作流关闭 `dry_run` 才应用策略。PR 的 push、CI 通过和镜像发布均不构成合并授权，合并必须由维护者明确决定。

## 来源与许可

官方 [TeslaMate](https://github.com/teslamate-org/teslamate) 的 [LICENSE](../LICENSE)、[NOTICE](../NOTICE)、[TRADEMARK.md](../TRADEMARK.md) 原样保留；代码按 AGPL-3.0-or-later 提供，修改说明见 [MODIFICATIONS.md](../MODIFICATIONS.md)。两个镜像保留各自代码许可，官方镜像构建继续保留其 NOTICE。

[高德逆地理编码文档](https://lbs.amap.com/api/webservice/guide/api/georegeo)、[百度逆地理编码文档](https://lbs.baidu.com/faq/api?title=webapi/guide/webservice-geocoding-abroad-base)、[Nominatim 使用政策](https://operations.osmfoundation.org/policies/nominatim/)与 [OpenStreetMap 数据许可](https://www.openstreetmap.org/copyright)分别约束对应服务和数据。
