# Research: 应用管理永久地址身份与迁移约束

- Query: 将永久地址身份、原始 WGS84 坐标和必要来源证据归 TeslaMate/PostgreSQL，适配器仅保留可丢弃缓存；明确应用改动、历史迁移、回滚和验收边界。
- Scope: mixed；现有仓库和固定上游源码为主要证据，数据库文档为实施参考。
- Date: 2026-10-03
- Status: planning only；未实施产品改动，未运行生产命令，未读取生产数据库。

## Findings

### 1. 已确认范围与结论

任务 PRD 要求保留历史地址数据库主键、负数 `osm_id`、原坐标及行程/充电关联。永久状态应落在 `addresses` 的现有地址实体和必要元数据上，不另建重复的坐标身份映射表。适配器不需要 PostgreSQL 账号；应用在解析/刷新请求中提供坐标、身份以及已验证来源证据。删除缓存后必须能继续刷新历史地址。

这与现有实现的职责分配不同，是用户明确选择的未来契约。当前源码仍由 SQLite 分配负数身份，不能把本研究描述成已发布行为。

### 2. Files found

| 文件 | 用途 |
| --- | --- |
| `upstream.json` | 当前固定 TeslaMate `v4.3.0` / `33d200b2fba9d5138803916a788cef5eae31b1aa`。 |
| `adapter/server.py:53` | Decimal 坐标规范化，不经浮点转换或主动舍入。 |
| `adapter/server.py:321` | SQLite identities/cache 建表及历史 schema 迁移。 |
| `adapter/server.py:380` | reverse 先分配 SQLite 身份，再调用 provider。 |
| `adapter/server.py:393` | lookup 仅收 ID，再从 SQLite 找坐标与来源证据。 |
| `adapter/server.py:441` | 可信 OSM 来源批量刷新、按集合匹配、同来源展开。 |
| `adapter/server.py:484` | 缓存、大陆/境外路由与解析结果存储。 |
| `adapter/server.py:520` | OSM 来源与 outside_mainland 永久保存，非 OSM 结果不清空旧证据。 |
| `patches/0001-nominatim-base-url.patch` | Geocoder origin 与 Finch 专用 pool 一起配置。 |
| `patches/0002-refresh-address-fields.patch:44` | 刷新新增 name/road/house_number/postcode/raw，排除身份和坐标。 |
| `patches/0002-refresh-address-fields.patch:106` | 本地身份刷新缺项检测。 |
| `patches/0002-refresh-address-fields.patch:135` | 现有负 ID 入库、刷新关联、正身份兼容与失败回归。 |
| `tests/test_adapter.py` | 路由、精度、来源、语言、缓存、批量、超时和隐私测试。 |
| 固定上游 `elixir/lib/teslamate/locations.ex` | 查找地址与批量刷新入口，见下面永久链接。 |
| 固定上游 `elixir/lib/teslamate/locations/geocoder.ex` | Nominatim 请求与响应到地址 attrs 的转换。 |
| 固定上游 `elixir/lib/teslamate/locations/address.ex` | Ecto schema/changeset 与 identity unique_constraint。 |
| 固定上游 `elixir/lib/teslamate/log.ex` | 行程起终点、充电记录通过 addresses.id 关联。 |
| 固定上游 migrations | osm_id bigint、身份唯一索引、坐标 numeric(8,6)/(9,6)。 |

读取了已准备并打补丁的临时源码副本，但下文固定上游事实使用 commit permalink，研究产物不依赖临时目录继续存在。补丁行为引用仓库内持久 patch。

### 3. 当前应用流程的源码证据

