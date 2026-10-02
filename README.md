# TeslaMate 高德地址适配

基于官方稳定版的小型维护项目：**大陆地址使用高德，境外使用 OpenStreetMap/Nominatim**。官方 TeslaMate 只增加 geocoder URL 配置补丁，地址转换、缓存和身份映射由独立 Python 标准库 sidecar 完成。

本项目是个人修改版本，不是官方 TeslaMate 发布。当前固定 **v4.3.0**，commit `33d200b2fba9d5138803916a788cef5eae31b1aa`；来源以 [upstream.json](upstream.json) 为准，不在仓库存放整份上游源码。

## 范围

- 提供 `/reverse`、`/lookup`、`/health`；SQLite 永久负数身份、按语言分开的响应缓存；无真实 Key 的模拟与本地 HTTP 测试。
- URL 补丁同时修改 Geocoder 和专用 Finch pool，保留 size=3 与 proxy；官方默认仍为 OSM。
- PR 校验、固定版本构建、稳定 release 检测和手动版本镜像发布流程；不自动提升 stable，不自动部署。
- **不修改生产服务、PostgreSQL 或 Dockhand stack。** 旧私人版身份导入、数据库升级迁移、真实 Key 联调尚未执行。

这只改变地址文字来源。HedgieMate/Grafana 的底图、地图纠偏和刷新频率由客户端负责。数据库、轨迹、SQLite 和 adapter 返回值始终保留 **WGS84**；只有发给高德的查询坐标临时转成 GCJ-02，不会写回或造成客户端二次纠偏。

TeslaMate 在行程结束解析起终点、充电开始解析地址，并修复缺失地址；它不对每个 GPS 点进行逆向解析。

## 结构与路由

```text
固定官方 TeslaMate + URL 补丁
  → 私有 Docker 网络中的 adapter
    → 高德 regeo / 官方 Nominatim
    → 独立 SQLite 身份与缓存
```

境外不依赖高德海外权限。常见 GCJ-02 矩形只用于快速排除，不能当作国界：框外直接查询 OSM；框内先请求高德，仅接受明确的大陆地址。高德失败或无法确认地区时，用 OSM 的 `country_code` 和港澳 ISO 地区代码确认；仅明确非大陆才接受 OSM 结果，大陆仍报告原高德错误。首次判断可能请求两个服务，已确认的 OSM 来源会持久保存。

