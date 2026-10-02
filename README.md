# 高德地址适配 · TeslaMate 社区修改源码

为个人自托管场景提供高德地址解析能力，基于官方 **TeslaMate v4.3.0** 维护小型源码补丁与独立适配服务。本仓库保存补丁、sidecar、测试和构建流程；完整 TeslaMate 源码在构建时从固定官方提交取得。

> This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

**当前状态：** 功能位于待合并的[开发 PR](https://github.com/srcheng17/teslamate/pull/1)，尚未部署生产，也未发布本修改版本的镜像。上游固定为 `v4.3.0` / `33d200b2fba9d5138803916a788cef5eae31b1aa`，以 [upstream.json](upstream.json) 为准。

[使用与配置](docs/AMAP.md) · [开发与构建](docs/AMAP.md#开发与构建) · [永久身份与备份](docs/AMAP.md#永久身份与备份) · [修改说明](MODIFICATIONS.md) · [官方文档](https://docs.teslamate.org/)

## 项目简介

[TeslaMate](https://github.com/teslamate-org/teslamate) 是用于 Tesla 车辆的自托管数据记录与分析工具。以下简介、官方功能及截图依据固定版本的[上游 README](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md) 整理：

- 使用 [Elixir](https://elixir-lang.org/) 编写。
- 车辆数据保存在 PostgreSQL。
- 通过 Grafana 展示和分析数据。
- 通过本地 [MQTT](https://en.wikipedia.org/wiki/MQTT) Broker 发布车辆数据。

官方项目建议从[官方仓库](https://github.com/teslamate-org/teslamate)与[官方文档](https://docs.teslamate.org/)获取正式版本。本仓库的社区修改内容、来源和重建方法见 [MODIFICATIONS.md](MODIFICATIONS.md)。

## 新增的高德地址能力

- **大陆高德、境外 OSM：** 独立服务提供 Nominatim 兼容的 `/reverse` 与 `/lookup`，保留官方地址读取链路。地区判断与公共 OSM 使用限制见[路由说明](docs/AMAP.md#路由与名称)。
- **保留地点名称：** 高德请求使用 `extensions=all`，优先首条 AOI 名称、再首条 POI 名称，缺失时回退到建筑、小区、道路和完整地址。
- **保留原始坐标和身份：** 仅高德查询临时转为 GCJ-02；返回值及存储保持 WGS84。独立 SQLite 保存永久负数身份，语言变化、缓存到期和重启均保持身份稳定。
- **保持小型修改：** TeslaMate 只增加 `NOMINATIM_BASE_URL` 配置补丁；适配逻辑使用 Python 标准库。构建校验固定上游提交，补丁或测试失败即停止。

```text
官方 TeslaMate + URL 补丁 → 私有网络中的 adapter → 高德 / 官方 Nominatim
                                      └→ SQLite 永久身份与响应缓存
```

这项能力改善**地址文字**。HedgieMate、Grafana 等客户端的底图、地图显示纠偏和刷新频率仍由客户端决定；不会将车辆轨迹写成 GCJ-02。历史私人版本的地址身份导入及数据库迁移仍需单独验证。

验证记录包含 **32 项 Python 测试、105 项上游 ExUnit 测试**及隔离容器联调。地点名称回归的同点样本已恢复原名称；样本结果不代表全库或全球地址准确率。参见[基础验收](.trellis/tasks/archive/2026-10/10-02-amap-mvp/validation.md)与[名称回归验收](.trellis/tasks/archive/2026-10/10-02-amap-poi-name/validation.md)。

## 文档

| 内容 | 入口 |
| --- | --- |
| 官方安装、使用与仪表盘 | [TeslaMate 官方文档](https://docs.teslamate.org/) |
| 适配器接口、配置与运行示例 | [高德地址适配指南](docs/AMAP.md) |
| 本地检查、固定版本构建与发布维护 | [开发与构建](docs/AMAP.md#开发与构建)、[版本跟进与发布](docs/AMAP.md#版本跟进与发布) |
| 永久身份、备份和历史兼容限制 | [永久身份与备份](docs/AMAP.md#永久身份与备份) |

## 官方功能

以下为官方 v4.3.0 的功能概览；本仓库通过固定官方源码构建保留这些能力。

### General · 通用功能

- 高精度行程记录。
- 尽快让车辆进入休眠，避免额外的待机耗电。
- 自动地址解析和自定义地理围栏。
- 通过 MQTT 集成 Home Assistant、Node-RED 和 Telegram。
- 同一 Tesla 账户支持多辆车辆。
- 充电费用记录。
- 从 TeslaFi 和 tesla-apiscraper 导入数据。
- 浅色、深色及跟随系统的主题模式。
- Web 界面支持包括简体中文、繁体中文在内的 19 种语言；缺失译文回退为英语。

### Dashboards · 仪表盘

下列链接指向官方仪表盘说明与示例截图。

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

## Screenshots · 官方截图

以下图片来自固定的官方 v4.3.0 源码，用于展示 TeslaMate Web 界面与内置仪表盘。更多图片见[官方截图文档](https://docs.teslamate.org/docs/screenshots/)。

![官方 TeslaMate Web 界面](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/web_interface.png)

![官方 TeslaMate 行程详情仪表盘](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/drive.png)

![官方 TeslaMate 电池健康仪表盘](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/battery-health.png)

## License · 许可与来源

TeslaMate 及本仓库代码按 **AGPL-3.0-or-later** 提供。上游 [LICENSE](LICENSE)、[NOTICE](NOTICE) 和 [TRADEMARK.md](TRADEMARK.md) 原样保留；完整许可、版权、附加条款及商标要求以这些文件为准。修改版本的对应源码与重建方式见 [MODIFICATIONS.md](MODIFICATIONS.md)。

高德服务与数据受其[服务文档及条款](https://lbs.amap.com/api/webservice/guide/api/georegeo)约束；OpenStreetMap 数据使用 [ODbL 许可](https://www.openstreetmap.org/copyright)。代码许可不替代上游服务或数据许可。

TeslaMate 是独立项目，与 Tesla, Inc. 无隶属、认可或赞助关系；相关商标归其权利人所有。向官方上游贡献时，请遵循[官方贡献说明](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md#license)，包括其 FLA/CLA 要求。

## Credits · 致谢

- TeslaMate 初始作者：[Adrian Kumpf](https://github.com/adriankumpf)。
- [TeslaMate 官方贡献者](https://github.com/teslamate-org/teslamate/graphs/contributors)。
- [本仓库修改与维护贡献者](https://github.com/srcheng17/teslamate/graphs/contributors)。
