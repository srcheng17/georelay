# 验证记录

2026-10-02。自动构建和发布范围离线验证完成；真实双架构发布结果见下方 2026-10-03 续验证。

- 独立 reviewer 核对受控 pin-only 分支、main 单父提交、双架构 verify 汇总、从测试产物直接发布以及移动 tag 拦截。
- 19 项 release/updater/publish 检查通过；全仓合并供应商改动后 55 项 Python 检查通过。
- 移动 tag 与 Docker UID 执行失败/空输出/非数字的回归先复现旧失败，再验证修复。
- Bash、actionlint v1.7.12、Python 语法、git diff --check 通过。
- main 保护实际回读：verify、strict、PR required、管理员适用、禁止强推。Actions PR 创建权限已按授权开启，工作流默认 read。

两 package 不具备跨包事务。实际发布后必须分别核对两个索引及匿名拉取；只完成架构 push 或首个索引不能称双镜像发布完成。不部署生产。

## 2026-10-03 发布验收（Asia/Shanghai）

- [PR #1](https://github.com/srcheng17/teslamate/pull/1) 已按保护流程合并，镜像源码 commit 为 `8f4efa1df503d5a25540d9185fb19ddcbd949d32`。
- [PR CI 37029365291](https://github.com/srcheng17/teslamate/actions/runs/37029365291)：amd64、arm64 build 和 verify 成功；publish 因 PR 事件条件跳过，符合设计。
- [main CI 37029960665](https://github.com/srcheng17/teslamate/actions/runs/37029960665)：amd64、arm64 build、verify、publish 全部成功，从已测试产物发布两个版本镜像。
- [updater 37030399601](https://github.com/srcheng17/teslamate/actions/runs/37030399601)：运行成功，artifact 返回 `status=current`。当前与检测到的官方稳定版均为 `v4.3.0`，commit `33d200b2fba9d5138803916a788cef5eae31b1aa`；本次无需创建更新 PR 或触发新版本构建。未来新稳定版的 PR/dispatch 路径由模拟测试证明，本次现场验证的是相同版本 noop。

两个 package 的新鲜浏览器页面均显示 Public。匿名 GHCR manifest 查询确认各索引恰含 `linux/amd64` 和 `linux/arm64`；使用无 auth、无 credential helper 的空临时 Docker config，四个 child manifest 均实际拉取成功，本地镜像架构及 OCI 标签回读一致。

共同版本为 `v4.3.0-amap-8f4efa1df503d5a25540d9185fb19ddcbd949d32`。四个镜像配置的 OCI 标签均已核对：

- `org.opencontainers.image.source=https://github.com/srcheng17/teslamate`
- `org.opencontainers.image.revision=8f4efa1df503d5a25540d9185fb19ddcbd949d32`
- `org.opencontainers.image.version=v4.3.0-amap-8f4efa1df503d5a25540d9185fb19ddcbd949d32`

| Package | 版本索引 digest |
| --- | --- |
| `ghcr.io/srcheng17/teslamate-amap` | `sha256:e68b40648669404f4e4fadf239466fc06cbb215b739fee585b19f2232dedfd97` |
| `ghcr.io/srcheng17/teslamate-amap-adapter` | `sha256:565c4770b43aca7fddba38d33a7f6ec73804d4552cc2712b2ad2173b9764e93a` |

| Package | 架构 | Child manifest digest |
| --- | --- | --- |
| `teslamate-amap` | `linux/amd64` | `sha256:af5eaab055d5c4f418cf39305493b6e61ca33ec7c747a8a1709caf4ff8923a88` |
| `teslamate-amap` | `linux/arm64` | `sha256:4656ee0d292a14b87c449bfd7498df0a7f04f531f2109564f3cdd17875d9e8a5` |
| `teslamate-amap-adapter` | `linux/amd64` | `sha256:9080172d6edec37d305e439c51df1aafc66525e23e86a2aa7152a2642e2aaf1b` |
| `teslamate-amap-adapter` | `linux/arm64` | `sha256:d4f7ec917da7388fffb31a8681f9c25b28676f9e304fe3c2de085e520fa44a5b` |

验证用镜像 references 已清理。以上只构建、发布与检查版本镜像，未部署生产、修改生产数据库或 Dockhand stack。
