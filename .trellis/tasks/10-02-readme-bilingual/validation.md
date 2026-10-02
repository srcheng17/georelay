# README 双语与版式验收

2026-10-02，承接用户对 README 的后续反馈：移除第三方客户端说明，提供默认英文与可选中文，并参考高 Star 开源项目的首页排版。此次只修改文档及项目约定，未修改产品、工作流、构建版本或生产服务。

## 参考与编辑

通过 GitHub 官方 API 读取 Immich、Syncthing 与 RustDesk 当前固定提交的 README，参考顶部语言选择、短导航、简短介绍和独立截图区。公开源码与当日 Star 快照见 [版式研究](research/readme-layout.md)。没有复制这些项目的品牌、徽章、统计或安装命令。

两种语言继续使用已安装的 Humanizer v3.0.0 编辑流程。README.md 为英文，README.zh-CN.md 为中文；中文技术指南返回中文首页。此前用户要求删除的 HedgieMate 和客户端地图说明包含在本次文档改动中。官方功能、来源截图、许可、致谢和逐字非官方声明保持原范围。

具体构建版本以 upstream.json 为准，版本说明区分检测 release、审查更新 pin、自动测试构建及 main 手动发布，不把当前版本写成项目长期定位。完整配置、身份备份及接口仍在详细指南，不虚构发布镜像。

上一版提交 `c1a24349632dc09ac8f06498ce1242ccf39c839a` 的 [CI](https://github.com/srcheng17/teslamate/actions/runs/37015755290) 实际成功，仅作为既有代码验证。本次最终提交的检查以 [PR #1 checks](https://github.com/srcheng17/teslamate/pull/1/checks) 为准，交付前核对；此次不合并、发布或部署。

## 检查结果

- 实现和独立只读审查均通过。两版内容、配置示例和链接一致，各保留 9 项官方通用功能、22 个面板链接、3 张固定截图和逐字非官方声明，均未包含第三方客户端说明。
- 两版及技术指南共 49 个相对链接/锚点有效，Markdown 围栏、details/summary 结构、任务 JSON 和 `git diff --check` 通过；独立增量审查无阻断或敏感信息。
- 通过 GitHub 官方 Markdown API 渲染两版，标题、3 张图片和 3 个折叠区保留。该接口不生成标题 ID，因此导航按渲染后标题对应的 GitHub slug 验证，并结合独立的本地锚点检查，不将 API 缺少 ID 误判成页面导航失败。
- 未改 LICENSE、NOTICE、TRADEMARK.md，也未新增品牌素材、虚构徽章或生产配置；没有重复执行本地产品测试，最终 CI 另行核对。
