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
