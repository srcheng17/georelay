# 验证记录

## 改动与审查

- `README.md`、`README.zh-CN.md` 直接展示并入现有 stack 的 Compose 片段，附已有流程的两镜像构建命令；`docs/AMAP.md` 区分接入现有 stack 与独立调试示例。
- 两版 YAML 和构建命令逐字一致。镜像标签与命令对应；明确当前未发布预构建镜像、官方镜像需要 URL 补丁、原服务配置需保留。
- 独立 trellis-check 审查核对了完整本轮 diff、任务材料、接口契约、质量约定、实际 Dockerfile 与构建入口，无阻断项。README 使用段之外未改动。

## Compose 配置解析

从实际 README 提取 YAML，使用临时虚构基础 stack 与假 `.env` 执行 `docker compose config --format json`，断言：

- TeslaMate 使用 `teslamate-amap:local`，新增 `NOMINATIM_BASE_URL=http://amap-adapter:8080`。
- 原 TeslaMate 环境变量、ports、volumes、depends_on 与网络保留；数据库、MQTT、Grafana 的完整服务配置及原命名卷保留。
- 适配器使用 `amap-adapter:local`，无 host port，保留 `amap-data:/data`、只读根文件系统、tmpfs、cap_drop 与 no-new-privileges。
- 默认网络互通且未设置 internal；按文档为自定义 bridge 网络补上同网配置后，两服务仍同网且保留出口。

以上检查通过。仅解析配置，不读取真实 stack 或 `.env`，不创建容器、网络、卷，不操作生产。

## 文档检查

- 50 个相对文件链接和标题锚点通过（英文 18、中文 18、指南 14）。
- 三份文档通过 GitHub GFM API 渲染。两版 README 的四组 details/summary、构建命令与 Compose 代码块保留；锚点按实际渲染标题生成 GitHub slug 核对。
- 初次渲染断言误写为五组折叠区；按源码核对为四组，修正临时验证脚本后通过，文档未因此修改。
- `git diff --check` 通过。

本轮只改说明与约定，未改产品代码、版本 pin 或 workflow。最终提交的完整 CI 结果由 PR 检查记录；本地不重复上游构建、真实 Key 或数据库抽样验证。
