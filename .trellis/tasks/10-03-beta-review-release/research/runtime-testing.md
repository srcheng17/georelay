# 构建后镜像测试研究

状态：上游运行契约研究；主应用启动部分现已由 main-image-smoke 实现并本地实证，adapter 镜像 suite/RPC 地址闭环已实现；法律/品牌门禁按后续main地址-only决定删除。下表记录补齐启动门禁之前的历史基线。2026-10-03 只读核查 `upstream.json` 固定的官方 commit `33d200b2fba9d5138803916a788cef5eae31b1aa`（v4.3.0）。

## 现有检查与缺口

| 依据 | 已有行为 | 与最终镜像的关系 |
| --- | --- | --- |
| `.github/workflows/ci.yml:46` | amd64/arm64 原生 runner | 新门禁应在两个架构各执行一次 |
| `.github/workflows/ci.yml:64` | 全部 Python unittest | 构建前测试 runner 上的源码 |
| `tests/test_adapter.py:103` | 34 项 adapter 测试（AST 方法计数） | 覆盖坐标/服务转换、永久身份、缓存、SQLite 迁移/备份、批量预算与失败处理 |
| `tests/test_adapter.py:665`、`:728`、`:745` | 真实本地 HTTP stub、slow-drip 超时、HTTP 契约/日志脱敏 | 无真实 Key、公共服务请求或车辆数据 |
| `scripts/test_upstream.sh:45`、`:68` | 隔离 Elixir/PostgreSQL，编译、格式检查、选定官方和补丁 ExUnit | 源码测试，不是最终 release 启动测试，也不是全量上游测试 |
| `patches/0001-nominatim-base-url.patch:144`、`patches/0002-refresh-address-fields.patch:157`、`:243` | 负数 signed bigint、刷新文本字段、保护历史身份及行程/充电引用、缺失身份失败 | Finch 被 mock；可复用其公共 fixture 与断言设计 |
| `.github/workflows/ci.yml:75` | 构建后架构、非 root、许可文件检查 | 真实最终镜像检查，应保留 |
| `.github/workflows/ci.yml:90` | 正常启动 adapter 并检查 `/health` | 仅本地 SQLite 就绪；未测最终 GeoRelay 启动/HTTP/地址闭环 |
| `.github/workflows/ci.yml:106` | `docker save` 保存已检查产物 | 新测试应放在保存前，发布继续复用相同镜像 |

目前仍无 beta 发布通道；已有共享 scripts/test_main_image.sh 启动入口，后续应扩展或复用它而非重新实现启动/清理。`docs/AMAP.md:138`—`:153` 已区分模拟源码测试与真实凭据/生产迁移的能力边界，后续文档沿用该边界。

## 最小复用：adapter 最终镜像运行 34 项现有测试

`adapter/Dockerfile:7`—`:15` 的工作目录是 `/app`，运行代码在 `/app/adapter`，Python 3.13 和 stdlib 已包含在镜像中。每个架构构建后执行：

```bash
docker run --rm --network none \
  --mount "type=bind,src=$PWD/tests,dst=/tests,readonly" \
  --entrypoint python georelay-adapter:checked \
  -m unittest discover -s /tests -p test_adapter.py -v
```

只挂测试目录，不挂宿主 `adapter/`，不将整个仓库挂到 `/app`，不更改镜像工作目录或增加 `PYTHONPATH`；否则会重新测试宿主源码。现有 suite 使用 `/tmp` 临时文件、loopback stub 和镜像内 `adapter.server`，`--network none` 仍允许容器 loopback，阻断公共请求。实现时核对 import 来源为 `/app/adapter/server.py`。保留现有正常 CMD 启动与 `/health` 检查，避免 override entrypoint 的 suite 遗漏启动路径。

## 固定官方 release 接口

以下通过固定 commit 的官方文件只读核查；以后升级 pin 时需重核：

- [官方 Dockerfile](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/Dockerfile)：builder `MIX_ENV=prod`、`mix release`；final Debian 镜像只复制 release，无源码/test/ExUnit。`WORKDIR /opt/app`，入口 `tini -- /bin/dash /entrypoint.sh`，CMD `bin/teslamate start`，端口 4000。
- [entrypoint.sh](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/entrypoint.sh)：先 `bin/teslamate eval "TeslaMate.Release.wait_for_database_and_migrate()"`，再执行 CMD。数据库等待无上游时间上限，测试必须自己设置有界等待。
- [runtime.exs](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/config/runtime.exs)：运行时需 `DATABASE_HOST`、`DATABASE_USER`、`DATABASE_PASS`、`DATABASE_NAME`；可设置 `DISABLE_MQTT=true`、`HTTP_BINDING_ADDRESS=0.0.0.0`、`ENCRYPTION_KEY`。使用明确的 CI 虚构 encryption key，避免启动生成并打印随机 key。
- 补丁设置 `NOMINATIM_BASE_URL=http://stub:8080`、`NOMINATIM_LOCAL_IDENTITIES_ONLY=true`；这是 compiled Finch 和地址刷新生产路径的配置。
- [router.ex](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate_web/router.ex) 与 [car_controller.ex](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate_web/controllers/car_controller.ex)：无 token 时 `/` 跳转 `/sign_in`；直接测实际 `/sign_in` 登录表单，不要要求首页直接 200。
- release 支持 `bin/teslamate rpc`；在运行容器执行 `Code.eval_file("/checks/runtime.exs")` 即可测试编译后的模块，无需将 ExUnit 加进发布镜像。

