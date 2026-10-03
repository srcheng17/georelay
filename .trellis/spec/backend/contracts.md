# 接口、数据与隐私

## 1. Scope / Trigger

适用于 `adapter/server.py`、三个地址补丁、迁移工具与 Compose 的跨层变更。永久身份由 TeslaMate/PostgreSQL 管理；适配器仅持可删除的查询缓存，无 PostgreSQL 凭据。默认官方 Nominatim GET 路径仍保留。

## 2. Signatures

- `GEORELAY_ADDRESS_MODE=nominatim|application`，缺省 `nominatim`。application 使用 `POST /v1/reverse` 和 `POST /v1/lookup`。
- `TeslaMate.Locations.LocalIdentities.initialize_fresh(fresh_install: true)` 预览；增加 `apply: true` 才初始化。PG 没有负地址不能证明从未使用旧 SQLite，fresh 声明由操作者核实。
- `TeslaMate.Locations.LocalIdentities.import_file(path)` 预览；增加 `apply: true` 才导入。结果为 `{:ok, %{mode: :preview|:applied|:already_initialized, kind: :fresh|:legacy, addresses: count, legacy_high_water: count}}` 或固定错误 atom。
- `python3 scripts/export_legacy_identities.py SNAPSHOT` 默认只读审计；`--export --output PATH` 输出 0600 JSON，拒绝覆盖。仅经核实旧 schema 语义时使用 `--legacy-osm-implies-outside`。
- `addresses.latitude/longitude` 为不限 scale NUMERIC；`georelay_address_identity_seq` 为降序 BIGINT；`georelay_identity_state` 保存 singleton/version/kind/evidence_sha256/legacy_high_water。
- 完成显式初始化/导入后才建立 `addresses_georelay_coordinates_index`，只约束负 node 的精确坐标。旧 osm_id/type 唯一约束保留。
- `GET /health` 返回 `{"status":"ok","protocol":1,"storage":"disposable-cache"}`。`python3 -m adapter.server --backup DEST` 只备份新缓存，拒绝覆盖和旧身份库。

## 3. Contracts

### 协议与精确值

reverse 请求：

```json
{"version":1,"address":{"osm_id":-1,"osm_type":"node","lat":"48.858400123","lon":"2.294500456","context":{"outside_mainland":false}},"language":"en"}
```

lookup 把 `address` 改为 `addresses` 数组，逻辑批次最多 50 项。可选 `provider=amap|baidu|osm` 覆盖本次策略；缺省环境策略 `GEOCODER_PROVIDER=auto|amap|baidu|osm`、`MAINLAND_PROVIDER=amap|baidu`。语言 trim/lower。

context 必须有布尔 `outside_mainland`；可选 `source_osm_type/source_osm_id` 必须成对，只有两字段都缺失才表示没有来源；显式 null、单字段或错误类型拒绝，来源为 node/way/relation 与正 BIGINT。它们是验证后的官方来源，不能从客户端历史正数 hash 推导。永久 context 存在 `addresses.raw.georelay`，增加 `version: 1`；供应商切换有界合并保留来源与独立境外证据；请求已有来源时，响应缺省来源可沿用，响应另给不同 type/id 必须拒绝。`provider=osm` 本身不证明境外。

响应保持 Nominatim 形状，osm_id/type/lat/lon 与请求一致，并有 `georelay={version:1,...context}`。身份为负 node BIGINT，分配范围为 -1 至 -(2^63-1)。坐标为 canonical Decimal 字符串，不舍入；coefficient 与 exponent 各限 1024，输入最多 2050 字节，lat/lon 分别限 ±90/±180。请求体最多 65536 字节；应用按编码大小拆成不超过 60 KiB 的子请求，并在整个逻辑批次验证完成后返回，后续子请求失败不能写入此前结果。

### 所有权、并发与迁移

应用先按精确坐标复用负地址；新点先分配候选编号，在长数据库事务外解析，成功才入库。坐标唯一冲突时读回胜出行，返回与 raw 都使用胜出身份。序列允许失败空洞，不能回收已发出的编号。缺初始化、失败或非法响应不合成 Unknown；默认 Nominatim 的上游行为保持。

legacy 导入先核验全部证据、旧 PG/raw、坐标与来源；恢复可证原精度后建立唯一约束。保留地址 PK、负 ID、行程/充电 FK、正身份及 positions 原坐标。不同的高精度点不能按六位或邻近距离合并。高水位包含 SQLite 全部记录、未引用身份以及 `sqlite_sequence`；未引用记录不制造空白 PG 地址。单次导入原子提交，重复同一证据幂等；失败不能留下 marker 或半恢复。上游起终点独立解析和逐地址/跨批刷新边界仍保留。

新服务不读写旧 SQLite。旧库封存；新模式开始分配后，镜像降级不能恢复新增映射，回滚需匹配截止点的 PG/旧 SQLite 备份。不提供双写或静默六位 down migration。

### 缓存与供应商

`ADAPTER_CACHE_DB=/data/cache.sqlite3`；旧 `ADAPTER_DB` 明确拒绝。已有 identities 文件拒绝且不修改。只有 cache 表与 expires 索引；模板不含客户端身份/坐标，按精确点、语言、策略、来源/境外 context 分隔，响应时附当前请求身份。默认 TTL 86400 秒，每 60 秒最多删除 500 条过期记录，复用页面，无 VACUUM。缓存失效或整体删除不影响 PG 身份；TTL 不自动写回历史地址。

