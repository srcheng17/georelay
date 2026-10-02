# TeslaMate 地址适配

[English](README.md) | 简体中文

为自托管的 [TeslaMate](https://github.com/teslamate-org/teslamate) 增加高德、百度和 OpenStreetMap 地址解析，用于行程和充电记录的地点名称与地址。本仓库维护源码补丁、独立适配器和构建流程。

> This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

[开始使用](#开始使用) · [功能](#功能) · [截图](#截图) · [版本维护](#版本维护) · [文档](#文档)

## 开始使用

往现有 TeslaMate stack 添加 `amap-adapter`，并将 TeslaMate 换成本项目的补丁镜像。两个镜像都支持 `linux/amd64` 和 `linux/arm64`。官方镜像不支持 `NOMINATIM_BASE_URL`。

下面的片段默认使用已发布的 `latest` 镜像。需要固定版本时，从 [TeslaMate 镜像](https://github.com/users/srcheng17/packages/container/package/teslamate-amap)和[适配器镜像](https://github.com/users/srcheng17/packages/container/package/teslamate-amap-adapter)页面选择相同版本，设置为 `TESLAMATE_AMAP_VERSION`。

在现有 stack 的 `.env` 中设置 `AMAP_KEY` 和 `NOMINATIM_USER_AGENT`，格式参考 [.env.example](.env.example)。默认大陆使用高德 Web 服务，境外使用 OSM；User-Agent 需包含应用名和实际联系方式。大陆改用百度时，设置 `MAINLAND_PROVIDER=baidu`、`BAIDU_AK` 及其对应的 `BAIDU_SK`。

把下面的片段并入已有 Compose 配置，保留其他 TeslaMate 环境变量、数据库、MQTT、Grafana 服务以及原有卷。

```yaml
services:
  teslamate:
    image: ghcr.io/srcheng17/teslamate-amap:${TESLAMATE_AMAP_VERSION:-latest}
    environment:
      NOMINATIM_BASE_URL: http://amap-adapter:8080
      # Keep your other TeslaMate settings here.
  amap-adapter:
    image: ghcr.io/srcheng17/teslamate-amap-adapter:${TESLAMATE_AMAP_VERSION:-latest}
    restart: unless-stopped
    environment:
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

重启和升级时保留 `amap-data`，其中存有永久地址身份和响应缓存。替换现有环境前，请阅读[备份与旧地址兼容说明](docs/AMAP.md#永久身份与备份)。其他选项见[配置指南](docs/AMAP.md#配置)。

发布新的 `latest` 不会更新运行中的容器。需要升级时，先备份 TeslaMate 数据库和适配器数据，再在 stack 目录执行：

```sh
docker compose pull teslamate amap-adapter
docker compose up -d teslamate amap-adapter
```

<details>
<summary>从源码构建镜像</summary>

需要本地构建时，在仓库根目录执行以下命令，并将上面的两个镜像地址改为 `teslamate-amap:local` 和 `amap-adapter:local`。目标目录 `/tmp/teslamate-amap-build` 必须不存在或为空。

```sh
python3 scripts/prepare_upstream.py /tmp/teslamate-amap-build
docker build -t teslamate-amap:local /tmp/teslamate-amap-build
docker build -t amap-adapter:local adapter
```

</details>

## 功能

默认中国大陆使用高德，境外使用 OpenStreetMap。设置 `MAINLAND_PROVIDER=baidu` 可将大陆服务改为百度；`GEOCODER_PROVIDER=amap|baidu|osm` 可固定使用一个服务。`/reverse` 和 `/lookup` 支持 `provider=amap|baidu|osm` 覆盖单次请求，TeslaMate 使用配置的默认策略。

返回结果包含地点名称以及省市区、道路等地址信息。切换服务保留原地址身份和坐标；百度海外解析需要对应权限；高德海外服务需显式设置 `GEOCODER_PROVIDER=amap`、`AMAP_API_REGION=global` 并提供该服务 Key。默认高德配置仅接受大陆结果，自动策略的境外地址使用 OSM，地区判断与名称处理见[路由说明](docs/AMAP.md#路由与名称)。

存储和响应中的坐标保持 WGS84，高德大陆查询临时转换为 GCJ-02，百度直接接收 WGS84。地址解析不改变 Web 界面的底图。行程、充电记录和地址仍由 TeslaMate 管理。

TeslaMate 使用 [Elixir](https://elixir-lang.org/) 编写，将车辆数据保存在 PostgreSQL，通过 Grafana 展示和分析数据，并向本地 [MQTT](https://en.wikipedia.org/wiki/MQTT) Broker 发布车辆数据。下面的功能介绍来自[官方 README](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md)。

<details>
<summary>通用功能</summary>

- 高精度行程记录。
- 使车辆尽早进入休眠，避免额外的待机耗电。
- 自动地址解析和自定义地理围栏。
- 通过 MQTT 集成 Home Assistant、Node-RED 和 Telegram。
- 同一 Tesla 账户支持多辆车。
- 充电费用记录。
- 从 TeslaFi 和 tesla-apiscraper 导入数据。
- 浅色、深色及跟随系统的主题模式。
- Web 界面支持简体中文、繁体中文等 19 种语言，缺失译文回退为英语。

</details>

<details>
<summary>内置仪表盘</summary>

点击面板名称可查看官方文档中的说明与截图。

- [电池健康](https://docs.teslamate.org/docs/screenshots/#battery-health)
- [电量](https://docs.teslamate.org/docs/screenshots/#charge-level)
- [充电记录](https://docs.teslamate.org/docs/screenshots/#charges)
- [充电详情](https://docs.teslamate.org/docs/screenshots/#charge-details)
- [充电统计](https://docs.teslamate.org/docs/screenshots/#charging-stats)
- [数据库信息](https://docs.teslamate.org/docs/screenshots/#database-information)
- [行程统计](https://docs.teslamate.org/docs/screenshots/#drive-stats)
- [行程记录](https://docs.teslamate.org/docs/screenshots/#drives)
- [行程详情](https://docs.teslamate.org/docs/screenshots/#drive-details)
- [效率与能耗](https://docs.teslamate.org/docs/screenshots/#efficiency)
- [地点与地址](https://docs.teslamate.org/docs/screenshots/#location-addresses)
- [里程](https://docs.teslamate.org/docs/screenshots/#mileage)
- [概览](https://docs.teslamate.org/docs/screenshots/#overview)
- [预计续航与电池衰减](https://docs.teslamate.org/docs/screenshots/#projected-range)
- [车辆在线与休眠状态](https://docs.teslamate.org/docs/screenshots/#states)
- [综合统计](https://docs.teslamate.org/docs/screenshots/#statistics)
- [温度](https://docs.teslamate.org/docs/screenshots/#temperatures)
- [时间线](https://docs.teslamate.org/docs/screenshots/#timeline)
- [旅程](https://docs.teslamate.org/docs/screenshots/#trip)
- [车辆软件更新](https://docs.teslamate.org/docs/screenshots/#updates)
- [待机耗电](https://docs.teslamate.org/docs/screenshots/#vampire-drain)
- [历史行驶地图](https://docs.teslamate.org/docs/screenshots/#visited-lifetime-driving-map)

</details>

## 截图

以下是官方 TeslaMate 界面和仪表盘的截图，更多示例见[官方截图文档](https://docs.teslamate.org/docs/screenshots/)。

![官方 TeslaMate Web 界面](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/web_interface.png)

<details>
<summary>行程详情与电池健康</summary>

![官方 TeslaMate 行程详情仪表盘](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/drive.png)

![官方 TeslaMate 电池健康仪表盘](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/battery-health.png)

</details>

## 版本维护

项目每六小时检查官方稳定 release。发现新版本后，自动在更新 PR 中固定 tag 和 commit，应用补丁，在两个 CPU 架构上运行测试与构建。全部通过后发布新的 GHCR 版本镜像，两个版本索引验证通过后再更新 `latest`；补丁冲突或检查失败会停止发布。

本仓库 `main` 上影响镜像的改动也会构建并发布已检查镜像。文档、agent 指令、Trellis 元数据和 Paseo 设置仅运行轻量检查；其他改动运行完整双架构验证。手动验证始终执行完整构建。版本标签包含上游版本和源码 commit，`latest` 跟随验证通过的版本。工作流不自动合并 PR，也不更新正在运行的服务。

每周清理保留 `latest` 和最近 10 组完整版本，以及它们引用的架构镜像。不完整或无法识别的记录保留待复核。需要长期拉取的旧版本请自行镜像保存。版本选择、清理预览与维护见[版本跟进与发布](docs/AMAP.md#版本跟进与发布)。

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
- [本仓库修改与维护贡献者](https://github.com/srcheng17/teslamate/graphs/contributors)。
