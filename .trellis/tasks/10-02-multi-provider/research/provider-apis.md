# 多供应商接口核对

核对日期：2026-10-02。只读检查官方技能、接口文档和现有 `adapter/server.py` / `tests/test_adapter.py`；未调用用户凭据、未访问生产数据。

## 来源

- 高德技能：[AMap-Web/amap-skills](https://github.com/AMap-Web/amap-skills/tree/0e544c2c46846d9e5b726efe9e78fe87252b7e29)，commit `0e544c2c46846d9e5b726efe9e78fe87252b7e29`。实际提供 `amap-jsapi-skill`，面向浏览器 JSAPI 2.0；核对其 `SKILL.md`、`references/security.md`。
- 百度技能：[baidu-maps/webapi-skills](https://github.com/baidu-maps/webapi-skills/tree/67d85191b91755b447088ee8c492a3fb54d99e8b)，commit `67d85191b91755b447088ee8c492a3fb54d99e8b`。核对 `skills/baidu-map-webapi/SKILL.md`、`references/global_reverse_geocoding.md`、`recipes/coordinate_to_structured_address.md`。
- 百度当前接口文档：[全球逆地理编码 V3](https://lbs.baidu.com/docs/webapi?title=reverse_geocoding/guide/webservice-geocoding-abroad-base)。页面正文已直接读取。
- 百度签名：[附录 / sn 计算算法](https://lbs.baidu.com/index.php?title=webapi/appendix)。页面当前 Java 参考实现及参数顺序说明已直接读取。
- 高德接口：[地理编码 / 逆地理编码](https://lbs.amap.com/api/webservice/guide/api/georegeo)。页面全部逆地理编码请求参数已直接读取。
- 高德签名：[如何添加数字签名](https://lbs.amap.com/faq/quota-key/key/41181/)。页面正文已直接读取。

## 百度请求与签名

标准服务为 `GET https://api.map.baidu.com/reverse_geocoding/v3/`，不用技能中的高级功能体验端点 `/map_service/`。`location` 顺序是 **纬度,经度**，与高德相反。

最小查询参数：`ak`、`location=<原始WGS84纬度>,<原始WGS84经度>`、`coordtype=wgs84ll`、`output=json`、`extensions_poi=1`。需要 `pois[].aoi_name` 时增加 `entire_poi=1`；可显式指定 `sort_strategy=distance`、`radius=1000` 保持附近结果的排序和半径明确。输入 WGS84 由百度自行转换，不需要本项目增加 BD09 转换。响应 `result.location` 默认是 BD09，不能写回本地身份或 Nominatim 响应坐标。

SN 必须使用这个 AK 对应的百度 SK。仅把 AK/SK 送给百度请求过程，不能混用高德安全密钥。

GET 的参数无需按字母排序，但签名中的顺序必须与实际 URL 完全相同；`sn` 放在最后。官方仅要求 POST 使用字母排序。可以为了确定性把 GET 参数排序，但必须签和发同一份查询字符串。

与官方 Java 参考实现一致的 Python 标准库实现：

```python
query = urllib.parse.urlencode(ordered_pairs)
raw = "/reverse_geocoding/v3/?" + query + sk
sn = hashlib.md5(urllib.parse.quote_plus(raw, safe="").encode("utf-8")).hexdigest()
url = "https://api.map.baidu.com/reverse_geocoding/v3/?" + query + "&sn=" + sn
```

`raw` 不包含 scheme/host，包含 endpoint 的尾斜杠和问号；`sk` 直接拼在 query 后面，不增加 `&`。第一次 `urlencode` 编码参数值（逗号 `%2C`、空格 `+`、字面 `+` `%2B`）；第二次 `quote_plus(..., safe="")` 编码整个路径+query+SK，已经出现的 `%` 变成 `%25`。不要在生成 SN 后重排参数或对整份 URL 再编码。Python 仍保留 RFC 的非保留字符；本项目实际参数是字母、数字、下划线、短横线、点、逗号，不涉及语言库间特殊字符差异。

官方示例已在本地执行断言通过：有序参数 `address=百度大厦`、`output=json`、`ak=yourak`，路径 `/geocoder/v2/`，SK 为公开示例 `yoursk`，结果 `7de5a22212ffaa9e326444c75a58f9a0`。可把此公开测试向量纳入代码测试，无真实凭据。

逆地理编码不要求路线 API 的 `timestamp`，不应从其他技能接口照搬。

## 百度响应、覆盖和语言

- 成功为整数 `status=0`；非零表示参数、鉴权、权限、配额或服务失败。避免用松散布尔判断接受 `False` 等畸形类型。
- `result.formatted_address` 是标准地址；`formatted_address_poi` 是含 POI 的详细地址，需要 POI 扩展。至少要求有效地址文本后再保存结果。
- `addressComponent` 提供 `province`、`city`、`district`、`town`、`street`、`street_number`、`country`、`country_code_iso2`、`adcode`。国外同名字段代表行政层级，不保证当地行政类型。
- city 可能为空，直辖市可复用 province；普通省辖县不要把省名当城市。
- 面名称为 `result.poiRegions[0].name`，周边地点为 `result.pois[0].name`；`pois[0].aoi_name` 仅 `entire_poi=1` 时可返回。沿用已有名称原则：仅取供应商排序首项，规范化空值/数组/非字符串；可以采用首个 poiRegion 名称 → 首个 POI 名称 → 道路 → 地址文本。`name` 与 `namedetails.name` 保持一致。
- 国家代码可从 `country_code_iso2` 转为小写两位代码；`country_code` 数字不是 ISO 两位代码。
- 大陆确认应独立于文字语言。可组合 `country_code_iso2=CN` 与有效大陆 `adcode` 省级前缀，或现有中文大陆省名白名单；不能把 CN 一概当大陆，港澳/台湾不能进入默认大陆 provider。若使用 adcode，白名单为 `11,12,13,14,15,21,22,23,31,32,33,34,35,36,37,41,42,43,44,45,46,50,51,52,53,54,61,62,63,64,65`；不要靠 `!=81/82` 接受任意未知代码。
- 境外逆地理编码是高级服务，需商用授权后申请开通；个人标准 AK 不能被假定有海外权限。默认自动策略继续境外 OSM。
- 默认国内 zh-CN、海外 en；繁体代码 `cht`。英文/其他语言翻译需要额外高级权限。Accept-Language 不能完整原样放到 `language`：应提取首选语言并映射 `zh-cn/zh-hans` 到 `zh-CN`、繁体变体到 `cht`，其他支持语言到基础代码，未支持的语言可省略以使用供应商默认值。不要承诺标准 AK 能返回所有语言。

## 高德 Key、安全密钥和 fixed 海外方案

高德 regeo 明确要求 **Web 服务 API 类型 Key**。已安装技能是浏览器 JSAPI 技能，其中 `securityJsCode` / `jscode` 是 JSAPI 安全机制，不能自动视为 REST 签名私钥，也不能因用户给了 JS 安全密钥便自动附加到 sidecar 请求。

REST `sig` 是另一种可选机制，须在相应 Web 服务 Key 设置中开通并取得该 Key 的私钥。算法为对未 URL 编码的所有请求参数（包括 key，不包括 sig）按参数名升序，以 `a=x&b=y` 拼接，末尾直接拼接私钥，再对 UTF-8 字节 MD5。之后正常 URL 编码并增加 sig。官方特别说明字面 `+` 参与正常签名，发送时才 URL 编码。当前未授权具体 Web 服务数字签名配置时继续仅使用 Web 服务 Key，不猜测用户提供的密钥类型。

当前 regeo 文档列出 `key,location,poitype,radius,extensions,roadlevel,sig,output,callback,homeorcorp`，**没有 `coordsys`**。不能用未证实的 `coordsys=gps` 或从坐标转换服务借参数。文档要求 location 经度在前，并提示不超过 6 位小数；永久本地坐标仍保留完整原始 WGS84，不应因请求格式变化而舍入身份。

固定 amap 若支持海外，现有数学矩形会让首尔/东京也执行 GCJ02。无需另外要求 OSM User-Agent 的最小方案为：

1. 框外直接以原始 WGS84 查询高德一次。
2. 框内先以 GCJ02 查询；只有有效响应明确大陆时直接采用。
3. 有效响应明确非大陆时，以 **原始 WGS84** 对同一高德 endpoint 再查一次；不切换服务，不需要 OSM。只有第二次仍明确非大陆时采用第二次结果。
4. 第一次失败（如未开海外权限）明确失败；两次覆盖判断不一致则明确失败，不静默回退或保存可疑结果。

此方案是当前矩形/行政字段启发式的有界延伸，不能声称解决精确国界：距边界数百米时，首次 GCJ 偏移可能跨界而被错误标成大陆。若未来要求这种边界精度，再引入有来源的覆盖边界数据；本轮注明限制即可。高德海外支持仍受实际 Key 权限限制。固定 amap 的文字映射必须使用上游 `addressComponent.country`，不能沿用现有无条件 `country=中国,country_code=cn`；无法确认 ISO 两位代码时可以省略，不能编造。

## 最小代码影响和契约

- `fetch` 增加百度请求/签名分支，仍复用无重定向、无环境代理、MAX_BODY 和可终止子进程。凭据经 stdin 传递，不能放 argv 或异常日志。高德第二次 WGS84 查询需要明确内部参数以绕过 GCJ02，不能暴露任意 upstream URL。
- `Adapter` / `main` 增加 `GEOCODER_PROVIDER=auto|amap|baidu|osm` 与 `MAINLAND_PROVIDER=amap|baidu`；百度配置建议 `BAIDU_AK[_FILE]`、`BAIDU_SK[_FILE]`，单份凭据 env/file 互斥。缺当前服务所需配置时明确 503，不要求不使用的服务也配置 Key。
- HTTP `provider` 可取同样四值；不存在时使用 env，显式 `auto` 使用自动地域策略。显式固定服务不被境外自动路由覆盖，非法/空白/重复参数 400。
- `reverse` / `lookup` 调用相同策略选择函数，使语言刷新和重新逆解析一致；lookup 仍仅接受已存在的私有负身份，不转发任意正数历史身份。
- 永久 `identities UNIQUE(lat,lon)` 不变；跨 provider、TTL、重启、语言切换仍使用同一负 node ID。
- cache 主键应包含 identity、language 和请求策略：`auto:amap`、`auto:baidu`、`amap`、`baidu`、`osm`。旧缓存可迁移到 `auto:amap`，或只丢弃可过期缓存；永久身份与源不能重建。显式 auto 与 env 默认 auto 可共享；固定 osm 不能复用 auto 缓存。
- 现有 `source_osm_type/id` 只作可信 OSM lookup 来源，**不再充当地域判定条件**。新增独立 `outside_mainland` 合理：旧版所有非空可信 OSM source 都满足海外确认契约，只在添加该列的迁移中初始化为 true；以后只根据有效覆盖字段更新，不能每次启动再把全部非空 source 标 true。
- 固定 OSM 可以解析大陆。保存其合法来源时不把 `outside_mainland` 标 true；其 source 不应导致后续 auto 跳过大陆 provider。固定 amap/baidu 成功时不必清空此前合法 OSM 来源；来源和最近文字供应商是不同概念。
- 批量 OSM 刷新只用于该请求策略实际选 OSM 的身份（固定 osm，或 auto 且独立海外确认为真），fixed amap/baidu 不应触发此刷新。匹配请求 type/id 集合的原有检查保留，auto 的 OSM 返回仍须确认非大陆；固定 OSM 不作此覆盖拒绝。

必要验证：官方 SN 公开向量与实际 mock HTTP query；百度 WGS84 原值和响应 BD09 不写回；env/request 四策略与非法参数；同点三供应商身份一致且缓存隔离；forced OSM 大陆之后 auto 仍使用大陆服务；旧 source/缓存迁移与重启；AMap 两阶段海外发送坐标及不一致覆盖失败；百度错误/语言/POI空值；原有 lookup 身份集合、预算、日志隐私回归。

## 技能的实际价值

百度技能直接适用，可减少接口、坐标顺序、权限、POI 和状态码错误；SN 仍需直接官方附录补充。高德技能主要适用于未来独立浏览器地图工作，对当前 Python sidecar 不需要引入 Loader、JS 代理或埋点；有价值的是理解 Key 类型与 JS 安全机制，避免把它与 REST 签名混用。两者均为开发参考，不需要成为镜像运行依赖。

## 更新：官方 REST 替代技能及海外服务分区

用户随后要求卸载 JSAPI 技能、查找更适合服务端开发的官方技能；本节只读核对，不安装替代技能、不执行其工作流、不使用其公共促销 Key。

找到同一官方组织维护的 [AMap-Web/amap-map-agent-skills](https://github.com/AMap-Web/amap-map-agent-skills/tree/cd14d34ff00340db8958623555b6da2ff070fdb2)，当前固定 commit `cd14d34ff00340db8958623555b6da2ff070fdb2`，默认分支 main。完整读取：

- [`skills/amap-map-google-maps-migration/SKILL.md`](https://github.com/AMap-Web/amap-map-agent-skills/blob/cd14d34ff00340db8958623555b6da2ff070fdb2/skills/amap-map-google-maps-migration/SKILL.md)，version 1.0.0。
- [`references/web-api-params.md`](https://github.com/AMap-Web/amap-map-agent-skills/blob/cd14d34ff00340db8958623555b6da2ff070fdb2/skills/amap-map-google-maps-migration/references/web-api-params.md)，覆盖 14 个 REST API，并含第 7 节逆地理编码的参数和响应字段映射。

这是比 `amap-jsapi-skill` 更匹配当前 sidecar 的官方开发参考，尽管整体主题是从 Google Maps 迁移，且同时含 JS/mobile 内容。它提供接口域名、坐标顺序、返回结构和多语言约定。另一个 `amap-lbs-skill` 偏综合 LBS 功能执行，此次不将其安装或执行。

### 新证据与此前海外方案的修正

技能明确区分服务分区：

| 服务分区 | Web API 域名 | 坐标系 | 逆地理编码路径 |
| --- | --- | --- | --- |
| Mainland（技能的服务分区含 HK/MO/TW） | `https://restapi.amap.com` | GCJ02 | `/v3/geocode/regeo` |
| Non-Mainland（技能的服务分区不含 HK/MO/TW） | `https://sg-restapi.opnavi.com` | WGS84 | `/v3/geocode/regeo` |

两个接口都以经度,纬度传 `location`；海外 regeo 支持 `langCode`，映射文档说明 20 多种语言。返回仍为 `regeocode.formatted_address` 与 `regeocode.addressComponent`，可复用文本映射。搜索/正向地理编码的海外 `city`/adcode 要求不能直接照搬给 regeo：第 7 节逆地理编码没有列出必填 city。

**修正此前“同 restapi.amap.com endpoint 二次发送 WGS84”的建议：它只是未经海外接口证实的启发式，不能被描述为官方支持的全球逆解析实现，也不应继续作为 fixed amap 的全球能力依据。** 官方新技能提供了专门海外域与 WGS84 约定。当前国内 regeo 没有 coordsys 参数的结论仍成立。

技能是按开发者/服务分区选择域名，并非提供精确坐标边界或按坐标自动路由算法；它将港澳台归国内服务分区，这与本项目已选的 auto 大陆服务、其他地区 OSM 是不同概念。不能拿数学 GCJ 矩形套它的服务分区，更不能因此改变本项目已确认的默认地域策略。

技能内公共促销 Web Service Key 宣称覆盖两种分区，只代表该公开测试 Key 的权限；**不能由此推断用户个人 Web 服务 Key、JS Key 或安全密钥也支持海外域**。研究输出已滤掉所有促销 Key，没有调用。官方海外门户 `https://mapsplatform.opnavi.com/` 及其 `/docs` 在本次环境无法连接，故海外分区结论当前来自上述固定官方 GitHub 技能，尚未经门户正文或实际专属 Key 验证。

### 最小产品建议

- 保留当前 auto 地域策略；fixed 服务的选择与地理覆盖、Key 权限分开说明，不把 fixed amap 文档写成现有个人 Key 必然能解析全球。
- 在正式增加海外 AMap profile 时，用固定允许列表中的官方海外域、WGS84 和适合该服务的专属 Key；不开放任意 URL，不从 HTTP provider 参数推导或接收 URL。境外域不要误走现有 gcj02 分支。
- 国内 profile 保持国内接口坐标约定；海外 profile 必须用原 WGS84。若需要二阶段探测，第二阶段也应采用经过配置/权限确认的海外 profile，而非同域换坐标后将成功文本当全球正确性证明。
- 只加最小域名/profile 能力即可，复用现有超时、错误、文本映射和身份缓存；不引入 JS Loader、Google Maps 迁移层、14 API 包装或公共促销 Key。
- 留下 mock HTTP 检查域名、原 WGS84/GCJ02 参数和缓存隔离。真实海外能力必须用用户专属 Key 的脱敏联调确认；在这之前不声称已完成全球 AMap 验证。

已把新证据及对同域二次查询的修正同步给 root 和 provider_implement；本研究不修改产品代码或部署配置。