存储与返回始终 WGS84。仅 mainland AMap 请求临时 GCJ02；global AMap 与百度使用原 WGS84。GCJ矩形不能充当国界；框内大陆服务失败须用 OSM 国家/港澳 ISO 证据确认境外，不能静默把大陆失败视为 OSM 成功。香港澳门 `country_code=cn` 时识别 `CN-HK/CN-MO`。

AMap regeo 使用 `extensions=all`；名称依次取供应商排序首项 AOI、POI、建筑、小区、道路、完整地址，错误/空数组/非字符串规范化。name 与 namedetails.name 一致。OSM lookup 按可信 type/id 集合匹配，拒绝缺项/重复/额外项，同一来源可展开多本地身份；合法历史正身份跳过。公共 OSM 使用专用 User-Agent、缓存和同缓存路径的 flock，完成后及服务首次启动至少等待一秒。

网络默认 8 秒、无重试；reverse 总预算 min(25,2*timeout+1)，lookup 默认 20 秒、固定 4 线程共享 deadline。任意失败立即取消排队任务，成功仍按请求顺序返回；不能以输入顺序等待遮住后续失败。缓存可保留已成功模板，响应不可部分成功。

`NOMINATIM_BASE_URL` 只接受 HTTP/HTTPS origin，可含端口/尾斜杠，禁止 userinfo/path/query/fragment。Geocoder 与 size3 Finch pool 使用同一校验、保留 NOMINATIM_PROXY。`NOMINATIM_LOCAL_IDENTITIES_ONLY` 保持旧默认路径契约，application 独立启用新协议。AMAP_KEY/AMAP_KEY_FILE 互斥且只给 sidecar；其他 Key 同样禁止日志输出。

## 4. Validation & Error Matrix

| 条件 | 结果 |
| --- | --- |
| 非有限/越界/超精度坐标、重复 JSON key/负身份、超50项 | HTTP 400 |
| 旧 adapter GET reverse/lookup | HTTP 409，明确协议不兼容 |
| 合法正身份 lookup | HTTP 200，跳过；全正返回 [] |
| 非 node 负身份 | HTTP 422 |
| 缺配置、缓存不可用 | HTTP 503 |
| 上游失败/非法或错身份响应 | HTTP 502 |
| 网络、锁或整体预算耗尽 | HTTP 504 |
| 未显式初始化 PG | `:identity_store_not_initialized`，零地址写入 |
| application 网络错误 | `:geocoder_unavailable`，不写 Unknown |
| 缺项/额外/重复/坐标或 provenance 不符 | `:invalid_adapter_response`，不写地址 |
| fresh apply 无声明；PG 已有负身份 | `:fresh_install_assertion_required`；`:legacy_import_required` |
| legacy 证据缺失/冲突/重复/范围不符 | 固定 audit 错误，导入原子拒绝 |
| 已有有效缓存 | HTTP 200，不访问 provider，封装本次身份 |

## 5. Good / Base / Bad Cases

- Base：应用显式 fresh 初始化，-1 地址解析成功，重启/删缓存后沿用 -1 刷新。
- Good：旧 -10001/-10002 曾共用六位坐标，导入各自可证原精度后仍为两行；高水位 10010 后的新候选小于 -10010。
- Good：50 条境外语言刷新按来源批量查询，长坐标按 body 限制拆分，全部核验后更新。
- Bad：PG 空表自动判 fresh、从 -1 重启旧编号，或用六位坐标去重。
- Bad：provider 切换丢失来源、把 provider=osm 当境外、缓存模板夹带其他候选编号。

## 6. Tests Required

`tests/test_adapter.py` 验证协议、模板重用、删缓存/重启/TTL/清理、精度、语言/provider/港澳、50 项/同来源展开、限流、并发与总超时、真实 HTTP 状态和脱敏。`tests/test_legacy_identities.py` 验证只读/0600导出、sqlite_sequence/未引用高水位、证据冲突和精度边界。

`tests/test_upstream.py` 验证精确 pin、依赖补丁序列预检和冲突零应用。补丁内 ExUnit 覆盖默认 GET 与新 POST、精确 PG roundtrip、候选竞争、来源保留、显式初始化、原子导入、长 body 分拆失败不部分写与日志隐私。最终编译镜像通过 `scripts/test_main_image.sh` 的 fresh 和 legacy 两种 RPC 场景；本机 arm64 不代替云端 native amd64/arm64 证据。

## 7. Wrong vs Correct

错误：适配器重建永久编号；正确：PG 分配且请求携带，缓存可删除。

错误：初始化时先六位去重再恢复精度；正确：全部历史证据审计、精度恢复后建局部唯一索引。

错误：只改 Geocoder URL 或记录 POST body；正确：pool 共用校验，日志只固定类别。

错误：对 Decimal 使用默认精度运算比较边界；正确：使用精确 tuple/string/copy_abs 或 Decimal.compare，保持末位差别。

SQLite/导出含位置隐私，使用 backup API 或停机一致副本，不复制活动 WAL 主文件。测试只用合成公开数据；源码/镜像保留许可。stdlib HTTP 面向受信私网，非 root、无 host port。任何生产读取/迁移/真实 Key 验证需有当前任务授权。
