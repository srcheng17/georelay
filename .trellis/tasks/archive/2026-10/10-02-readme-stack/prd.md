# 直观的 stack 接入说明

## 目标

将中英文 README 开始使用部分改为直接操作现有 TeslaMate stack 的说明，让读者看到需要新增的适配器服务和现有 TeslaMate 服务的两项修改。

## 范围

- 复用现有 adapter Dockerfile 和上游 prepare/build 流程，不新增构建抽象、Dockerfile 或完整 stack。
- 两版 Getting started 提供可读的局部 Compose 片段：现有 teslamate 使用 teslamate-amap:local 镜像并设置 NOMINATIM_BASE_URL；新增 amap-adapter:local，配置 Key/User-Agent、永久卷、不开放 host port，沿用现有示例安全配置。
- 清楚说明 local 标签来自源构建，当前没有可直接拉取的已发布镜像。用邻近简短构建说明或折叠区让读者取得两个镜像，不只外链中文开发指南。
- 明确这是并入已有 stack 的修改片段，保留原有 environment/服务/卷。默认同网可互通，显式自定义网络需将适配器加入 TeslaMate 的同网并保留外网出口。
- 不能说原始官方 TeslaMate 只增加一个 sidecar 就可用；URL 支持仍需本仓库补丁镜像。永久身份卷备份和旧地址兼容说明保留链接。
- 同步详细指南里的 stack 接入说明，两版事实、代码配置及主要入口一致；其余官方功能、截图、来源许可、语言切换不改。
- 不修改产品、workflow、pin 或生产，不合并、发布镜像或部署。测试只用假配置执行 Compose 解析，不接生产。

## 验收

- 读者能直接看到新增容器和 TeslaMate 服务要改的 image/env，不依靠抽象步骤推导。
- README 镜像标签与实际构建命令一致；无虚构 GHCR 标签或单 sidecar 即可支持官方镜像的说法。
- 中英文代码片段一致；Compose 解析与和假基础 stack 合并检查通过，原配置保留、同网、持久卷、无 host port。
- 链接、Markdown、diff 与独立审核通过，推送当前 feat/amap-adapter 后核对最终 verify。
