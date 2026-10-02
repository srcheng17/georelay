# GeoRelay modified version and source / 修改版本与来源

GeoRelay is a modified version maintained independently of the official TeslaMate project.

This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

GeoRelay 是个人维护的 TeslaMate 修改版本，不是官方 TeslaMate 发布，也不代表 TeslaMate、高德、百度或 Tesla。

- 官方来源：https://github.com/teslamate-org/teslamate
- 固定源码版本以 `upstream.json` 为准；修改位于 `patches/`，不存整份上游源码。
- 本项目新增独立 `adapter/`、NOMINATIM_BASE_URL 补丁、检查与构建流程。
- 上游 `LICENSE`、`NOTICE`、`TRADEMARK.md` 原样保留；原 Dockerfile 保留镜像中的 LICENSE/NOTICE。
- 本仓库代码按 AGPL-3.0-or-later 提供。AMap、百度及 OSM 服务和返回数据仍受其各自条款约束，不随代码许可改变。
- 修改版本的对应源码：本仓库 https://github.com/srcheng17/georelay ，结合固定官方 commit 与本仓库补丁可重建。镜像标签包含上游版本与本仓库完整 commit；发布流程携带源码/修改版本 OCI 标签。

Modification dates / 修改日期：

- 2026-10-02: Added the independent AMap/OSM geocoding adapter and configurable `NOMINATIM_BASE_URL` with shared Geocoder/Finch validation; added AMap place-name selection and configurable AMap/Baidu/OSM providers.
- 2026-10-03: Explicit address refresh also updates place name, road, house number and raw address fields while preserving identity and coordinates. `NOMINATIM_LOCAL_IDENTITIES_ONLY=true` skips historical positive identities during refresh; the default `false` retains the upstream reverse fallback. Local lookup refreshes mainland batches with bounded concurrency. Preparation requires byte-identical reviewed upstream legal files; both images include dated modification notices. Renamed the distributed application to GeoRelay with a plain wordmark, neutral favicon, prominent disclaimer and corresponding-source link; removed upstream logos and app icons while preserving legal credits and compatibility identifiers.

Corresponding Source: https://github.com/srcheng17/georelay. The image's `org.opencontainers.image.revision` identifies the exact commit: open `https://github.com/srcheng17/georelay/tree/<revision>`. That commit's `upstream.json`, `patches/`, `adapter/` and build scripts provide the fixed official source revision and changes needed to rebuild this version. The `org.opencontainers.image.source` label links to the source repository.

向其他使用者提供修改版本时，同时提供该版本对应源码的访问方式。公开镜像同时提供对应源码 commit；构建与发布不执行生产部署。
