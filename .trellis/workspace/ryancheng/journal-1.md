# Journal - ryancheng (Part 1)

> AI development session journal
> Started: 2026-10-02

---


## Session 1: AMap and OSM adapter MVP
<!-- trellis-session: v=2 fp=eea932dc1a09dce0 -->

**Date**: 2026-10-02
**Task**: AMap and OSM adapter MVP
**Branch**: `feat/amap-adapter`

### Summary

Implemented and verified mainland AMap / overseas OSM sidecar and fixed-release TeslaMate URL patch; PR #1; no production changes.

### Git Commits

| Hash | Message |
|------|---------|
| `f09ecd0` | feat: add isolated AMap and OSM geocoding adapter |
| `0b2348d` | docs: record verified MVP and completed project guidelines |

### Testing

- [OK] 31 Python tests, 105 ExUnit tests, Docker health/license checks and GitHub run 36995771539 passed.

### Status

[OK] **Completed**

### Next Steps

- Review PR #1; real AMap key validation and any production migration require separate work.


## Session 2: 高德与 OSM 真实 Key 隔离联调
<!-- trellis-session: v=2 fp=946ff82940d0e89d -->

**Date**: 2026-10-02
**Task**: 高德与 OSM 真实 Key 隔离联调
**Branch**: `feat/amap-adapter`

### Summary

用户授权参考 Dockhand Key；18项真实联调通过，无产品代码与生产变更，更新脱敏验收文档。

### Main Changes

- README、验收记录和质量约定同步真实联调结论

### Git Commits

| Hash | Message |
|------|---------|
| `9c577a6` | docs: record live geocoding verification |

### Testing

- [OK] 大陆2点与境外/港澳4点、语言lookup、重启、TTL、断网缓存和恢复均通过
- [OK] 31项Python测试及文档检查通过；测试资源和tmpfs Key已清理，生产容器身份与启动信息不变

### Status

[OK] **Completed**

### Next Steps

- 现有PR待人工审查；生产迁移与历史导入仍为独立工作


## Session 3: 真实地址样本核对与 AOI/POI 名称修复
<!-- trellis-session: v=2 fp=57c9e72bdb5b5b54 -->

**Date**: 2026-10-02
**Task**: 真实地址样本核对与 AOI/POI 名称修复
**Branch**: `feat/amap-adapter`

### Summary

生产只读样本发现基础响应丢失地点名，改详细请求及AOI/POI优先映射；隔离复核恢复同点原名，未修改生产。

### Main Changes

- 最小名称修复、虚构回归、契约与脱敏验收同步

### Git Commits

| Hash | Message |
|------|---------|
| `99b67ea` | fix: preserve AMap area and place names |

### Testing

- [OK] 32项Python测试与独立复核通过，回归先红后绿
- [OK] 真实样本23项reverse及31项断言通过，同点旧高德17/17名称一致；临时资源与Key已清理

### Status

[OK] **Completed**

### Next Steps

- 历史OSM字段差异和旧正身份迁移仍须独立评估，未部署


## Session 4: 公开仓库与 README 整理
<!-- trellis-session: v=2 fp=831b546c98764bfd -->

**Date**: 2026-10-02
**Task**: 公开仓库与 README 整理
**Branch**: `feat/amap-adapter`

### Summary

按授权公开仓库并回读main保护；保留官方README结构，补充高德能力与独立配置指南，来源许可及公开内容审查通过。

### Main Changes

- README保留官方功能、截图、许可与致谢，新增能力与docs/AMAP.md一致；main要求PR和verify、base同步，禁强推及删除。

### Git Commits

| Hash | Message |
|------|---------|
| `1482e5894834c8459bd5ec862a98058b90adbd7d` | docs: present AMap integration with upstream project overview |

### Testing

- [OK] 30条相对链接/锚点、22个仪表盘锚点、3张固定commit截图、敏感信息审查及diff检查通过。

### Status

[OK] **Completed**

### Next Steps

- 推送最终提交并核对PR CI；未合并、发布或部署。


## Session 5: README 文字与结构优化
<!-- trellis-session: v=2 fp=0868b7f6de7a28ad -->

**Date**: 2026-10-02
**Task**: README 文字与结构优化
**Branch**: `feat/amap-adapter`

### Summary

安装并使用Humanizer v3.0.0改写README，保留官方功能来源，移除固定版本定位和验收报告口吻。

### Main Changes

- README按地址功能、使用、官方功能与截图、版本维护组织；具体构建版本指向upstream.json，准确区分检测新版与自动构建。

### Git Commits

| Hash | Message |
|------|---------|
| `f8ad02d328fffd989d82b7151748930b26e821b7` | docs: simplify README structure and version guidance |

### Testing

- [OK] 23个相对链接/锚点、22面板链接、3固定截图、Markdown/JSON/diff及独立增量审查通过。

### Status

[OK] **Completed**

### Next Steps

- 推送当前功能分支，核对最终verify；不合并、发布或部署。


## Session 6: README 中英文与版式整理
<!-- trellis-session: v=2 fp=b18cc1ee09c70d81 -->

**Date**: 2026-10-02
**Task**: README 中英文与版式整理
**Branch**: `feat/amap-adapter`

### Summary

默认英文README、中文可选，参考Immich/Syncthing/RustDesk整理语言导航与截图折叠，删除第三方客户端说明。

### Main Changes

- 两版顶部语言切换和短导航，使用入口靠前，官方功能和长列表折叠；保留许可来源并准确说明版本流程。

### Git Commits

| Hash | Message |
|------|---------|
| `feca63335c8cb1ff31570f90cd10c827aafc6388` | docs: add bilingual README navigation and layout |

### Testing

- [OK] 49个相对链接锚点、双语结构内容及独立审查通过；GitHub官方Markdown渲染保留标题、三图、三个折叠区。

### Status

[OK] **Completed**

### Next Steps

- 推送当前功能分支并核对最终GitHub verify；不合并、发布或部署。


## Session 7: README stack setup
<!-- trellis-session: v=2 fp=f2ef503ec4be37e8 -->

**Date**: 2026-10-02
**Task**: README stack setup
**Branch**: `feat/amap-adapter`

### Summary

中英文 README 直接提供并入现有 TeslaMate stack 的局部配置与两镜像本地构建方法。虚构 Compose 合并保留原设置、默认及自定义同网、持久卷和安全配置检查通过；50 个链接锚点、GitHub GFM 渲染和独立审查通过。未修改生产或发布镜像。

### Git Commits

| Hash | Message |
|------|---------|
| `ce2586ae82c3e3c17db9ca289bfe5e0ef47e759f` | docs: show adapter setup in an existing TeslaMate stack |

### Status

[OK] **Completed**
