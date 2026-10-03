# GeoRelay

[English](README.md) | 简体中文

自托管的行程与充电记录，支持高德、百度和 OpenStreetMap 地址解析。GeoRelay 从上游稳定版本构建修改版应用，通过独立适配器查询地点名称和地址。

> This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

[开始使用](#开始使用) · [功能](#功能) · [版本维护](#版本维护) · [文档](#文档)

## 开始使用

往现有 TeslaMate stack 添加 `georelay-adapter`，并将 TeslaMate 换成本项目的补丁镜像。两个镜像都支持 `linux/amd64` 和 `linux/arm64`。官方镜像不支持 `NOMINATIM_BASE_URL`。

应用镜像 `georelay` 和适配器镜像 `georelay-adapter` 已在 GHCR 公开发布，名称适用于所有支持的地址服务。选择 Release 中注明应用管理地址身份的配套版本；较早镜像使用不同协议。下面的片段默认使用 `latest` 镜像。需要固定版本时，从[应用镜像](https://github.com/users/srcheng17/packages/container/package/georelay)和[适配器镜像](https://github.com/users/srcheng17/packages/container/package/georelay-adapter)页面选择相同版本，设置为 `GEORELAY_VERSION`。

在现有 stack 的 `.env` 中设置 `AMAP_KEY` 和 `NOMINATIM_USER_AGENT`，格式参考 [.env.example](.env.example)。默认大陆使用高德 Web 服务，境外使用 OSM；User-Agent 需包含应用名和实际联系方式。大陆改用百度时，设置 `MAINLAND_PROVIDER=baidu`、`BAIDU_AK` 及其对应的 `BAIDU_SK`。

把下面的片段并入已有 Compose 配置，保留其他 TeslaMate 环境变量、数据库、MQTT、Grafana 服务以及原有卷。

```yaml
services:
  teslamate:
    image: ghcr.io/srcheng17/georelay:${GEORELAY_VERSION:-latest}
    environment:
      NOMINATIM_BASE_URL: http://georelay-adapter:8080
      GEORELAY_ADDRESS_MODE: application
      # Keep your other TeslaMate settings here.
  georelay-adapter:
    image: ghcr.io/srcheng17/georelay-adapter:${GEORELAY_VERSION:-latest}
    restart: unless-stopped
    environment:
      ADAPTER_CACHE_DB: /data/cache.sqlite3
      GEOCODER_PROVIDER: "${GEOCODER_PROVIDER:-auto}"
      MAINLAND_PROVIDER: "${MAINLAND_PROVIDER:-amap}"
      AMAP_API_REGION: "${AMAP_API_REGION:-mainland}"
      AMAP_KEY: "${AMAP_KEY:-}"
      BAIDU_AK: "${BAIDU_AK:-}"
      BAIDU_SK: "${BAIDU_SK:-}"
      NOMINATIM_USER_AGENT: "${NOMINATIM_USER_AGENT:?Set NOMINATIM_USER_AGENT in .env}"
    volumes:
      - amap-data:/data
    read_only: true
    tmpfs:
      - /tmp:size=16m,mode=1777
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
volumes:
  amap-data:
```

Compose 默认网络可以让两个服务互通。如果 TeslaMate 使用自定义网络，把适配器加入同一网络，并保留访问地址服务的外网出口。适配器无需映射主机端口。

永久地址编号、原坐标和供应商来源保存在 PostgreSQL；适配器卷只保留可丢弃缓存与限流状态。启用解析前先完成[初始化或迁移](#已有地址与备份)，升级时保留原卷以便封存旧身份文件。其他选项见[配置指南](docs/AMAP.md#配置)。

发布新的 `latest` 不会更新运行中的容器。需要升级时，先备份 TeslaMate 数据库并完成所需身份迁移，再在 stack 目录执行：

```sh
docker compose pull teslamate georelay-adapter
docker compose up -d teslamate georelay-adapter
```

<details>
<summary>从源码构建镜像</summary>

需要本地构建时，在仓库根目录执行以下命令，并将上面的两个镜像地址改为 `georelay:local` 和 `georelay-adapter:local`。目标目录 `/tmp/georelay-build` 必须不存在或为空。

```sh
python3 scripts/prepare_upstream.py /tmp/georelay-build
docker build -t georelay:local /tmp/georelay-build
docker build -t georelay-adapter:local adapter
```

</details>

### 已有地址与备份

应用在 PostgreSQL 管理稳定负数地址编号，每次向适配器发送编号、精确 WGS84 坐标和可信来源。适配器不持有数据库凭据；删除或重建其缓存不会改变永久地址。历史正数身份保留，在本地地址刷新时跳过。

从未使用旧 SQLite 身份库的新安装，启动配套镜像后显式初始化：

```sh
docker compose exec -T teslamate bin/teslamate rpc 'IO.inspect(TeslaMate.Locations.LocalIdentities.initialize_fresh(fresh_install: true))'
docker compose exec -T teslamate bin/teslamate rpc 'IO.inspect(TeslaMate.Locations.LocalIdentities.initialize_fresh(apply: true, fresh_install: true))'
```

第一条只审计，不写入。PostgreSQL 暂无地址不能证明是新安装；已有环境须先[审计并导入旧身份库](docs/AMAP.md#永久身份与备份)。两个镜像必须配套升级；初始化或导入未完成时，应用拒绝地址解析。

缓存到期只刷新适配器响应；应用切换地址语言时显式刷新已有文字，保留编号、坐标和行程/充电关联。高德、百度使用服务默认语言，英语请求也可能得到中文。

永久数据以 PostgreSQL 备份为准。旧 SQLite 快照作为迁移及回滚档案保留，新缓存无需与数据库配套恢复。新模式分配编号后，不能只降级镜像回到旧身份库；匹配备份的回滚边界见迁移指南。

## 功能

默认中国大陆使用高德，境外使用 OpenStreetMap。设置 `MAINLAND_PROVIDER=baidu` 可将大陆服务改为百度；`GEOCODER_PROVIDER=amap|baidu|osm` 可固定使用一个服务。版本化 POST 接口支持通过 provider 字段覆盖单次请求，TeslaMate 使用配置的默认策略。

返回结果包含地点名称以及省市区、道路等地址信息。切换服务保留原地址身份和坐标；百度海外解析需要对应权限；高德海外服务需显式设置 `GEOCODER_PROVIDER=amap`、`AMAP_API_REGION=global` 并提供该服务 Key。默认高德配置仅接受大陆结果，自动策略的境外地址使用 OSM，地区判断与名称处理见[路由说明](docs/AMAP.md#路由与名称)。

存储和响应中的坐标保持 WGS84，高德大陆查询临时转换为 GCJ-02，百度直接接收 WGS84。地址解析不改变 Web 界面的底图。行程、充电记录和地址仍由 TeslaMate 管理。

## 版本维护

项目每六小时检查官方稳定 release，并创建固定 tag 和 commit 的更新 PR。同仓 PR 与受控分支发布先经过原生 amd64/arm64 测试，包括镜像内 adapter 测试和应用启动、迁移、地址契约，再生成 beta 镜像；beta 不更新 `latest`。上游名称、翻译、资源、法律文本和 Dockerfile 保持原样，准备过程只应用地址补丁；补丁冲突或检查失败停止发布。

只有成功 beta 仍对应当前 PR commit、main 基线有效且分支保护允许时，发布控制器才自动合并，并显式触发 main 构建，发布正式版本与 `latest`。main 的镜像相关改动也发布已检查镜像；README、使用指南、agent 指令、Trellis 元数据和 Paseo 设置走轻量检查。成功、轻量检查和 check-only 不通知；镜像构建、测试、合并或发布失败时，通过仓库配置的 Actions Secret `BARK_URL` 发 Bark。控制器首次经过审阅合入 main 后，自动流程才会生效。

每组经验证的双镜像有对应 [GitHub Release](https://github.com/srcheng17/georelay/releases)，包含本项目可读更新、精确镜像 digest、源码和上游版本。自动跟进显示 TeslaMate 旧版本 → 新版本及官方变更链接；beta 标记为预发布。缺失说明可单独补录，无需重建镜像。固定镜像发布和浮动标签结果分别记录，浮动更新失败仍使流程失败。

两镜像使用相同的上游版本和源码 commit 标签；PR 浮动 beta 别名为 `beta-pr-N`，正式 `latest` 跟随 main 已审阅 pin。发布镜像不会更新运行服务。每周保留 `latest` 和最近 10 组完整正式版本及其架构镜像；beta 和其他未知记录继续受保护，beta 自动清理延期。配置、版本选择与维护见[版本跟进与发布](docs/AMAP.md#版本跟进与发布)。

## 文档

- [地址适配指南](docs/AMAP.md)：配置、接口、构建和备份。
- [TeslaMate 官方文档](https://docs.teslamate.org/)：安装与日常使用。
- [源码与修改说明](MODIFICATIONS.md)：本仓库的修改范围和重建方式。

## 许可与来源

TeslaMate 及本仓库代码采用 AGPL-3.0-or-later。上游 [LICENSE](LICENSE)、[NOTICE](NOTICE) 和 [TRADEMARK.md](TRADEMARK.md) 原样保留，完整许可、版权、附加条款及商标要求以这些文件为准。修改版本的对应源码与重建方式见 [MODIFICATIONS.md](MODIFICATIONS.md)。

高德、百度服务与数据分别受[高德](https://lbs.amap.com/api/webservice/guide/api/georegeo)和[百度](https://lbs.baidu.com/faq/api?title=webapi/guide/webservice-geocoding-abroad-base)的文档及条款约束；OpenStreetMap 数据使用 [ODbL 许可](https://www.openstreetmap.org/copyright)。代码许可不替代上游服务或数据许可。

TeslaMate 是独立项目，与 Tesla, Inc. 无隶属、认可或赞助关系；相关商标归其权利人所有。向官方上游贡献时，请遵循[官方贡献说明](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md#license)，包括其 FLA/CLA 要求。

## 致谢

- TeslaMate 初始作者：[Adrian Kumpf](https://github.com/adriankumpf)。
- [TeslaMate 官方贡献者](https://github.com/teslamate-org/teslamate/graphs/contributors)。
- [本仓库修改与维护贡献者](https://github.com/srcheng17/georelay/graphs/contributors)。
