# TeslaMate 高德地址适配

为自托管的 [TeslaMate](https://github.com/teslamate-org/teslamate) 增加高德地址解析，让行程和充电记录显示高德提供的地点名称与地址。本仓库维护源码补丁、独立适配器和构建流程。

> This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

## 高德地址解析

中国大陆使用高德逆地理编码，境外使用 OpenStreetMap。返回结果包含地点名称以及省市区、道路等地址信息，地区判断与名称处理见[路由说明](docs/AMAP.md#路由与名称)。

车辆坐标保持 WGS84，仅查询高德时临时转换为 GCJ-02。TeslaMate 继续负责行程、充电记录和地址入库，Grafana、HedgieMate 等客户端沿用原有读取方式。底图选择和地图显示纠偏由客户端负责。

## 使用

需要运行本仓库构建的补丁版 TeslaMate 和高德适配器。官方镜像不支持本项目新增的 `NOMINATIM_BASE_URL`。

1. 按[源码构建步骤](docs/AMAP.md#开发与构建)生成 TeslaMate 和适配器镜像。
2. 参照[配置指南](docs/AMAP.md#配置)设置高德 Web 服务 Key 和 OSM 调用者标识，运行适配器。
3. 将两个服务接入同一个 Docker 网络，通过 `NOMINATIM_BASE_URL` 把 TeslaMate 的地址请求指向适配器。

适配器的数据卷需要持久保存，备份方法与旧地址兼容范围见[永久身份与备份](docs/AMAP.md#永久身份与备份)。TeslaMate 的常规安装和使用方式见[官方文档](https://docs.teslamate.org/)。

## 官方功能

TeslaMate 使用 [Elixir](https://elixir-lang.org/) 编写，将车辆数据保存在 PostgreSQL，通过 Grafana 展示和分析数据，并向本地 [MQTT](https://en.wikipedia.org/wiki/MQTT) Broker 发布车辆数据。以下功能介绍与截图来自[官方 README](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md)。

### 通用功能

- 高精度行程记录。
- 使车辆尽早进入休眠，避免额外的待机耗电。
- 自动地址解析和自定义地理围栏。
- 通过 MQTT 集成 Home Assistant、Node-RED 和 Telegram。
- 同一 Tesla 账户支持多辆车。
- 充电费用记录。
- 从 TeslaFi 和 tesla-apiscraper 导入数据。
- 浅色、深色及跟随系统的主题模式。
- Web 界面支持简体中文、繁体中文等 19 种语言，缺失译文回退为英语。

### 仪表盘

点击面板名称可查看官方文档中的说明与截图。

| 面板 | 面板 |
| --- | --- |
| [电池健康](https://docs.teslamate.org/docs/screenshots/#battery-health) | [电量](https://docs.teslamate.org/docs/screenshots/#charge-level) |
| [充电记录](https://docs.teslamate.org/docs/screenshots/#charges) | [充电详情](https://docs.teslamate.org/docs/screenshots/#charge-details) |
| [充电统计](https://docs.teslamate.org/docs/screenshots/#charging-stats) | [数据库信息](https://docs.teslamate.org/docs/screenshots/#database-information) |
| [行程统计](https://docs.teslamate.org/docs/screenshots/#drive-stats) | [行程记录](https://docs.teslamate.org/docs/screenshots/#drives) |
| [行程详情](https://docs.teslamate.org/docs/screenshots/#drive-details) | [效率与能耗](https://docs.teslamate.org/docs/screenshots/#efficiency) |
| [地点与地址](https://docs.teslamate.org/docs/screenshots/#location-addresses) | [里程](https://docs.teslamate.org/docs/screenshots/#mileage) |
| [概览](https://docs.teslamate.org/docs/screenshots/#overview) | [预计续航与电池衰减](https://docs.teslamate.org/docs/screenshots/#projected-range) |
| [车辆在线与休眠状态](https://docs.teslamate.org/docs/screenshots/#states) | [综合统计](https://docs.teslamate.org/docs/screenshots/#statistics) |
| [温度](https://docs.teslamate.org/docs/screenshots/#temperatures) | [时间线](https://docs.teslamate.org/docs/screenshots/#timeline) |
| [旅程](https://docs.teslamate.org/docs/screenshots/#trip) | [车辆软件更新](https://docs.teslamate.org/docs/screenshots/#updates) |
| [待机耗电](https://docs.teslamate.org/docs/screenshots/#vampire-drain) | [历史行驶地图](https://docs.teslamate.org/docs/screenshots/#visited-lifetime-driving-map) |

### 截图

TeslaMate Web 界面、行程详情和电池健康面板。更多图片见[官方截图文档](https://docs.teslamate.org/docs/screenshots/)。

![官方 TeslaMate Web 界面](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/web_interface.png)

![官方 TeslaMate 行程详情仪表盘](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/drive.png)

![官方 TeslaMate 电池健康仪表盘](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/battery-health.png)

## 版本维护

项目跟进官方稳定版，当前构建使用的版本记录在 [upstream.json](upstream.json)。构建时从官方仓库取得该版本的源码，再应用本仓库的补丁。

每周定时检查上游新 release。维护者审查变化并更新版本配置与补丁后，CI 自动运行检查并构建 TeslaMate 和适配器镜像；补丁冲突或测试失败会中止构建。镜像发布需要在 `main` 手动触发，工作流不自动部署服务。具体步骤见[版本跟进与发布](docs/AMAP.md#版本跟进与发布)。

## 许可与来源

TeslaMate 及本仓库代码采用 AGPL-3.0-or-later。上游 [LICENSE](LICENSE)、[NOTICE](NOTICE) 和 [TRADEMARK.md](TRADEMARK.md) 原样保留，完整许可、版权、附加条款及商标要求以这些文件为准。修改版本的对应源码与重建方式见 [MODIFICATIONS.md](MODIFICATIONS.md)。

高德服务与数据受其[服务文档及条款](https://lbs.amap.com/api/webservice/guide/api/georegeo)约束；OpenStreetMap 数据使用 [ODbL 许可](https://www.openstreetmap.org/copyright)。代码许可不替代上游服务或数据许可。

TeslaMate 是独立项目，与 Tesla, Inc. 无隶属、认可或赞助关系；相关商标归其权利人所有。向官方上游贡献时，请遵循[官方贡献说明](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md#license)，包括其 FLA/CLA 要求。

## 致谢

- TeslaMate 初始作者：[Adrian Kumpf](https://github.com/adriankumpf)。
- [TeslaMate 官方贡献者](https://github.com/teslamate-org/teslamate/graphs/contributors)。
- [本仓库修改与维护贡献者](https://github.com/srcheng17/teslamate/graphs/contributors)。
