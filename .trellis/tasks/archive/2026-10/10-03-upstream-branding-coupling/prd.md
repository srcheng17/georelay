# Reduce upstream branding coupling

## Goal
降低 GeoRelay 跟随上游稳定版本时的无关构建中断，同时保持地址行为、公开独立品牌和法律文件完整性。

## Background and authorization
- 用户先确认允许内部沿用 TeslaMate 技术标识、取消整个静态目录全等检查，并保留公开应用品牌、法律文件完整性和构建启动验证；随后明确要求“确认，创建trellis任务本分支优化”。本任务在 enhanced-hedgehog 隔离分支实施。
- 两份地址功能补丁合计修改 3 个独立生产文件；品牌补丁修改 27 个生产文件，其中 20 个是 gettext 目录文件。具体统计和条款边界见 research/branding.md。
- scripts/prepare_upstream.py:57-61 的全目录文件集合检查会阻止无关静态文件变化；64-83 的源码片段和全局名称扫描将源代码书写形式当作品牌判据。
- patches/0003-georelay-branding.patch:203-1051 为翻译的逐行品牌补丁，容易受翻译换行和上下文变化影响。

## Requirements
1. 内部脚本、模块、数据库/MQTT 标识和必要法律署名可继续沿用 TeslaMate；无关内部名称不能导致准备失败。
2. 无关非视觉静态文件的增加以及旧已知品牌图标的删除不再阻止准备；保留 GeoRelay 图标替换，新增未知视觉资源仍需人工复核。
3. 当前四条用户可见应用名称文案在所有语言中仍使用 GeoRelay；机械翻译处理不依赖 diff 行号、周边文案或换行布局，且不修改其他消息、注释、技术标识或法律署名。
4. 公开标题、导航名称、图标、项目链接、逐字免责声明和法律署名继续由实际渲染/静态资源测试验证。
5. 保留固定 tag/commit 核验、严格应用功能和模板补丁、地址身份与刷新契约、法律原文变化人工复核和双架构构建门禁。
6. 文档和相关 Trellis 规范明确检查边界与受控品牌转换的维护方式。

## Acceptance criteria
- [x] 真实离线 Git fixture 中，无关内部名称和新增非视觉静态文件可通过，原文/文件保留。
- [x] 缺失旧已知品牌资源可通过，GeoRelay favicon 正确生成；未知新增视觉资源仍被拦截。
- [x] 品牌 patch 不再触及 gettext 文件；受控转换处理当前四个语义 msgid 的多行形式及其翻译，其他条目逐字保留。
- [x] 当前固定上游 prepare 成功；转换后的翻译消息语义与现有品牌效果一致，默认/德文/中文及所有实际可用语言的渲染检查通过。
- [x] 全仓 Python、实际上游格式/ExUnit 检查和隔离镜像构建/健康检查通过；验证失败或未执行时明确记录，不夸称云端双架构已完成。
- [x] 文档与规范同步，git diff --check 通过；当前任务改动保持在 enhanced-hedgehog。

## Out of scope
- 不重写 Dockerfile、不建立完整 fork、不修改地图供应商及生产数据契约。
- 不放宽法律原文变化审核，不修改 LICENSE/NOTICE/TRADEMARK.md。
- 主应用连接临时数据库的启动验证已交给用户指定的 agent；本任务不重复修改 ci.yml 或 scripts/test_upstream.sh 的启动逻辑。
- 不部署生产、不更新 registry、不合并分支；push/PR 需要报告并等待用户审阅。
