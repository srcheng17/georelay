# 应用、适配器与历史迁移的跨层实施复核

日期：2026-10-03。范围：固定官方源码中的地址补丁、新 POST 协议、永久来源保留、精确坐标、初始化/迁移以及失败写入边界。复核者负责本次 adapter 实现，独立只读审查其他 implementer 的应用/迁移与 Release 实现；不把自己的 adapter 实施称为独立审查。最后修正仅关闭三个 SQLite 测试 fixture 连接，不改产品代码。

当前复读版本：`patches/0003-application-owned-identities.patch` SHA256 `f389830d373f7d17d54724f2659b8df6b1e9e462fa092ea2c6ddd9d7780a5458`。同时复读 `/tmp/georelay-application-20261003/elixir/` 中实际应用后的源码及回归测试。应用与适配器未发现剩余产品代码阻断；最终编译镜像的 fresh/legacy 收尾由主会话执行并记录于 `verification.md`。

## 已确认问题与闭环

### P1：合法但不同的响应来源可覆盖既有可信来源（已关闭）

原 `Geocoder.validate_local_response` 只校验来源字段形状，随后 `merge_raw` 合并响应 metadata；一个不同但合法的正 OSM type/id 因而可能覆盖已经保存在 PostgreSQL 的可信来源。

当前 `elixir/lib/teslamate/locations/geocoder.ex:206,230` 在构造 Address 前执行 `matching_source?`：请求已带来源、响应也带来源时，两字段必须完全一致；响应缺省可选来源时，`LocalIdentities.merge_raw` 沿用原证明。首次新点仍可获得适配器验证后的合法来源，不阻断正常 OSM 首次解析。

当前 `elixir/test/teslamate/locations/local_identities_test.exs:274` 分别返回另一合法 ID 与另一合法 type，断言 `:invalid_adapter_response` 且完整地址行未变；`:310` 验证新分配地址能接收新来源。已有供应商切换测试在 `:256` 确认缺省来源不会清除此前 OSM/境外证明。最终 compiled fixture 的 `scripts/runtime_geocoder_stub.py` 另返回 `source_osm_id=456`，`scripts/runtime_locations.exs:83` 对刷新失败前后的全部地址快照作零写入断言，主会话执行收尾验证。

### P1：显式 null 来源被当作缺省并破坏永久上下文（已关闭）

原 `validate_context` 使用值均为 nil 判断“没有来源”，接受显式 `source_osm_type:null/source_osm_id:null`；Map.take 保留这些键，合并时可清掉旧来源，或者留下 outside=true 但没有来源的非法永久 metadata。相同错误也影响导入文件校验。

当前 `elixir/lib/teslamate/locations/local_identities.ex:49` 仅两个键都不存在才允许来源缺省；键存在则必须为合法成对 type/正 BIGINT，不能为 null。校验发生在响应持久化与导出数据审计之前。

当前 `elixir/test/teslamate/locations/local_identities_test.exs:324` 覆盖双 null、单 null、半对与合法字段配 null，断言失败且整个旧地址/来源原样；`:371` 覆盖 legacy null 导入，断言坐标未恢复、旧行未变、ready marker 未创建。真正缺省且 outside=false 仍可接受。compiled fixture 使用 outside=false 的双 null，避免依赖既有 outside=true 规则偶然拦截；主会话执行最终镜像验证。

## 核对的跨层合同

