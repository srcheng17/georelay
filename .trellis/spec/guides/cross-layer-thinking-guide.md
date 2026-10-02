# 跨层检查

- 追踪固定官方 Geocoder → HTTP pool → adapter → provider → SQLite → Address changeset；改变 URL 时检查 caller 和 pool 是否共用校验。
- 区分存储/响应 WGS84、AMap 临时请求 GCJ02、客户端显示纠偏；测试三者边界，禁止双重转换。
- 永久 ID 与可过期文字缓存分开，provider/language/重启不影响身份。
- 检查失败是否成为官方特殊 Unknown；非 200 固定错误应能稍后重试。
- 构建成功不等于生产可迁移。契约详见 `../backend/contracts.md`。
