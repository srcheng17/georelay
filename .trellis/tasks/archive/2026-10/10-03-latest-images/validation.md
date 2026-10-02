# 验证记录

2026-10-03。仅开发与镜像发布，不部署生产。

- 全仓标准库 unittest：62 项，41.090 秒，OK；含 13 项执行真实发布 shell 的回归测试。
- 独立 reviewer 全范围审查无阻塞；最终 Trellis checker 阅读任务及 9 个变更文件，未发现需要修改的问题。
- actionlint v1.7.12、2 个 Bash 脚本语法、10 个 Python AST、git diff --check 均通过。
- 两版 README YAML 字节一致；假 stack 的 Compose config 合并验证默认/空值 latest 及固定版本覆盖，保留原环境、网络、卷，无 host port；49 个本地链接与锚点通过。
- 正常推广复用双架构版本索引的精确 digest；故障覆盖两包版本失败、latest 创建/读取/内容失败、官方 API/非稳定版本失败、过期 main/upstream 源或 parent、原事件/身份/移动tag/非root守卫。

## 实际发布验收

- [PR #2](https://github.com/srcheng17/teslamate/pull/2) 已按正常保护流程合并，源码 commit 为 `2db4c204578aa14d4c3fb9441ead72304af3f3a3`。
- [PR CI 37033504160](https://github.com/srcheng17/teslamate/actions/runs/37033504160)：两个原生架构 build 与 verify 成功；publish 按 PR 事件条件跳过。
- [main CI 37034259606](https://github.com/srcheng17/teslamate/actions/runs/37034259606)：两个 build、verify、publish 全部成功。各架构日志实际运行 62 项 Python 检查；严格补丁、上游 ExUnit、镜像许可/架构/非 root/健康检查均成功。
- 两个 latest 已实际推广成功，与共同固定版本 `v4.3.0-amap-2db4c204578aa14d4c3fb9441ead72304af3f3a3` 的索引 digest 分别完全一致。匿名 GHCR 查询确认两个索引恰含 linux/amd64 与 linux/arm64。
- 空临时 Docker config 无 auth 或 credential helper，按 latest 标签实际拉取四个 package/架构组合全部通过；本地架构及 OCI source/revision/version 回读一致，source 为本仓库、revision 为上述源码 commit、version 为上述固定版本。
- 临时镜像引用已清理，不启动或更新生产容器，不修改数据库或 Dockhand stack。两个 package 不具备原子更新，只有全部推广及匿名验证成功后才认定整体完成。

| Package | latest 与固定版本的索引 digest |
| --- | --- |

| `ghcr.io/srcheng17/teslamate-amap` | `sha256:51171cfe61443a185ae25a6b1533d94a7f825d2d65f1ca8b8b62252d8d91a701` |
| `ghcr.io/srcheng17/teslamate-amap-adapter` | `sha256:0c888df2324364f7c45f39ceaa6d9a1848a6a2622c18baa14ce3aae9746f5cbc` |

| Package | 架构 | Child manifest digest |
| --- | --- | --- |
| `teslamate-amap` | `linux/amd64` | `sha256:066e2f46423832d3116fc5717078ab47bac9961fb7dd446bba95f7830484fcb1` |
| `teslamate-amap` | `linux/arm64` | `sha256:ce91eea9e1b1df5c7c1bc7116344ca473f94cb786f95e6444d909bb68f571146` |
| `teslamate-amap-adapter` | `linux/amd64` | `sha256:f24f1b6f81d168972024ecaa24929a1a03827a3af69ee513b7e61820d9cb713c` |
| `teslamate-amap-adapter` | `linux/arm64` | `sha256:cb182f70c72fd9c621ee5c02cf4472dae22c59e9bb04ab8b5d4c720133d914e7` |
