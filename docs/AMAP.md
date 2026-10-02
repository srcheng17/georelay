# 高德地址适配指南

本指南介绍高德地址服务的配置与维护。项目介绍和官方功能见[首页](../README.md)，修改范围见 [MODIFICATIONS.md](../MODIFICATIONS.md)，构建使用的官方版本见 [upstream.json](../upstream.json)。

## 架构与范围

```text
固定官方 TeslaMate + NOMINATIM_BASE_URL 补丁
  → 私有 Docker 网络中的 adapter
    → 高德 regeo / 官方 Nominatim
    → 独立 SQLite 永久身份与响应缓存
```

补丁同时修改 Geocoder 的 BaseUrl 和专用 Finch pool，保留 pool size=3 与 proxy 配置。未配置自定义 URL 时，TeslaMate 仍使用官方 OSM。Sidecar 无需 Tesla token、ENCRYPTION_KEY 或生产 PostgreSQL 权限。

适配器改变地址文字来源；原 PostgreSQL 继续由 TeslaMate 管理，客户端继续读取原数据。HedgieMate/Grafana 的底图、地图显示纠偏和刷新频率由客户端决定。数据库、轨迹、SQLite 和适配器响应均保留原始 **WGS84**；仅发给高德的查询临时转换为 **GCJ-02**。

TeslaMate 在行程结束解析起终点、充电开始解析地址，启动及定时任务补修缺失地址，语言切换通过 lookup 刷新地址；普通 GPS 点不会逐点逆向解析。

## 路由与名称

默认策略为**大陆高德、境外 OSM**，不依赖高德海外服务权限。常见 GCJ-02 矩形仅用于快速排除，不能当作国界：

1. 框外直接请求官方 Nominatim；已有可信 OSM 来源的坐标也直接使用 OSM。
2. 框内首次解析先请求高德，仅接受明确的大陆地址。
3. 高德失败、缺少 Key 或无法确认地区时，请求 OSM 确认。只有明确的非大陆地址才接受 OSM 结果；普通 `country_code=cn` 保留原高德错误。
4. 香港、澳门的 OSM 结果可能使用 `country_code=cn`，通过 `ISO3166-2-*` 字段中的 `CN-HK` / `CN-MO` 识别。成功确认的 OSM 来源永久保存，后续避免重复探测高德。

首次解析可能请求两个服务；这不是精确国界多边形判断。高德本身存在海外服务，本项目选择境外 OSM。

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

reverse / lookup 支持 `format=jsonv2`（也接受 `json`）。`Accept-Language` 区分缓存并传给 OSM；当前高德查询不传语言参数，因此英文请求也可能得到中文地址。

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
| `AMAP_KEY` | 高德 Web 服务 Key，仅提供给 sidecar |
| `AMAP_KEY_FILE` | 可替代 `AMAP_KEY`；两者不能同时设置，文件须让容器 UID 10001 可读 |
| `NOMINATIM_USER_AGENT` | OSM 请求必填，包含应用名和实际联系方式；未配置时 OSM 请求返回 `503` |
| `ADAPTER_DB` | `/data/adapter.sqlite3`，必须永久保存 |
| `CACHE_TTL_SECONDS` | 默认 `86400`，最大 `31536000`；只影响响应缓存 |
| `UPSTREAM_TIMEOUT_SECONDS` | 单次上游默认 `8` 秒，最大 `20`；无自动重试 |
| `LOOKUP_TIMEOUT_SECONDS` | 整批 lookup 默认 `20` 秒，最大 `25` |

时间配置必须为大于零的有效数值。reverse 总预算为 `min(25, 2 × UPSTREAM_TIMEOUT_SECONDS + 1)` 秒，默认 17 秒，包含必要的地区确认；lookup 共享整批预算。单次上游响应读取上限为 1 MiB。

### Compose 示例

