# 已确认的来源与最小决策

交接来源：官方 TeslaMate v4.3.0，commit 33d200b2fba9d5138803916a788cef5eae31b1aa；https://github.com/teslamate-org/teslamate/releases/tag/v4.3.0 。实现 worker 必须复核对应源码接口和测试。Geocoder 使用 BaseUrl，HTTP pools 独立写死 OSM，两者均需修改；`Unable to geocode` 会生成 Unknown，adapter 不得使用该消息。

AMap 官方 reverse API：https://lbs.amap.com/api/webservice/guide/api/georegeo 。固定 HTTPS `/v3/geocode/regeo`，请求 GCJ02，保留原 WGS84。v3 不保证任意 Accept-Language 翻译。境外走官方 Nominatim 原始 WGS84，正数旧身份不进行私版 hash 猜测。OSM 使用政策：https://operations.osmfoundation.org/policies/nominatim/ ，设置可识别 User-Agent、缓存并限制单实例每秒最多一次。

用户提供的手工交接已包含完整前序决策；本次以此和现场源码为依据，不扫描生产或旧日志。Python 标准库可覆盖 HTTP、SQLite、URL 和测试，无框架依赖。
