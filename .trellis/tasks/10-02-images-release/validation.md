# 验证记录

2026-10-02。自动构建和发布范围离线验证完成，真实双架构发布待 CI。

- 独立 reviewer 核对受控 pin-only 分支、main 单父提交、双架构 verify 汇总、从测试产物直接发布以及移动 tag 拦截。
- 19 项 release/updater/publish 检查通过；全仓合并供应商改动后 55 项 Python 检查通过。
- 移动 tag 与 Docker UID 执行失败/空输出/非数字的回归先复现旧失败，再验证修复。
- Bash、actionlint v1.7.12、Python 语法、git diff --check 通过。
- main 保护实际回读：verify、strict、PR required、管理员适用、禁止强推。Actions PR 创建权限已按授权开启，工作流默认 read。

两 package 不具备跨包事务。实际发布后必须分别核对两个索引及匿名拉取；只完成架构 push 或首个索引不能称双镜像发布完成。不部署生产。
