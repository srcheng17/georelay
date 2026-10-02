# GeoRelay geocoding adapter / 独立地址适配服务

This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

This independently maintained GeoRelay companion service is licensed under AGPL-3.0-or-later; see LICENSE in this directory. Provider services and returned data remain subject to their own terms.

Modification dates / 修改日期：

- 2026-10-02: Added a Python standard-library AMap/OSM adapter with permanent local identities, SQLite caching and backup; preserved AMap place names and added configurable AMap/Baidu/OSM providers.
- 2026-10-03: Local lookup skips historical positive identities and refreshes mainland batches with bounded concurrency while preserving local identity, request order and the batch deadline. Renamed the distributed service to GeoRelay and added this dated modification notice to the image.

Corresponding Source: https://github.com/srcheng17/georelay. The image's `org.opencontainers.image.revision` identifies the exact commit: open `https://github.com/srcheng17/georelay/tree/<revision>` and use `adapter/` and its build scripts. The `org.opencontainers.image.source` label links to the source repository. 镜像标签保留本仓库完整 commit；按该 commit 获取对应源码与构建脚本。
