# 接口、数据与隐私

## 1. Scope / Trigger

适用于 adapter/server.py、patches/0001-nominatim-base-url.patch、Compose 和 CI 的跨层变更。地址服务不改 TeslaMate 数据坐标、客户端地图或生产数据库。

## 2. Signatures

- GET /reverse?lat=<WGS84>&lon=<WGS84>&format=jsonv2
- GET /lookup?osm_ids=N-1,N-2&format=jsonv2，最多50个本地身份。
- GET /health，只检测SQLite就绪。
- python3 -m adapter.server --backup DEST，SQLite在线备份，拒绝覆盖。
- identities 永久存 id/lat/lon 与可信OSM来源；cache 按 identity/language 存文字与 expires。

## 3. Contracts

原始WGS84 Decimal规范化不舍入；坐标→单调负 node ID 用事务/UNIQUE持久保存，不能hash。响应 osm_id/type/lat/lon 始终为本地身份和原坐标。TTL、语言、重启不变ID；永久OSM来源只接受成功固定官方请求返回的合法正身份。

大陆AMap请求临时GCJ02，境外OSM保留WGS84。GCJ矩形不能充当国界；框内AMap失败可由OSM国家/港澳ISO字段确认非大陆，不能把大陆AMap失败静默替换成OSM成功。香港澳门OSM可能country_code=cn，须识别 ISO3166-2-* 的 CN-HK/CN-MO。

OSM刷新按可信来源批量lookup，不盲转外部正ID。按type/id集合匹配而非zip；拒绝缺项/重复/额外项，同一来源展开多个本地身份。公共OSM用NOMINATIM_USER_AGENT、缓存与本地卷flock，每次完成后至少间隔1秒。

AMAP_KEY/AMAP_KEY_FILE只给sidecar且互斥；ADAPTER_DB永久卷；缓存默认86400秒；网络默认8秒，无重试；reverse总预算min(25,2*timeout+1)，lookup默认20秒。真实Key不属于自动测试。

NOMINATIM_BASE_URL是新增补丁变量，默认官方OSM。只接受HTTP/HTTPS origin，可含端口/尾斜杠；禁止userinfo/path/query/fragment。Geocoder和专用Finch pool调用同一校验函数，保留size3和NOMINATIM_PROXY。测试实际signed bigint负数入库，不只看Ecto类型。

## 4. Validation & Error Matrix

| 条件 | 结果 |
| --- | --- |
| 非有限/越界坐标、非法格式/重复参数/超50身份 | 400 |
| 本地身份或端点不存在 | 404 |
| 正数历史身份、非node负身份 | 422 |
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

tests/test_adapter.py 检查转换/原值、永久ID并发/TTL/重启/语言、地域错误边界、50项批量和同来源多身份、慢滴网络硬超时、HTTP状态/隐私、在线备份。tests/test_upstream.py 检查错pin/冲突fail closed；补丁内ExUnit验证默认/自定义URL、pool/proxy、负ID数据库roundtrip及错误不变Unknown。CI构建两个镜像并检查非root健康与许可。

## 7. Wrong vs Correct

错误：只改Geocoder BaseUrl；正确：与Finch专用pool共享经过校验的URL。
错误：缓存过期重分ID；正确：身份和来源永久存储，仅文字过期。
错误：记录完整请求/异常；正确：禁用访问URL日志，固定错误类别。
错误：把地图显示纠偏写回数据库；正确：只转换高德查询参数，保留WGS84。

SQLite含位置隐私，备份用backup API或停机复制，不复制活动WAL库。源码和镜像保留许可，不提交Key、车辆数据、运行配置/备份。stdlib HTTP只面向受信私网，非root且不开放host port。