公共 Nominatim 需要标识调用者、缓存和限流。本服务将 OSM 请求串行化，每次完成后至少间隔一秒；仅运行一份共享本地数据卷的服务，不用于批量采集。地址数据保留 OSM attribution。参见 [Nominatim 使用政策](https://operations.osmfoundation.org/policies/nominatim/)。

## 配置

`NOMINATIM_BASE_URL` 是**本项目新增变量，官方镜像本身没有此能力**。补丁版 TeslaMate 可设置：

```dotenv
NOMINATIM_BASE_URL=http://amap-adapter:8080
```

只接受 HTTP/HTTPS origin，可含端口，不能包含账号、路径、query 或 fragment；末尾 `/` 会规范化。未设置时使用 `https://nominatim.openstreetmap.org`。`NOMINATIM_PROXY` 是 CONNECT proxy，不是 geocoder URL。

Sidecar 配置：

| 变量 | 默认值 / 用途 |
| --- | --- |
| `AMAP_KEY` | 高德 Web 服务 Key，只交给 sidecar |
| `AMAP_KEY_FILE` | 可替代 `AMAP_KEY`，两者不能同时设置；文件须让容器 UID 10001 可读 |
| `NOMINATIM_USER_AGENT` | 境外请求必填，包含应用名和实际联系方式；未配置时 OSM 请求返回 503 |
| `ADAPTER_DB` | `/data/adapter.sqlite3`，必须永久保存 |
| `CACHE_TTL_SECONDS` | `86400`，最大 31536000；只影响响应缓存 |
| `UPSTREAM_TIMEOUT_SECONDS` | 单次上游最多 `8` 秒，最大 20；无自动重试 |
| `LOOKUP_TIMEOUT_SECONDS` | 整批 lookup 最多 `20` 秒，最大 25 |

reverse 总预算为 `min(25, 2 × UPSTREAM_TIMEOUT_SECONDS + 1)` 秒，包含必要的地区确认；lookup 共用整批预算。响应体最多 1 MiB，lookup 最多 50 个本地身份。超时或上游错误返回明确失败，不合成永久 `Unknown`。`/health` 仅证明本地存储可用，不证明 Key、配额或外网正常。

## 开发与验证

无需真实 Key：

```sh
python3 -m unittest discover -s tests -v
git diff --check
python3 scripts/prepare_upstream.py /tmp/teslamate-amap-build
bash scripts/test_upstream.sh /tmp/teslamate-amap-build
docker build -t teslamate-amap:local /tmp/teslamate-amap-build
docker build -t amap-adapter:local adapter
```

准备目录必须不存在或为空。脚本核实 tag 解引用 commit，再严格应用补丁，任一步失败立即停止。上游测试脚本只创建独立 Elixir/PostgreSQL 容器、随机网络和临时存储，无 host port，退出时清理。它会执行官方编译、格式检查、原 Geocoder/HTTP 测试以及新增负数 ID 数据库兼容测试。

运行示例 sidecar 时，先复制 `.env.example` 为 `.env` 并按需填写，文件不提交 Git；健康检查无需 Key。配置了服务后，再使用 [compose.example.yaml](compose.example.yaml)：

```sh
docker compose -f compose.example.yaml config --quiet
docker compose -f compose.example.yaml up -d --build
docker compose -f compose.example.yaml exec -T amap-adapter python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/health").read().decode())'
```

示例不开放 host port，也不是生产 stack 替换文件。未来部署时，补丁版 TeslaMate 必须加入同一网络；普通 bridge 保留上游访问出口，不能将其设成阻断出口的 `internal: true`。

## 永久身份与备份

同一规范化原始 WGS84 坐标始终对应同一个负数 `osm_id`，`osm_type=node`。这属于适配器私有身份，不是真实 OSM 对象。重启、语言切换、缓存到期和文字刷新均不得改变身份。lookup 接受例如 `N-10001`，只返回请求的本地身份。

已成功从 OSM 获得的真实对象来源保存在 SQLite，供境外语言刷新批量调用官方 `/lookup`；结果按来源身份匹配，再还原本地负 ID 和原坐标，不能直接接收任意正数身份。私人版的正数 hash 与真实 OSM ID 无法仅凭数值区分，历史迁移需另行验证。

**SQLite 不是可随意删除的缓存目录。** 丢失或回退映射库可能让新分配 ID 与 TeslaMate 已有地址冲突。使用在线 backup API，输出路径必须不存在：

```sh
docker compose -f compose.example.yaml exec -T amap-adapter python -m adapter.server --backup /data/adapter-snapshot.sqlite3
docker compose -f compose.example.yaml cp amap-adapter:/data/adapter-snapshot.sqlite3 ./adapter-snapshot.sqlite3
```

备份包含位置隐私，需受控保存；不要直接复制活动数据库文件。恢复时先停 sidecar，恢复与 TeslaMate 数据一致的完整映射库，再验证身份后启动。`.osm.lock` 只保存限流时间，无需当作身份备份。此处只给出方法，本次没有备份或更改生产。

## GitHub 跟进

- `Check upstream release` 每周检测稳定 release，输出当前/建议 tag 和 commit，不改 pin、不创建部署。
- 人工审查新版变化后更新 `upstream.json` 和补丁，由 PR 触发 `Validate and build`。
- CI 必须通过 Python、严格补丁、ExUnit、两个镜像构建和非 root 容器健康检查；冲突或失败不发布。
- 仅 `main` 上手动运行并勾选 `publish` 才推送已经检查过的镜像。标签为 `<upstream-tag>-amap-<完整仓库提交号>`，无 `latest`/`stable`。
- 当前 CI 构建 `linux/amd64`；Mac ARM 可在本机按上述命令构建。定时检测和 main 手动发布须在 PR 合并后生效；本任务不自动合并或发布镜像。

## 来源与许可

官方 [TeslaMate](https://github.com/teslamate-org/teslamate) 的 [LICENSE](LICENSE)、[NOTICE](NOTICE)、[TRADEMARK.md](TRADEMARK.md) 原样保留。代码按 AGPL-3.0-or-later 提供；修改说明和对应源码见 [MODIFICATIONS.md](MODIFICATIONS.md)。官方镜像构建继续保留其许可文本，adapter 镜像也携带代码许可。

[高德 Web Service 文档](https://lbs.amap.com/api/webservice/guide/api/georegeo) 与 [OpenStreetMap 数据许可](https://www.openstreetmap.org/copyright) 分别约束上游服务和数据。高德本身存在海外服务；本项目按用户选择采用境外 OSM，并非声称高德没有海外能力。
