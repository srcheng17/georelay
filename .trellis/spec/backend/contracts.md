# 接口、数据与隐私

## 1. Scope / Trigger

适用于 adapter/server.py、patches/0001-nominatim-base-url.patch、Compose 和 CI 的跨层变更。地址服务不改 TeslaMate 数据坐标、客户端地图或生产数据库。

## 2. Signatures

- GET /reverse?lat=<WGS84>&lon=<WGS84>&format=jsonv2
- GET /lookup?osm_ids=N-1,N-2&format=jsonv2，最多50个本地身份。
- reverse/lookup 的 provider=amap|baidu|osm 覆盖单次请求；缺省使用 GEOCODER_PROVIDER=auto|amap|baidu|osm，MAINLAND_PROVIDER=amap|baidu。
- GET /health，只检测SQLite就绪。
- python3 -m adapter.server --backup DEST，SQLite在线备份，拒绝覆盖。
- identities 永久存 id/lat/lon、可信OSM来源与独立outside_mainland自动路由证据；cache 按 identity/language/policy 存文字与 expires。

## 3. Contracts

原始WGS84 Decimal规范化不舍入；坐标→单调负 node ID 用事务/UNIQUE持久保存，不能hash。响应 osm_id/type/lat/lon 始终为本地身份和原坐标。TTL、语言、重启不变ID；永久OSM来源只接受成功固定官方请求返回的合法正身份。

自动策略大陆AMap请求临时GCJ02或百度原WGS84，境外OSM保留WGS84。GCJ矩形不能充当国界；框内AMap失败可由OSM国家/港澳ISO字段确认非大陆，不能把大陆AMap失败静默替换成OSM成功。香港澳门OSM可能country_code=cn，须识别 ISO3166-2-* 的 CN-HK/CN-MO。

AMap regeo请求 `extensions=all`。name优先 `regeocode.aois[0].name` → `pois[0].name` →建筑→小区→道路→完整地址；缺失/空数组/非字符串须规范化，详情列表及首项错误结构不得异常。只取供应商排序的首项，不遍历任意周边地点。`name` 与 `namedetails.name` 一致，不能用道路替代已返回的AOI/POI。文字随TTL正常刷新，身份不变。

OSM刷新按可信来源批量lookup，不盲转外部正ID。按type/id集合匹配而非zip；拒绝缺项/重复/额外项，同一来源展开多个本地身份。合法正数历史身份在外部lookup跳过，不访问OSM；全正返回空列表。公共OSM用NOMINATIM_USER_AGENT、缓存与本地卷flock，每次完成后至少间隔1秒。

AMAP_KEY/AMAP_KEY_FILE只给sidecar且互斥；ADAPTER_DB永久卷；缓存默认86400秒；网络默认8秒，无重试；reverse总预算min(25,2*timeout+1)，lookup默认20秒。lookup复用address以固定4线程并发，共享deadline；FIRST_EXCEPTION观察任意项失败并取消排队任务，不能按输入顺序等待而遮住后续失败。成功结果仍按输入顺序返回；OSM限流不放宽。真实Key不属于自动测试。

NOMINATIM_BASE_URL是新增补丁变量，默认官方OSM。只接受HTTP/HTTPS origin，可含端口/尾斜杠；禁止userinfo/path/query/fragment。Geocoder和专用Finch pool调用同一校验函数，保留size3和NOMINATIM_PROXY。测试实际signed bigint负数入库，不只看Ecto类型。

NOMINATIM_LOCAL_IDENTITIES_ONLY严格true/false，缺省false保留默认及自托管OSM缺项reverse回退；连接本adapter时设true。true模式缺少本地负身份明确失败，跳过缺项正身份。显式refresh写回name/road/house_number/postcode/raw及行政字段，保持数据库id/osm身份/坐标/关联；sidecar TTL不自动更新PostgreSQL，find_address同身份复用逻辑不变。

## 4. Validation & Error Matrix

| 条件 | 结果 |
| --- | --- |
| 非有限/越界坐标、非法格式/重复参数/超50身份 | 400 |
| 本地身份或端点不存在 | 404 |
| 合法正数历史身份 | 200，跳过；全正返回[] |
| 非node负身份 | 422 |
| 缺配置、SQLite不可用 | 503 |
| 上游失败/非法或错身份响应 | 502 |
| 网络、锁或整批预算耗尽 | 504 |
| 有效缓存 | 200，不再访问provider |
| 缓存过期且刷新失败 | 明确非200，不生成Unknown |

## 5. Good / Base / Bad Cases

- Base：大陆坐标发GCJ02给AMap，SQLite和返回保持WGS84。
- Good：50条境外语言刷新只需一次批量OSM请求，重启后仍是原负ID。
- Bad：仅凭bbox把首尔/新加坡认作大陆；或用OSM country_code=cn把港澳误认成大陆。
- Bad：把私人fork正数hash当成真实OSM对象，或将额外上游身份写回客户端。

## 6. Tests Required

tests/test_adapter.py 检查转换/原值、永久ID并发/TTL/重启/语言、地域错误边界、50项批量和同来源多身份、慢滴网络硬超时、HTTP状态/隐私、在线备份。tests/test_upstream.py 检查错pin/冲突fail closed；补丁内ExUnit验证默认/自定义URL、pool/proxy、负ID数据库roundtrip及错误不变Unknown。影响镜像的改动及手动验证执行双架构镜像构建、非root与适配器健康检查；轻量改动仍须通过Python与verify检查，具体发布/保留契约见quality-guidelines.md。

名称回归用虚构AOI/POI验证优先级与缺失fallback，并由本地HTTP测试实际请求参数确认 `extensions=all`；不能只mock详细响应而漏掉真实请求参数。

## 7. Wrong vs Correct

错误：只改Geocoder BaseUrl；正确：与Finch专用pool共享经过校验的URL。
错误：缓存过期重分ID；正确：身份和来源永久存储，仅文字过期。
错误：记录完整请求/异常；正确：禁用访问URL日志，固定错误类别。
错误：把地图显示纠偏写回数据库；正确：只转换高德查询参数，保留WGS84。

SQLite含位置隐私，备份用backup API或停机复制，不复制活动WAL库。源码和镜像保留许可，不提交Key、车辆数据、运行配置/备份。stdlib HTTP只面向受信私网，非root且不开放host port。

多服务共用永久坐标身份，文字缓存按 auto:mainland_provider 或固定服务隔离，高德global profile再增加:global后缀。旧cache事务迁移至auto:amap，旧可信OSM来源按原版本契约可迁移为境外证据；显式OSM大陆请求不设置outside_mainland。source_osm只表示可信对象来源，不作为地域判断，非OSM结果不清空。固定OSM允许大陆，批量lookup仍核对请求集合。

百度标准reverse_geocoding/v3/使用coordtype=wgs84ll；SN按实际URL相同query顺序签名，quote_plus(path+?+urlencode(query)+SK,safe='')后MD5，sn最后追加。AK/SK各支持环境变量和_FILE互斥；不使用高德JS安全密钥。AMAP_API_REGION=mainland|global 显式选择固定官方域与坐标系；默认mainland请求restapi.amap.com GCJ02并只接受大陆，global请求sg-restapi.opnavi.com原WGS84，需要配套服务Key。不自动将国内Key转发新域；auto境外仍OSM。不把GCJ矩形等于国界。固定海外服务依赖用户应用权限。
