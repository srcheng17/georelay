# 本地实施验证

日期：2026-10-03。用户已确认实施；分支 holy-shrimp，独立工作区。未读取真实车辆位置/凭据，未操作生产、发布、push或合并。

## 实现与源码证据

- PG addresses 是永久身份/精确 WGS84/可信来源的权威；序列只管降序高水位，适配器仅 disposable cache，无PG凭据。
- 默认官方 Nominatim GET 保留，新模式 POST 严格核验；显式 fresh/legacy 门禁、全 SQLite 分配范围、精度恢复、候选竞争、来源保留与失败无 Unknown 已实现。
- 固定官方 v4.3.0 / 33d200b2fba9d5138803916a788cef5eae31b1aa 严格准备通过；依赖补丁使用独立临时index全系列预检，失败零部分应用，逆序树一致性通过。
- 最终补丁相关 ExUnit 150 项、compile warnings-as-errors及格式通过。末轮review发现并修复显式null和已有来源被不同合法来源覆盖两个遗漏，新增4项回归；刷新零写、旧来源保持、legacy原子拒绝及fresh新来源均通过。
- Exporter/prepare Python聚焦15项通过；完整仓库173项通过，最后整套回读为94.233秒，无ResourceWarning。

## 隔离镜像与集成证据

- 适配器最终镜像 c72eb5b7bec3ec72c1d9cea75c4064f55115740e97cb4e38f3fad1c63ed6c973；packaged 34 项在 --network none 下通过。随后只修3个测试fixture sqlite连接关闭，再以 -W always::ResourceWarning 运行34项通过且无警告（10.367秒），产品镜像未改变。
- 最终主镜像 6efb92f09590323f29e4cb6c886ad2a841037e373cd1804d7d205b1a55a12c0f；native arm64 build通过。上游Sass弃用警告保留，无定制UI修改。
- 实际默认entrypoint分别运行 fresh、legacy：登录表单HTTP200、106条迁移、核心表、编译RPC检查通过；各自独立internal网络/tmpfs PG，清理成功。
- fresh：精确新点、复用避免第二次reverse、正地址/行程/充电/positions关联、语言与来源、失败零写以及8个并发候选收敛。
- legacy：-10001/-10002同六位但原精度不同的历史恢复、缺证据原子拒绝、预览/导入/重复幂等、原PK/FK/positions/正地址保留、未引用10003不造地址、高水位10010后新候选绕过。
- 两镜像native arm64、non-root，适配器health/protocol/cache-only schema/license与临时资源清理回读通过。无真实地图Key或外部provider请求。

## 文档与审查

- 保留用户要求的README删除，双语配置、迁移/缓存/回滚与可读更新说明同步；原Compose project/卷/实际服务名保留要求。
- 49个本地链接/锚点、fences、双语Compose一致性及与合成原stack合并验证通过，原DB/MQTT环境/网络/卷保留，无生产配置读取。
- 新接口和发布七节可执行spec已同步；parent/child contexts校验通过。独立Release review闭环3项；应用跨层review复读最终patch，null和wrong-source两项闭环，无剩余代码阻断。

## 未执行与门禁

当前本地arm64和fake测试不能代替云端native amd64/arm64或实际Release/native-token权限证明。可信writer首次合入需当前任务明确审阅；生产迁移/容器升级仍不在范围。新模式分配后不能只降级镜像，需相同截止点PG/旧SQLite恢复。本地实施完成与完整线上验收分别记录，任务保持in_progress。

末轮fixture增加null-source与wrong-source失败，13项主镜像shell/HTTP回归通过（26.137秒）；检查失败零写并保留旧可信来源。

## 最终版本收尾

最终0003 SHA256：f389830d373f7d17d54724f2659b8df6b1e9e462fa092ea2c6ddd9d7780a5458。重新strict prepare到独立空目录，严格应用v4.3.0固定源码，构建上述最终镜像。该最终镜像的fresh/legacy两次默认入口检查各成功：HTTP200登录表单、106条迁移、compiled RPC（包括null/wrong-source失败零写与旧来源保持）、清理回读。此证据替代修正前镜像。

完整仓库最后整套173项（94.233秒）后仅增加同一fixture测试内的wrong-source断言；该受影响13项又完整通过（26.137秒），应用新增源码另由150项ExUnit及最终compiled两个场景验证。adapter最终34项无ResourceWarning；Release独立两轮review无剩余代码阻断。