## 最小新增：GeoRelay 最终 release 运行检查

已有 test_main_image.sh 隔离 shell 入口负责默认 release 启动、迁移、登录 HTTP 与有界取消清理；仅补小型 Python stub/Elixir 检查文件。既有模式来自 `scripts/test_upstream.sh:25`—`:44` 的唯一资源名、trap 清理与数据库就绪等待。不给生产 Dockerfile 加测试依赖。

1. 构建完成后创建独立 `docker network create --internal`；在其中启动 `postgres:18-trixie`（与现有脚本一致）、tmpfs 数据目录和虚构 CI 密码，预建测试数据库。资源名包含 run/attempt/架构或随机值，所有容器均无 host port。
2. 用已构建 `georelay-adapter:checked` 的 Python 运行小型只读挂载 stub（override entrypoint，不改产品 server）。stub 按路径、语言和固定公共坐标返回 Nominatim JSON：`/reverse` 返回本地负数 node 身份；`/lookup` 返回刷新后的名称/road/house_number/raw。另提供确定性的失败和缺失身份场景，并验证 lookup 请求/语言及未走 reverse fallback。复用现有 fixture 的字段形状与虚构文本。
3. 正常运行 `georelay:checked` 的官方入口和 CMD，配置临时数据库、stub origin、local-only、禁用 MQTT、CI encryption key。独立网络阻断公网，无 token、车辆凭据或地图 Key。
4. 使用 Python probe 容器（仍可复用 adapter 镜像）轮询 HTTP 至有界超时，检查 `/sign_in` HTTP200、HTML类型、无redirect、实际token表单与有界body。这样证明入口迁移与完整release启动，不依赖品牌、favicon或定制法律端点。
5. 将小型 Elixir fixture 检查只读挂到 `/checks`，用 `docker exec <app> bin/teslamate rpc 'Code.eval_file("/checks/runtime.exs")'` 执行。用 pattern match/raise，而非 ExUnit；调用 compiled `Locations.find_address`，经过真实 Finch HTTP/stub 并在 PostgreSQL 保存负数身份。通过 `Locations.refresh_addresses` 验证 name/road/house_number/raw 更新，ID/osm_type/坐标保持；同批正数历史地址保持；行程/充电 address_id 引用保持。
6. stub 返回错误或缺失本地身份时，要求明确 `{:error, ...}`，原地址未覆盖、地址数量不增、不生成 Unknown、不触发 reverse fallback。不要以 `/health` 或 TCP 就绪代替这些断言。
7. 明确检查 RPC 失败退出码和成功标记，捕获容器提前退出/HTTP 超时；任一断言失败使本架构 build job 失败。正常结束及失败都清理 app/stub/db/probe、网络及临时卷；仅输出脱敏错误与合成 fixture 信息，不上传完整日志。

## 门禁与边界

- 源码检查 → 构建两镜像 → 每架构镜像测试 → 保存同一产物 → 两 package 发布与双架构索引验证 → 当前 PRD 定义的条件合并；失败通过 Bark 通知。用户最新要求已替换早期成功审阅通知方案，通知/合并仍属于父任务规划。
- 现有源码测试保留；runtime 补足包装、迁移、生产编译路径与跨容器 HTTP 契约。PG/stub/probe 仅 CI 临时资源，不接现有 Compose stack、host ports 或生产卷。
- 启动门禁已有本机原生 arm64 真实证据：HTTP 200、105 项迁移及故障/超时/TERM 零残留，完整 98 项与最终专项 9 项通过（见 ../../10-03-main-image-smoke/validation.md）。云端两架构、adapter 镜像 suite 和 release RPC 地址断言仍须实际验证；不得把上述启动证据扩写成全闭环已通过。
- 无真实地图服务、车辆登录、配额、生产数据升级/迁移验收；公开 fixture 和 CI stub 通过不能证明这些能力。

2026-10-03最终整合：用户明确回复“合并，验证”，已授权本次bootstrap分支/PR合入并验证GHCR。整合main c8a6e83（PR9）地址-only修改，保留共享prepare、两个地址补丁与原生Dockerfile；删除品牌词/法律端点额外门禁，以真实登录表单、迁移和compiled地址RPC验收。旧品牌镜像测试记录仅为历史结果；最终以本次云端运行结果为准。
