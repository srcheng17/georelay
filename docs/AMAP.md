# GeoRelay 地址适配指南

本指南介绍高德、百度和 OSM 地址服务的配置与维护。项目介绍见[中文首页](../README.zh-CN.md)，修改范围见 [MODIFICATIONS.md](../MODIFICATIONS.md)，构建使用的官方版本见 [upstream.json](../upstream.json)。

## 架构与范围

```text
TeslaMate / PostgreSQL
  → 永久地址编号、精确 WGS84 原坐标、可信来源与历史关联
  → POST /v1/reverse 或 /v1/lookup，携带编号、坐标和来源
    → 私有 Docker 网络中的 adapter
      → 高德 regeo / 百度逆地理编码 / 官方 Nominatim
      → 可丢弃 SQLite 文字缓存与限流状态
```

应用先按精确坐标查找已有本地地址，只有新坐标才申请降序负编号并解析。供应商成功后写入地址；并发首次请求通过 PostgreSQL 唯一约束收敛到胜出行。编号空洞允许，失败不会写入 Unknown。

补丁同时修改 Geocoder 的 BaseUrl 和专用 Finch pool，保留 size=3 与 proxy。`GEORELAY_ADDRESS_MODE` 默认 `nominatim` 保留原 GET 官方路径；`application` 才启用本项目协议。Sidecar 无需 Tesla token、ENCRYPTION_KEY 或 PostgreSQL 权限。

地址、轨迹、缓存键和响应均保留原始 **WGS84**；高德大陆请求临时转换为 **GCJ-02**，百度直接接收 WGS84。地址文字解析仍由高德/百度/OSM提供；数据库管理编号和历史关联，不能从坐标自行得到地点名称。

TeslaMate 在行程结束、充电开始及缺失地址修复时解析，语言切换显式刷新地址；普通 GPS 点不会逐点逆向解析。

## 路由与名称

`GEOCODER_PROVIDER` 设置默认策略；版本化 POST 请求的 provider 字段可覆盖单次请求。TeslaMate 使用默认配置，地址供应商选择不改变 Web 底图。

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

服务监听容器端口 `8080`，仅面向受信任私网。应用与适配器必须使用同一配套版本；旧 GET 地址协议明确拒绝，不能混用镜像。

| 接口 | 参数与行为 |
| --- | --- |
| `POST /v1/reverse` | `version=1`、`address`、`language`，以及可选 `provider`；返回 Nominatim 形状的地址 |
| `POST /v1/lookup` | `version=1`、`addresses`（最多50项）、`language`、可选 `provider`；按请求顺序返回负 node 地址 |
| `GET /health` | 仅检查本地缓存就绪，成功为 `{"status":"ok","protocol":1,"storage":"disposable-cache"}` |

```json
{
  "version": 1,
  "address": {
    "osm_id": -10001,
    "osm_type": "node",
    "lat": "48.858400123",
    "lon": "2.294500456",
    "context": {
      "source_osm_type": "node",
      "source_osm_id": 123,
      "outside_mainland": true
    }
  },
  "language": "en"
}
```

示例为公开虚构测试上下文；`context` 的真实值只能来自应用已有可信来源。没有来源时传 {"outside_mainland": false}；不得从任意正编号推断 OSM 对象或把显式大陆 OSM 查询当作境外证据。响应附 `georelay` 版本/来源/境外证据，应用永久保留该上下文，供应商切换不会抹掉已有可信来源。

`language` 区分缓存并传给 OSM，高德/百度使用默认语言。缓存键包含规范化精确坐标、语言、策略和影响结果的来源上下文；缓存模板不保留客户端编号，返回时使用本次请求身份。删除缓存后可凭请求重建结果。

| 条件 | 状态码 |
| --- | --- |
| 非法 JSON/字段、坐标越界、重复负身份或超过50项 | `400` |
| 端点不存在 | `404` |
| 非 node 的负身份 | `422` |
| 旧 GET 地址协议 | `409` |
| 上游失败、非法响应或身份不匹配 | `502` |
| 缺配置或缓存存储不可用 | `503` |
| 网络、限流锁或整批预算耗尽 | `504` |

