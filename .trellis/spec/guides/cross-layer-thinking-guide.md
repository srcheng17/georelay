# 跨层检查

- 追踪 PG 身份 → 固定官方 Geocoder → HTTP pool → adapter 缓存 → provider → Address 写入；URL 校验供 caller/pool 共用。
- 区分存储/响应 WGS84、AMap 临时 GCJ02、客户端显示纠偏，禁止双重转换。
- PG 永久身份/来源与可丢弃文字缓存分开；检查候选竞争、精确坐标和 context 是否逐层保持。
- fresh 不能从空 PG 推断；legacy 精度/全部高水位审计通过后才能建唯一约束与启用。
- application 失败不得写 Unknown，批次错误不得部分返回；保留单地址/导入与上游事件写入边界。
- 固定双镜像、浮动别名和 Release 记录分别核验；补录只修记录门禁，不能豁免镜像或 alias 失败。
- 构建成功不等于生产可迁移，本地 fake API 不等于 native token/云端发布已验证。契约见 `../backend/contracts.md` 与 `../backend/quality-guidelines.md`。