1. `Locations.find_address/1` 从 settings 取语言，先 reverse 成功，再按 `{osm_id, osm_type}` 取地址；不存在才 `create_address`。没有先按坐标查找，也没有由应用分配本地负身份。[固定上游 locations.ex:35-48][up-find]
2. `Geocoder.details/2` 接受 Address 列表，但请求只序列化 `osm_type` 的首字母和 `osm_id`；`/lookup` 没有 lat/lon、来源或路由证据。[固定上游 geocoder.ex:37-55][up-details]
3. `Address` 已有 latitude/longitude Decimal 字段和 raw map；changeset 验证必要地址字段，唯一约束只覆盖 osm_id/type。[固定上游 address.ex:5-55][up-address]
4. `osm_id` 实际数据库列为 bigint，`addresses.id` 为 integer。不要混淆 PostgreSQL 主键和外部兼容身份，不用 `-addresses.id` 取代历史 ID。[osm identity migration:7-13][up-id-migration]、[precision migration:9-13][up-precision-address]
5. `addresses` 与 `positions` 坐标都保留 6 位小数；Ecto `read_after_writes: true` 会读回存储精度。SQLite 规范化坐标可以有更高精度，提升 PG 类型不会自动找回已经舍入的信息。[precision migration:9-13][up-precision-address]、[precision migration:61-66][up-precision-position]、`adapter/server.py:53-68`。
6. 行程和充电记录关联的是 `addresses.id`；分别调用 `Locations.find_address`，失败时保留事件、不给地址关联。[log.ex:389-428][up-log-drive]、[log.ex:454-479][up-log-charge]。新的失败处理要继续这个语义。
7. 上游将 HTTP 200 的 `Unable to geocode` 转成 osm_type=unknown、osm_id=0、坐标零的成功 attrs。[geocoder.ex:117-131][up-unknown]。适配器的临时失败不得触发这个特殊分支；新地址请求失败不得创建占位/Unknown 行。
8. `raw` 只是最近一次供应商返回结果。[geocoder.ex:134-156][up-raw]；当前 patch 的刷新也会覆盖它。OSM 结果包含 `raw.upstream` 的可信正 ID，后续高德/百度结果可能只携带自己的 provider 标记。永久 OSM 来源和独立 outside_mainland 不能仅从“当前 raw”重建。

### 4. 应用归属建议及必须保持的不变量

- 继续用现有 `addresses.id` 关联行程/充电。历史负 node `osm_id` 原值导入/保留，历史正 ID 与 unknown 不重编号。
- 本地地址的唯一坐标保存在 `addresses.latitude/longitude`；选择能承接现有 Decimal 精度、避免强制 6 位量化的数据库类型。精度提升仅限需要保存 canonical 地址点的列；不要顺带改写车辆 positions、轨迹或地图纠偏逻辑。
- 用最少的应用字段承接可信 OSM 来源 `{type, positive_id}` 和独立“已确认非大陆”证据。具体字段名由 design 定义；不能以 source_osm 存在等同于 outside_mainland，也不能把非 OSM 刷新当成清空来源的理由。
- app-owned 元数据应由合法适配器响应和已验证的历史 import 更新，不信任未知正数 ID、私人 fork hash、任意输入 raw 字段或坐标 bbox 推断的来源。
- 缓存期限、语言、供应商和重启只影响结果缓存，不影响 `addresses` 身份与 canonical 坐标。TTL 不自动改写应用已有文字。
- 适配器缓存不得保留“必须恢复”的映射；宜按 canonical 坐标、语言、策略及会影响 OSM 请求的来源上下文隔离。请求中应用身份只在响应中回传，不由 cache 中旧候选 ID 决定。
- 默认官方/自托管 Nominatim 路径继续现有语义；应用身份模式必须显式开启，客户端与 adapter 协议能力不匹配时启动或请求 fail closed。

### 5. 新负身份分配与并发

采用一条 PostgreSQL 标量降序 sequence 即可，不需要独立身份实体、通用注册框架或坐标 hash：

