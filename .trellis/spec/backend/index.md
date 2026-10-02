# 后端开发约定

本仓库维护独立 Python 标准库 `adapter/server.py`、`patches/` 中的上游 URL、刷新与 GeoRelay 品牌补丁和 `.github/workflows/` 构建流程，不复制完整上游。实现以当前任务 PRD/design、下列契约和 `tests/` 共同验证。

## Pre-Development Checklist

- 阅读 [接口与数据](contracts.md)、[质量与发布](quality-guidelines.md)。
- 追踪 TeslaMate Geocoder → Finch pool → adapter → AMap/Baidu/OSM → SQLite → TeslaMate Address 的完整流。
- 不操作生产容器、PostgreSQL、Dockhand，也不提交真实 Key、精确车辆坐标或运行备份。

## Quality Check

- `python3 -m unittest discover -s tests -v`；Python 标准库，无额外测试依赖。
- `git diff --check`；对固定上游验证补丁、Elixir 格式和对应 ExUnit 测试。
- 隔离 Docker 构建和健康检查；GitHub checks 必须核对实际结论。
- 不把模拟测试说成真实高德验证，不把构建/发布说成生产上线。