正数历史身份只跳过，不请求 OSM；全正批次返回 `[]`。应用刷新只传唯一的负 node 地址，保留历史正地址。lookup 失败不返回部分成功列表，不合成 Unknown；缓存可保留已成功解析的项目。应用核验返回身份集合、坐标与来源，不接受缺项、重复、额外项或移动后的坐标。

lookup 使用最多4线程、同一截止时间；可信 OSM 来源仍批量匹配，公共请求维持文件锁限流。`health` 成功不能证明 Key、配额或外网可用。

## 配置

### 补丁版 TeslaMate

`NOMINATIM_BASE_URL` 是**本项目新增变量，官方镜像本身不支持**：

```dotenv
NOMINATIM_BASE_URL=http://georelay-adapter:8080
GEORELAY_ADDRESS_MODE=application
```

仅接受 HTTP/HTTPS origin，可含端口；不能包含账号、路径、query 或 fragment，末尾 `/` 会规范化。默认值为 `https://nominatim.openstreetmap.org`。`NOMINATIM_PROXY` 是 CONNECT proxy，不能替代自定义 geocoder URL。

`GEORELAY_ADDRESS_MODE=application` 启用 PostgreSQL 地址所有权与新 POST 协议；只有完成显式 fresh 初始化或 legacy 导入后才能分配/刷新地址。默认 `nominatim` 继续使用官方或自托管 OSM。原 `NOMINATIM_LOCAL_IDENTITIES_ONLY` 仅用于旧 Nominatim 刷新策略，不代替新模式初始化。

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
| `ADAPTER_CACHE_DB` | `/data/cache.sqlite3`，只保存可丢弃缓存 |
| `CACHE_TTL_SECONDS` | 默认 `86400`，最大 `31536000`；只影响响应缓存 |
| `UPSTREAM_TIMEOUT_SECONDS` | 单次上游默认 `8` 秒，最大 `20`；无自动重试 |
| `LOOKUP_TIMEOUT_SECONDS` | 整批 lookup 默认 `20` 秒，最大 `25` |

显式旧 ADAPTER_DB 或把含 identities 的旧文件指定为新缓存会拒绝启动，旧文件保持不变。新 cache 默认每60秒有界清理最多500条过期记录；TTL 到期不会改写 PostgreSQL。

只需配置实际使用的服务凭据；缺少凭据的查询返回 `503`。所有 `_FILE` 文件需让容器 UID 10001 可读，通过只读挂载或 Compose secrets 提供，不与对应环境变量同时设置。

时间配置必须为大于零的有效数值。reverse 总预算为 `min(25, 2 × UPSTREAM_TIMEOUT_SECONDS + 1)` 秒，默认 17 秒，包含必要的地区确认；lookup 共享整批预算。单次上游响应读取上限为 1 MiB。

### Compose 示例

#### 接入现有 stack