- PostgreSQL addresses 保存主键、稳定负 node ID、精确 WGS84 与必要来源；降序 BIGINT sequence 仅保存高水位。默认 nominatim 仍走原 GET；application 显式启用 POST，不向官方服务发送自定义协议。
- 未完成显式 fresh/legacy 初始化不能分配或刷新。空地址表不会自动证明 fresh；fresh apply 要求声明且检查旧负身份。原 schema migration 只扩大 NUMERIC 并准备序列/state，导入审计及精度恢复之后才创建局部精确坐标唯一索引。
- provider 网络请求在长期数据库事务外；候选并发插入 DO NOTHING 后按精确坐标回读胜出行，返回胜出身份/raw。失败允许 sequence 空洞，不生成 Unknown、空白地址或回收已发编号。
- response 严格匹配负身份、原坐标、metadata version/来源与完整身份集合。lookup 逻辑最多50项，按真实编码尺寸拆成不超过60 KiB子请求；全部子请求核验完才交给 Locations，后批失败不返回前批成功列表。保留上游逐地址、跨批和起终点独立解析边界。
- 三处 coordinate 合同已对齐：app/export/adapter 的 coefficient与exponent各1024，文本最多2050字节，精确规范化，不受 Python Decimal 默认28位运算精度舍入。PG地址精度扩大但 positions 与轨迹未改。
- adapter cache key 以精确点、语言、策略及来源/境外上下文隔离，模板不绑定客户端身份/坐标，封装时加入本次请求值。cache TTL/整库删除不会丢 PG 身份；每60秒最多清理500条过期cache，无永久表写入、无VACUUM。旧 ADAPTER_DB/含 identities 的旧文件明确拒绝而非静默复用。
- 可信 OSM lookup 先完整核对 type/id 集合，再缓存；同来源可展开多个本地身份。公共 OSM 限流/专用UA、四worker/deadline、供应商切换与港澳/境外路由保持；GCJ-02只临时用于大陆高德请求，存储/响应仍WGS84。
- exporter 默认一致副本只读预览，包含所有映射及 sqlite_sequence 已分配范围，含未被PG引用/已删除的高水位；显式 export 使用0600且拒绝覆盖。SQLite nullable source columns 表示未记录来源，输出JSON中省略键；这与拒绝JSON显式null一致。
- legacy apply 在初始化advisory/table锁与一个PG事务中完成：先验证全部证据、坐标/raw/来源与冲突，再恢复原精度，保留PK/负ID/FK，建立索引/state和范围。未引用身份只保留分配范围，不创建空白PG地址；失败无部分坐标恢复或ready marker，同一证据幂等。
- 文档明确先配置 `GEORELAY_ADDRESS_MODE=application` 再 import。固定 Ecto `cast_decimal` 调用 Decimal.parse，默认超过34位输入拒绝而非舍入；若绕过文档在默认模式导入超精度数据，update失败会触发PG事务回滚。没有证据支持静默精度破坏，不据此扩大实现或新增产品模式。
- 新模式产生新编号后，旧SQLite不含新增映射，不能仅降级镜像；需要匹配截止点PG/旧SQLite恢复。不存在长期双写、PG凭据给adapter、静默六位down migration或正数hash来源推断。

## 验证证据及边界

- adapter实施测试34项通过。主会话最终adapter image为 `sha256:c72eb5b7bec3ec72c1d9cea75c4064f55115740e97cb4e38f3fad1c63ed6c973`。
- Python3.13 ResourceWarning来源确认为3个测试fixture的SQLite连接生命周期。仅将 `tests/test_adapter.py:367,378,725` 的连接包在 contextlib.closing 中；在已构建镜像、network none、`-W always::ResourceWarning` 下34项通过（10.367秒），无警告，不改变产品镜像。
- 应用implementer报告上述最终SHA的150项完整相关ExUnit通过，并完成compile warnings-as-errors、formatter及补丁系列严格准备/逆向树一致检查。本复核实际复读4项新增回归和对应源码，按主会话要求不重复同套件。
- 主会话报告最终fixture对应13项主镜像shell/HTTP回归通过（26.137秒）；最终编译fresh/legacy镜像结果以 `verification.md` 收尾记录为准，不把之前构建SHA当作最终修复验证。
- Release独立复核已关闭3项真实问题，85项聚焦回归通过，见子任务 `research/implementation-review.md`。该结果不代替trusted-main首次启用、native GITHUB_TOKEN写权限、实际云端双架构发布或匿名拉取证明。

未读取生产坐标/凭据，未写生产数据库、迁移真实部署、发送真实通知、push、创建/更新GitHub Release或合并。本地源码、fake/loopback与native arm64镜像证据不冒充线上/amd64或真实地图Key联调。当前任务PR/分支的合并仍需用户明确授权；本复核不授予发布或生产操作权限。