1. 完成迁移预检后确定历史已分配 ID 高水位。新值必须比全部历史负 ID 范围更小，包含尚未写入 PG 的 SQLite identities 和可信 SQLite sequence 高水位，不能只看 PG 已引用地址。
2. sequence 的 bigint 范围必须与 adapter 当前 `MAX_ID = 2**63 - 1`、合法 node 负身份解析范围一致。检测边界、overflow、错误的正/零/非 node 值；不用 abs/取负操作悄悄溢出。
3. `nextval` 的缺口正常：provider 失败不创建 Address，冲突失败也不回收 ID。不要为保证连续编号把 HTTP 放在数据库事务里。
4. 只有在精度恢复、冲突预检通过后，才建立本地地址精确坐标 partial UNIQUE；范围应排除正数历史对象与 unknown（例如负 node 本地地址），保留 osm_id/type 的现有唯一索引。
5. 并发同点请求可以拿到不同候选 ID，并在供应商请求完成后通过 partial UNIQUE 的插入冲突处理收敛到同一已保存 Address。数据库插入/读取获胜行要有确定的重试或冲突路径，不依赖先查后插的时间窗口。
6. 若应用选择序列化，应限制短临界区；不持有数据库行锁/连接跨越 8-25 秒供应商网络预算。无论采用哪条实现路径，都以并发测试验证同点同身份、无重复地址、无 Unknown、无长事务阻塞。
7. 缓存先于 DB insert 成功不会成为永久状态。若候选 ID 最终输给同点获胜行，调用方返回获胜 Address，缓存不能使后续刷新恢复输掉的候选身份。

PostgreSQL 官方 sequence 文档说明 nextval 原子分配且 rollback 不收回值；ON CONFLICT 文档提供插入冲突语义。实施时要在实际 Ecto/PostgreSQL 隔离测试中证明所选路径，不能仅凭该机制名称视为完成。

### 6. 历史迁移预检与阻断条件

所有实际演练在一致性恢复副本上进行，生产读取/变更须另行授权。只输出脱敏数量、布尔断言和错误类别；真实位置或地址不进入 Git/fixture/log。

| 预检 | 处理或阻断条件 |
| --- | --- |
| SQLite 完整性与版本/来源 | 用在线 backup API 或停机一致副本；识别 schema/version 与可信来源范围，未知来源不能自动信任。 |
| PG schema 与数字边界 | 核对 osm_id bigint、实际坐标 typmod、现有唯一/FK 约束及所有负身份范围；序列初始化须预检 overflow。 |
| PG 负 ID → SQLite ID | 按原身份匹配；PG 有本地负 ID、SQLite 无映射或坐标证据矛盾时阻断，不能按附近点猜测。 |
| SQLite 有身份、PG 无 Address | 由于 reverse 在 provider 查询前分配身份，可能是失败/未保存请求；不自动补占位 Address，但须预留全部历史 ID 范围。 |
| precision 证据 | 对每个匹配 ID 比较 SQLite canonical 坐标与 PG 6 位存储关系；必要时核对可信 raw 原输入。坐标提升须是原值恢复，不能变成 provider 坐标替换。 |
| coordinate duplicates | 区分舍入造成的同点与真正相同 canonical 点；原坐标恢复后仍冲突时停止，不能通过合并/删除 Address 改写关联。 |
| identity mismatches | 重复本地 ID、非 node 负 ID、缺失/非法坐标、同 ID 不同位置、provider 私有正 hash 等单列，失败关闭。 |
| permanent source import | 从 SQLite identities 导入 source_osm 与 outside_mainland；当前 raw 可做证据补充，不能代替已被覆盖的永久元数据。 |
| older SQLite schema | 无 outside_mainland 的历史 schema 曾只在境外 OSM 存来源，只有确认版本契约才可按原迁移规则推导；未知版本不套用。 |
| foreign keys | 比较迁移前后 addresses.id、drives.start/end_address_id、charging_processes.address_id 全部关系，地址数与历史 identity 不因升级改变。 |
| idempotency | 已导入且证据一致时重复执行无变化；证据不一致时停止；migration/version 状态记录不包含原始位置。 |

