# GeoRelay 镜像名称与部署

核对上游 TRADEMARK.md 第 5 节后，用户明确确认沿用已公开的 `ghcr.io/srcheng17/georelay` 与 `ghcr.io/srcheng17/georelay-adapter`，以中性名称表示多地图支持。保留 GeoRelay 品牌及各 provider 配置。原始部署要求为先测试两个镜像，再切换 Dockhand TeslaMate；这一授权继续有效。

## 要求与验收

- 发布、保留规划和双语文档中的公开包名一致；仓库改名不隐式改变镜像包名，旧公开包不删除。
- 固定版本与 latest 沿用 georelay 版本前缀及双架构校验。
- 先备份、再用独立数据库副本验证；生产动作通过 Dockhand 原生 API 执行。
- 新分支完成本地、真实 CI 和独立审查，创建 PR 等待审阅。没有当前 PR 的明确合并授权，不合入 main。
- 测试、发布和实际部署分别记录；凭据、响应、运行配置和备份不提交 Git。
