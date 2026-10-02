# 实施顺序

1. 实现最小脚本及离线 fake Docker 回归；覆盖默认入口、退出/超时/探测/迁移失败及清理。
2. 纳入 ci.yml 双架构 build，置于 artifact 保存前；同步必要维护文档与质量约束。
3. 核对固定官方端点、entrypoint、环境与迁移；重新准备当前源码并实际构建 arm64 主镜像/adapter。
4. 运行真实隔离检查与故意损坏入口的失败检查，保存脱敏证据；运行相关 unittest、语法、actionlint、diff检查。
5. 独立 review 并修正机械问题；提交到当前任务分支。若 push/PR，报告分支、PR、实际双架构 checks 等待用户审阅，不合并。