单纯 ALTER numeric scale 不能恢复历史高精度坐标，也不能提前以当前六位地址坐标做唯一化。若原始证据缺失，本任务不能声称完成“精确坐标保持”和旧映射可删除的验收。

### 7. 分阶段切换和回滚

- 演练前保存成对一致的旧 PostgreSQL、旧 SQLite 与旧镜像固定版本/digest；旧 SQLite 暂时保留为迁移/回滚证据。
- 停止旧身份分配写入窗口后预检、导入、设置降序 sequence，再验证新成对应用/adapter。不得让旧 adapter 继续分配并撞上新应用身份范围。
- 删除“缓存文件后可以继续刷新”的隔离演练通过前，不删除旧永久映射备份。
- 未产生新应用写入时可以恢复成对快照和旧镜像；不能只回滚一个容器，让旧 ID-only lookup 面对纯缓存数据库。
- 新模式已写入后，原 SQLite 不包含新身份。回滚要么验证从 PG 反向导出所有新增身份/原坐标/来源证据的能力，要么回到成对切换快照并明确新数据损失边界。不能把镜像 downgrade 描述成无条件安全回滚。
- numeric down migration 到六位会损失已保存精度；不得自动静默降级。回滚方案必须明确恢复/反导路径，且在隔离副本验证。
- 生产迁移、部署与旧数据删除不属于当前 planning 授权。首次切换与回滚操作须有独立、可审阅计划。

### 8. 应用侧测试矩阵

| 场景 | 必须验证的实际行为 |
| --- | --- |
| fixed upstream/default off | 未配置应用身份模式时，官方 Nominatim reverse/lookup、pool/proxy 和缺项 reverse fallback 保持原样。 |
| negative bigint | 实际 PG 入库/读回历史与新负 ID，边界不溢出，主键/FK 保持。 |
| exact Decimal | 超过 6 位的不同输入仍保存为不同点；数值等价的尾零/科学计数 canonical 成同点；SQLite 原值恢复后不误合并。 |
| same-point concurrency | 多个调用同点同时成功，只存一条 local Address，所有调用返回相同 ID；覆盖 provider 已成功但 insert 发生冲突的窗口。 |
| different points | provider/语言不同不跨点复用；唯一索引不影响历史正 OSM 或 unknown 行。 |
| provider failure | 新点 502/503/504 后无新增 Address/Unknown/占位关联；ID 可留缺口，之后成功可正常保存。 |
| refresh/cache deletion | 导入后删除整个新 adapter 缓存并重启，历史刷新仍回传同身份/原坐标，文字可更新，关联不变。 |
| source permanence | OSM → AMap/Baidu → OSM 后仍保留可信来源和 outside_mainland；显式大陆 OSM 不误记境外。 |
| batch matching | 50 项、同 OSM 源多 local 点、乱序、缺项、重复、额外项；按 type/id 校验，不 zip。 |
| protocol mismatch | 新 app/旧 adapter 和旧 app/新 adapter 明确失败，不分配意外 ID、不写 Unknown。 |
| historical import | 无 mapping、precision conflicts、unsupported negative type、invalid sources、sequence 高水位、重复 import、boundary overflow 全部有阻断测试。 |
| failure during import | 回滚/重试仍一致，历史主键与 FK 零改动；序列不回退重用。 |
| privacy | 应用和 sidecar 的请求、响应、异常日志都不泄露坐标、地址、供应商 Key、POST 请求体；只保存脱敏断言。 |
| restored-copy/rollback | 在固定版恢复副本演练导入、清缓存刷新、成对回滚，并证明产生新身份后的限制。 |

实施完成后按现有质量契约运行 Python、固定上游 patch/apply、Elixir 格式/ExUnit、双架构构建与实际镜像健康/启动验证。这里只定义验收，未运行这些实施测试。

## External references