现有 TeslaMate stack 的配置片段和镜像取得方式见[开始使用](../README.zh-CN.md#开始使用)。需要新增 `georelay-adapter`，同时将现有应用的 `image` 换成 GeoRelay 镜像并设置 `NOMINATIM_BASE_URL` 和 `GEORELAY_ADDRESS_MODE=application`。保留其他环境变量、数据库、MQTT、Grafana 服务及原有卷；自定义网络下将适配器加入应用所在网络，并保留外网出口。已有适配器服务保留 `amap-adapter` 服务名和对应 Base URL，命令中的服务名也按实际 stack 使用，原 Compose project 和卷保持不变。数据迁移步骤见下文，不能只更换镜像跳过初始化。

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

`prepare_upstream.py` 的目标目录必须不存在或为空。脚本核实 tag 解引用后的 commit，再严格应用全部地址补丁并检查空白；任何一步失败立即停止。

准备修改地址集成需要的 HTTP、Locations、Geocoder、本地身份模块、地址精度迁移及对应测试。上游页面、名称、翻译、图标、法律文件和 Dockerfile 保持原样；这些内容变化或缺失不会触发本项目的额外审核门禁。应用仍显示 TeslaMate，仓库与镜像名为 GeoRelay。

上游检查脚本创建独立 Elixir/PostgreSQL 容器、随机网络和临时存储，无 host port，退出时清理。它执行官方编译、格式检查、原 Geocoder/HTTP 测试，以及新增 URL 配置和负数 signed bigint 数据库兼容测试。

`test_main_image.sh` 保留主镜像默认入口和启动命令，在独立 internal 网络连接全新临时 PostgreSQL，验证真实迁移及登录页面 HTTP 就绪。探测使用 adapter 镜像里的 Python，不映射 host port；成功、失败和超时均清理测试资源。CI 的两个原生架构在保存待发布镜像前执行此检查，失败阻止发布。

上述命令验证当前源码的模拟接口、身份持久化、批量预算和上游数据库刷新契约。实际构建和发布结果见仓库的 [Actions](https://github.com/srcheng17/georelay/actions)，核对运行对应的源码 commit。自动测试无需真实地图凭据，不能证明个人 Key 的权限、配额或生产迁移可行性。

## 永久身份与备份

同一规范化精确 WGS84 坐标对应稳定负 `osm_id`、`osm_type=node`。应用 addresses 行是唯一永久坐标权威，编号序列只保存高水位，不复制坐标。真实 OSM 来源与独立境外证据保存在 `raw.georelay`；同一真实 OSM 对象可以对应多个本地地址。

### 新安装

只有从未使用旧 SQLite 身份库的安装才声明 fresh。PostgreSQL 当前没有负地址不能证明旧库没有分配过未引用编号。应用启动迁移不会自动选择 fresh：

```sh
docker compose exec -T teslamate bin/teslamate rpc 'IO.inspect(TeslaMate.Locations.LocalIdentities.initialize_fresh(fresh_install: true))'
docker compose exec -T teslamate bin/teslamate rpc 'IO.inspect(TeslaMate.Locations.LocalIdentities.initialize_fresh(apply: true, fresh_install: true))'
```

先预览，确认成功再 apply；失败或证据不足停止。初始化标记保存在 PostgreSQL，未完成时地址功能拒绝工作，应用登录页仍可用。

### 从旧 SQLite 迁移

先在停写窗口取得 PostgreSQL 与旧 SQLite 的一致备份，并在隔离恢复副本演练。SQLite 使用旧版本的在线 backup API 或停止旧服务后复制，不复制活动 WAL 文件。旧版本快照示例：

```sh
snapshot="adapter-snapshot-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
docker compose exec -T georelay-adapter python -m adapter.server --backup "/data/$snapshot"
docker compose cp "georelay-adapter:/data/$snapshot" ./legacy-identities.sqlite3
chmod 600 ./legacy-identities.sqlite3
```

上述 backup 必须在切换到新缓存版本前执行，新版本 `--backup` 只备份缓存。保留原 Compose project、卷与服务名；示例若与现有名称不同，应替换为实际服务名。备份与导出含精确位置，应保存在权限受控的目录并移出 Docker 主机。

仓库导出工具默认只读审计；通过后显式写出权限0600的导入文件：

```sh
python3 scripts/export_legacy_identities.py ./legacy-identities.sqlite3
python3 scripts/export_legacy_identities.py ./legacy-identities.sqlite3 --export --output ./legacy-identities.json
```

启动配套应用/适配器，设置 `GEORELAY_ADDRESS_MODE=application`，移除旧 `ADAPTER_DB`，使用独立 `ADAPTER_CACHE_DB`。将导出文件放进应用临时路径并保持只让应用用户读取；以下命令先预览，成功后再执行 apply：

```sh
docker compose cp ./legacy-identities.json teslamate:/tmp/georelay-identities.json
docker compose exec -T --user root teslamate chown nonroot:nonroot /tmp/georelay-identities.json
docker compose exec -T teslamate bin/teslamate rpc 'IO.inspect(TeslaMate.Locations.LocalIdentities.import_file("/tmp/georelay-identities.json"))'
docker compose exec -T teslamate bin/teslamate rpc 'IO.inspect(TeslaMate.Locations.LocalIdentities.import_file("/tmp/georelay-identities.json", apply: true))'
docker compose exec -T teslamate rm /tmp/georelay-identities.json
```

导入审计负身份/类型、完整 SQLite 已分配高水位（包括未引用记录和 AUTOINCREMENT 历史）、原坐标、来源与区域证据。恢复可证明的原精度，保留地址主键和负编号、行程/充电外键，不制造未引用空白地址。缺项、冲突、精度或来源证据不符会停止，不能按六位坐标或距离合并。

导入提交为原子操作，完成后才建立精确坐标约束并启用新编号序列。地址坐标改用不限 scale NUMERIC；positions 仍为原六位精度，已有轨迹不修改。因此六位 Position 和恢复后的高精度 Address 可能是不同 canonical 点，不能强行复用。

### 备份、缓存与回滚

新模式只需将 PostgreSQL 作为永久数据备份。缓存和限流文件可以重建；停止适配器后删除新 cache 文件及其 WAL/SHM，不触碰旧身份档案，再启动服务并验证历史刷新。删除限流文件后仍遵守公共服务的启动限流。

缓存到期不会自动更新 PostgreSQL；应用显式语言刷新写回地点、道路、门牌、行政字段及 raw，保留身份/原坐标/关联。新模式普通查找先复用已有地址。

封存旧 SQLite 与迁移截止点的 PostgreSQL 备份。新应用开始分配编号后，旧库没有新增身份，不能只降级镜像回滚；需要恢复相同截止点的匹配备份并明确之后新增数据范围。不限 scale 坐标不能静默降回六位；本方案不提供长期双写或自动反向迁移。历史正数 hash 的迁移仍需单独方案。

## 版本跟进与发布

自动流程只发布 GHCR 镜像，不更新运行容器。

1. [Check upstream release](../.github/workflows/upstream-release.yml) 每六小时检查官方稳定 release，也可在 main 手动触发。GitHub 定时调度可能延迟。
2. 新版本创建 upstream/tag 分支与 PR，只修改 upstream.json。草稿、预发布、降级或移动 tag 停止处理；共享 prepare 只应用严格地址补丁；不重写或比对上游 UI、翻译、图标与法律文本，不追加 Dockerfile 指令。
3. [Validate and build](../.github/workflows/ci.yml) 检出实际 PR head commit，原生 amd64/arm64 分别运行源码检查、共享 prepare/地址 ExUnit、镜像架构/用户与 adapter 许可检查，以及最终镜像内 adapter suite 和应用启动/迁移/地址闭环。应用保留上游 TeslaMate 界面，HTTP 就绪以实际登录表单为准。无需账号或真实地图 Key，使用独立临时资源。
4. 两架构通过后，复用相同已测试产物发布两个 package 的 beta 版本并验证索引；当前 PR 可更新 beta-pr-N，不能改写 latest。
5. [Beta release control](../.github/workflows/beta-control.yml) 从可信 main 读取 run、PR 与 registry 元数据。两架构/verify/beta 索引与 Release 记录成功，PR 同仓且 open/non-draft、head 仍为 tested SHA、main 基线有效且服务器保护允许时，带 expected head SHA 普通 merge。fork、过期或被新提交替代的成功候选只跳过；控制器不执行候选脚本、不自动重写分支、不合并自身首次启用 PR。
6. 合并回读成功后显式 dispatch main，绑定 expected_main_sha 与 source_pr；GITHUB_TOKEN 合并的 push 本身不会触发新 CI。main 对 merge commit 重新构建/测试，发布正式版本与 latest；推广前回读 current main。main 的镜像相关 push 或 main publish dispatch 也可正式发布，latest 跟随已审阅 main pin，无需等待尚未合入的新官方版本。

成功、轻量检查和 check-only 不发通知。可信镜像构建、测试、合并操作、dispatch 或发布实际失败时发 Bark，含失败阶段（包括 Release 记录）、commit 与 PR/run 链接。beta 早期失败由可信控制器通知；main CI的独立收尾job直接通知正式失败，覆盖前序失败与发布job超时，避免依赖bot dispatch后未触发的workflow_run。稳定控制器不重复发送main通知。合并后的 main 失败不要求 PR 仍 open；关联API不可读时保留基本run通知。fork 和正常过期跳过不通知。

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

latest 发布不会自动替换运行容器。更新服务时，先备份 TeslaMate 数据库、确认所选版本的迁移要求，再从现有 stack 目录执行：

```sh
docker compose pull teslamate georelay-adapter
docker compose up -d teslamate georelay-adapter
```

数据库迁移不能靠仅回退镜像撤销；本项目自动发布链路不执行这些生产操作。

### Release 更新说明与补录

每份已验证的固定双镜像对应同名 Git tag 和 [Release](https://github.com/srcheng17/georelay/releases)，tag 指向实际测试源码；beta 使用预发布 Release。正文列出本项目更新、上游版本、官方变更链接、两镜像 digest、平台与原 Actions attempt。上游自动更新仍只改 upstream.json，Release 会显示上游旧版本 → 新版本；不能证明此前发布基线时明确注明，不虚构版本范围。

维护 adapter/patches 功能或迁移时，同一提交添加或更新 `docs/changes/*.md` 的可读说明；只重命名旧说明不算新内容。发布记录器从精确源码读取这些文字，冻结首次基线，重试保持人工添加的外围正文。

固定镜像与浮动标签分别记录。过期来源或跳过别名的固定组仍有记录；别名部分失败时记录已验证的固定事实，整体发布仍失败。只有当前 main 正式源码的两个实际 latest 都匹配时才可设 GitHub latest。Release 记录失败也不算完整发布，控制器/updater/正式失败通知都检查该门禁。

publisher 只保存数据 receipt，无源码写权限；独立可信 main job 验证原 run/attempt、官方 pin 与两个镜像索引后写 tag/Release，不执行候选脚本。receipt artifact 名为 `publication-receipt-<run>-<attempt>-<source>-<version>`，请求保留 90 天（受仓库上限），JSON 最多 64 KiB、ZIP 最多 1 MiB。缺失、过期或证据不匹配时停止，不能靠重建猜测原发布结果。

仅记录失败时，在 main 手动运行 [Record existing image release](../.github/workflows/release-only.yml)，填写原 `original_run_id`、`original_attempt`、`original_source` 和 `original_version`。该流程只重验并补录，不构建或推送镜像，不推广别名、不更新容器。也可先从可信 main 本地执行只读预览：

```sh
python3 scripts/record_release.py --repository srcheng17/georelay \
  --run-id RUN_ID --attempt ATTEMPT --source FULL_SHA --version FIXED_VERSION --repair
```

CLI 默认只读，`--apply` 才写。补录成功只替代失败的记录门禁；构建、verify、publish 或别名失败不会被豁免。updater 轮询补录结果并显式触发受限 beta 重评，再次核对当前 PR/head/base/保护，避免依赖 bot workflow_run 是否触发。

可信 writer 首次需当前任务经明确审阅合入 main；main 尚无脚本时返回 `bootstrap_not_enabled`，不能作为完整 beta 放行。默认 GITHUB_TOKEN 对修改 workflow 的 beta 精确源码创建 tag/Release 的能力仍待获授权后实测；权限失败会明确阻断，不换用 PAT/App 或改写 tag 目标。

### GitHub 配置与首次生效

在仓库 Settings → Secrets and variables → Actions 添加 repository secret `BARK_URL`，保存 HTTPS Bark endpoint；真实地址/设备 key 不进入代码、PR 或日志。GitHub hosted runner 必须能访问该 endpoint。先完成 payload dry-run、模拟接收及响应验证；Secret 缺失时明确报告未配置，不报告通知成功。请求有界重试，结果 uncertain 时不盲目重复发送；跨 workflow 重跑不承诺服务端幂等。

首次控制器 PR 仍须维护者明确审阅/合并，进入 main 后 workflow_run 自动化才生效。保留 strict verify 分支保护与 Actions 来源，不启用管理员 bypass 或新增 PAT。控制器读取公开保护摘要确认所有人必须通过 verify；普通 merge 接口原子执行已有 strict 规则。Actions token 无权读取 strict 详情，不为此申请管理员凭据。updater 创建 PR/dispatch；独立控制器完成已授权的条件合并与 main dispatch。异常 pin/分支来源停止处理，已运行或成功发布的同提交不重复触发。Bark 配置及首次生效后的实际自动链路需单独验收。

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