在仓库根目录参照 [.env.example](../.env.example) 准备本地 `.env`。填写 Key 和调用者标识，保留该文件在 Git 忽略范围内。示例通过 `AMAP_KEY` 传值；选择 `AMAP_KEY_FILE` 时，需在 Compose 中添加对应环境变量及只读文件挂载，并清空 `AMAP_KEY`。

[compose.example.yaml](../compose.example.yaml) 仅运行 sidecar，可用于开发和后续部署审查：

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

同一规范化原始 WGS84 坐标始终对应同一个负数 `osm_id`，`osm_type=node`。它是适配器私有身份，不是真实 OSM 对象。重启、语言切换、TTL 到期和文字刷新均不改变身份；lookup 接受例如 `N-10001`。

成功从官方 OSM 请求获得的真实对象来源保存在 SQLite。境外语言刷新按可信来源批量调用官方 `/lookup`，严格核对返回身份集合，再还原每条本地负 ID 和原坐标；同一 OSM 对象对应多个本地坐标时也分别保留本地身份。外部传入的任意正数身份不会被盲目转发。

**SQLite 不是可随意删除的缓存。** 丢失或回退映射库可能让新分配 ID 与 TeslaMate 已有地址冲突。使用 SQLite 在线 backup API，输出路径必须不存在：

```sh
docker compose -f compose.example.yaml exec -T amap-adapter python -m adapter.server --backup /data/adapter-snapshot.sqlite3
docker compose -f compose.example.yaml cp amap-adapter:/data/adapter-snapshot.sqlite3 ./adapter-snapshot.sqlite3
```

备份包含位置隐私，应受控保存；不要直接复制活动数据库文件。恢复时先停止 sidecar，恢复与 TeslaMate 数据一致的完整映射库，确认身份后再启动。`.osm.lock` 只保存限流时间，无需作为身份备份。

私人版本可能使用正数 hash，无法仅凭数值判断它是否为真实 OSM ID。旧地址身份导入、历史关联修复和 TeslaMate 数据库升级均属于独立迁移工作，需在恢复副本验证后另行执行。仅回退应用镜像不等于回滚已升级的数据库。

## 版本跟进与发布

构建流程与生产部署分开：

1. [Check upstream release](../.github/workflows/upstream-release.yml) 每周检查稳定 release，输出当前及建议 tag/commit；不修改 pin。
2. 人工审查上游变化后更新 `upstream.json` 和补丁，通过 PR 触发 [Validate and build](../.github/workflows/ci.yml)。
3. CI 通过 Python、严格补丁检查、ExUnit、两个镜像构建和非 root 容器健康检查后，才能进入可选发布步骤；冲突或失败即停止。
4. 仅在 `main` 手动运行工作流并勾选 `publish`，才发布已检查的镜像。版本标签为 `<upstream-tag>-amap-<完整仓库提交号>`；没有自动 `latest` / `stable` 提升。

发布目的地由工作流中的当前仓库名生成：

```text
ghcr.io/<owner>/<repository>-amap:<version>
ghcr.io/<owner>/<repository>-amap-adapter:<version>
```

这些是发布规则，不表示镜像已经发布。当前 CI 构建 `linux/amd64`；Mac ARM 可按本地构建命令生成对应镜像。定时检测和 main 手动发布在开发 PR 合并后生效；工作流不自动合并 PR 或部署生产。

## 来源与许可

官方 [TeslaMate](https://github.com/teslamate-org/teslamate) 的 [LICENSE](../LICENSE)、[NOTICE](../NOTICE)、[TRADEMARK.md](../TRADEMARK.md) 原样保留；代码按 AGPL-3.0-or-later 提供，修改说明见 [MODIFICATIONS.md](../MODIFICATIONS.md)。两个镜像保留各自代码许可，官方镜像构建继续保留其 NOTICE。

[高德逆地理编码文档](https://lbs.amap.com/api/webservice/guide/api/georegeo)、[Nominatim 使用政策](https://operations.osmfoundation.org/policies/nominatim/)与 [OpenStreetMap 数据许可](https://www.openstreetmap.org/copyright)分别约束对应服务和数据。