- Fixed upstream: TeslaMate `v4.3.0`, commit `33d200b2fba9d5138803916a788cef5eae31b1aa`；上述源码链接均固定 commit，不使用浮动 main/tag。
- [PostgreSQL 18 CREATE SEQUENCE](https://www.postgresql.org/docs/18/sql-createsequence.html)、[sequence functions](https://www.postgresql.org/docs/18/functions-sequence.html)：降序范围、nextval 并发和非事务性缺口的实施参考。
- [PostgreSQL 18 INSERT / ON CONFLICT](https://www.postgresql.org/docs/18/sql-insert.html)、[partial indexes](https://www.postgresql.org/docs/18/indexes-partial.html)：局部唯一化与冲突收敛的实施参考。
- 固定上游 `.github/workflows/elixir_test.yml:26` 使用 `postgres:18-trixie`，但当前部署 PostgreSQL 版本未核对；外部数据库文档本轮未联网验证，实施须核对目标兼容范围。

## Related specs and intentional future deviations

- `.trellis/workflow.md`：task creation 不等于实施批准；保持 planning，复杂任务完成 PRD/design/implement 后等主会话审阅 gate。
- `.trellis/spec/backend/contracts.md:9-18`：现有 GET `/lookup` 和 SQLite 身份归属需变更；新协议、纯缓存 schema/health/backup 含义由 design 取代，实施后同步 spec。
- `.trellis/spec/backend/contracts.md:26-30`：长期 ADAPTER_DB、ID-only lookup 与 find_address 同身份复用表述将变化；默认官方路径、负 ID稳定、原坐标、刷新关联保持。
- `.trellis/spec/backend/contracts.md:68`：永久 source_osm 与 outside_mainland 原则保留，只转移归属到应用，不能因 cache-only 改造删掉。
- `.trellis/spec/backend/quality-guidelines.md:11` 及现有 prepared-source 改动范围：未来需要 Address schema/migration/application geocoding 等额外地址生产文件，超出现有三个文件/两个补丁的检查假设；须以本任务设计明确限定范围，再更新相应 spec/prepare tests，不能规避严格 pin/apply gate。
- `.trellis/spec/guides/cross-layer-thinking-guide.md`：完整数据流、WGS84/GCJ02边界、失败不成为 Unknown、构建不等于可迁移。

## Caveats / Not Found

- 没有访问生产库或真实旧 SQLite，无法确认实际冲突数、缺失映射、来源版本、精度分布、ID 高水位或目标 PostgreSQL 版本。迁移预检结果尚未获得。
- `positions` 也只保留六位；旧地址恢复到更高精度后，新 reverse 若从已落库 Position 取得六位输入，并不与旧精确点数值相同。迁移演练必须检查输入精度与历史复用边界，不以六位舍入或附近匹配强行合并身份。
- 新应用请求 schema/版本协商以及元数据字段名由主会话 design 与协议研究确定，本文件只给出必须承接的数据和约束。
- 不承诺无写入停顿的热迁移；旧 SQLite 的身份并不一定全部对应已保存的 Address。
- 当前应用 `Tesla.Middleware.Logger` 仍存在；新增含坐标请求体时必须检查应用日志路径，不能仅凭 sidecar 禁用访问日志视为隐私验证完成。
- 此次仅规划；不得把本文件当成生产脚本、已完成实现、已发布镜像或已经迁移的证据。

[up-find]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate/locations.ex#L35-L48
[up-details]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate/locations/geocoder.ex#L37-L55
[up-address]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate/locations/address.ex#L5-L55
[up-id-migration]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/priv/repo/migrations/20200120142602_replace_place_id_with_osmid.exs#L7-L13
[up-precision-address]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/priv/repo/migrations/20200410112005_database_efficiency_improvements.exs#L9-L13
[up-precision-position]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/priv/repo/migrations/20200410112005_database_efficiency_improvements.exs#L61-L66
[up-log-drive]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate/log.ex#L389-L428
[up-log-charge]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate/log.ex#L454-L479
[up-unknown]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate/locations/geocoder.ex#L117-L131
[up-raw]: https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/elixir/lib/teslamate/locations/geocoder.ex#L134-L156
