# 设计

## 构建与发布

复用 ci.yml，以原生 amd64/arm64 runner 运行现有完整验证；每架构保存已测试的两镜像 tar。单独 verify 汇总 matrix 结果，保持 main 保护检查名称，失败不得由 skipped 掩盖。

main push 自动发布，main 手动 dispatch 仍可用。自动上游分支只允许 upstream/<稳定tag> 的 dispatch；发布前验证相对 main 的改动只有 upstream.json，tag 与分支匹配。PR 事件不发布。

发布 job 顺序载入两个 tar 并立即推架构标签，避免同名 checked tag 覆盖；随后组合两镜像的多架构版本索引。版本保持 <upstream-tag>-amap-<完整源码commit>，与 OCI source/revision/version label 一致。首次 package 设为 public 后再证明匿名拉取，公有 repo 不自动等于公有 package。

## 官方更新

每六小时轮询官方稳定版，GitHub schedule 为尽力调度，不保证立即触发。复用 check_release 严格校验，自动更新只创建 pin 分支/PR，不改 main 或补丁，不 force push。

显式 workflow_dispatch 触发同一 CI，避免 GITHUB_TOKEN 创建的 PR 需要人工批准运行。updater 最小权限 contents/write、pull-requests/write、actions/write；发布 job 才有 packages/write。仓库允许 Actions 创建 PR，代码不审批或合并。

已有分支必须保持相同官方 pin，不能将移动 tag 当作可更新版本；复用分支/PR，排队或已成功的构建不重复触发。创建分支、PR、dispatch 中途失败可重试恢复缺少的后续步骤，失败可重试但不忽略错误继续发布。

## 文档

使用公开 GHCR 镜像和统一版本变量，保留 Key/User-Agent、永久卷及同网；只提供现有 stack 局部片段。实际发布前不宣称已匿名可用，完成后用已验证版本更新示例。
