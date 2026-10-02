# 修改版本与来源

本仓库是个人维护的 TeslaMate 高德地址适配版本，不是官方 TeslaMate 发布，也不代表 TeslaMate、高德或 Tesla。

- 官方来源：https://github.com/teslamate-org/teslamate
- 固定源码版本以 `upstream.json` 为准；修改位于 `patches/`，不存整份上游源码。
- 本项目新增独立 `adapter/`、NOMINATIM_BASE_URL 补丁、检查与构建流程。
- 上游 `LICENSE`、`NOTICE`、`TRADEMARK.md` 原样保留；原 Dockerfile 保留镜像中的 LICENSE/NOTICE。
- 本仓库代码按 AGPL-3.0-or-later 提供。AMap 服务及返回数据仍受其各自条款约束，不随代码许可改变。
- 修改版本的对应源码：本仓库 https://github.com/srcheng17/teslamate ，结合固定官方 commit 与本仓库补丁可重建。镜像标签包含上游版本与本仓库完整 commit；发布流程携带源码/修改版本 OCI 标签。

向其他使用者提供修改版本时，同时提供该版本对应源码的访问方式。当前 MVP 不执行生产上线或公开镜像发布。
