# 实施与验证计划

1. 根 agent 补齐 backend/frontend 约定、PRD/design/context（先于产品代码），激活既有 task。
2. adapter worker 独占 `adapter/`、`tests/test_adapter.py`：stdlib HTTP/SQLite、输入和上游边界、容器与 mock/HTTP 测试。
3. patch worker 独占 `patches/`、`upstream.json`、`scripts/prepare_upstream.py`、`scripts/test_upstream.sh`、`tests/test_upstream.py`：官方契约追踪、URL 补丁与 ExUnit 测试、严格应用测试。
4. release worker 独占 `.github/`、`scripts/check_release.py`、`tests/test_release.py`：检测/校验/构建/手动发布 fail closed；与 patch worker 对齐命令。
5. 根 agent 负责 README、示例 Compose、来源许可、集成测试、跨组件质量检查、私有 GitHub commit/push/PR/check 核验。所有 worker 不提交、不推送、不操作生产，不覆盖别人编辑。
6. 完整质量门通过后记录验收、完成 bootstrap/task bookkeeping，同步可审查提交。

## 检查

- `python3 -m unittest discover -s tests -v`、`git diff --check`。
- `python3 scripts/prepare_upstream.py <isolated-dir>`，严格 pin/apply；`scripts/test_upstream.sh <isolated-dir>` 在隔离 Elixir/Postgres 环境运行对应 ExUnit，不使用任何生产容器或卷。
- Docker build adapter 与官方补丁镜像；只创建独立测试资源并清理。
- GitHub checks 真实通过；无 Key mock 覆盖不能等价声称 AMap 实际账户可用。

## 风险与回退

对工作分支普通 revert 即可；无生产状态变更。SQLite 永久 ID 是外部引用契约，未来迁移需独立备份/恢复验收。官方 4.0.1→4.3.0 数据迁移及回滚不属本次构建验证。
