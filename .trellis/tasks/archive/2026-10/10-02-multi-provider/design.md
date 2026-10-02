# 设计

## 修改边界

行为缺口位于 adapter/server.py 的供应商选择、fetch、映射和 SQLite cache；必要文件为 server.py、对应 unittest、Compose/env 配置、中英文 README/指南和接口 spec。复用标准库、有界 HTTP 子进程、OSM 限流及永久身份，无插件框架。

## 接口与配置

GEOCODER_PROVIDER=auto|amap|baidu|osm，默认 auto；MAINLAND_PROVIDER=amap|baidu，默认 amap。请求参数仅接受 amap|baidu|osm，缺省使用配置。BAIDU_AK/BAIDU_SK 分别支持 _FILE 且同一项互斥；不记录密钥或完整请求。

百度标准 reverse_geocoding/v3/ 使用 coordtype=wgs84ll、location=lat,lon、output=json、extensions_poi=1。SN 签名用与 URL 相同的有序 urlencode query，quote_plus(path+?+query+SK,safe='') 后 MD5，sn 最后追加。成功 status=0 后规范化地址、行政区、街道、POI；海外权限属于用户应用。

## 路由与持久化

固定策略始终指定服务；auto 保留当前大陆服务优先、由 OSM 确認境外的失败边界。数学矩形不是国界，不把大陆服务失败静默替换为 OSM 大陆结果。高德 AMAP_API_REGION=mainland|global 默认 mainland；显式 global 使用官方海外 allowlist 域 sg-restapi.opnavi.com 和原 WGS84，不向新域自动转发国内 Key。mainland 固定模式只接受大陆结果；auto 全世界仍通过 OSM 支持，不把矩形等同国界。

身份仍只由规范化原 WGS84 分配。cache 增加 policy 维度，键为 identity/language/policy，auto:amap 和 auto:baidu 独立于固定服务。高德global profile再增加:global后缀，避免区域配置变化复用旧结果。事务迁移旧缓存到 auto:amap，不重建 identities。

source_osm_* 只记录可信来源，非 OSM 结果不能清空；新 outside_mainland 单独存自动路由确认，显式 osm 大陆请求不会污染 auto。旧 source 在原版本必为境外确认，可迁移此证据。OSM 批量 lookup 只刷新当前策略确实走 OSM 的身份，按请求来源集合校验；固定 osm 不要求境外，auto 仍要求。

## 回退与交付

保留现有期限、有效缓存和明确失败。仅新增服务分支，不动生产。数据库迁移需备份，旧版本无法理解新缓存键，回滚代码可丢弃文字缓存但永久映射必须保留。
