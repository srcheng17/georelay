# 设计与边界

## 数据流与坐标

固定官方源码→Geocoder/Finch 共用的 NOMINATIM_BASE_URL→私网 sidecar→AMap/OSM→独立 SQLite；TeslaMate PostgreSQL 及其读取者职责不变。

原始 WGS84 以 Decimal 数值等价文本规范化，不舍入；SQLite、响应、轨迹保持原 WGS84。仅 AMap regeo 请求临时 GCJ02。客户端已有地图纠偏，不重复改客户端坐标。

## 已确认路由

用户明确选择大陆高德、境外 OSM。GCJ02 bbox 仅作快速排除；框内先请求 AMap，只有明确大陆省级地址才采用。AMap失败/无Key/不能判断时，OSM用于确认：有效 country_code 非cn，或 ISO3166-2-* 为 CN-HK/CN-MO，才接纳为非大陆；如果OSM确认大陆，则保留原AMap错误。由可信 OSM 响应获得的来源持久化，以后同身份直接OSM。首次查询可能探测两个服务，不宣称精确国界几何判断。

公共 OSM 固定官方 HTTPS endpoint，配置可识别 User-Agent；本地卷 flock 串行请求，完成后至少间隔1秒，缓存避免重复调用。只部署一份服务实例，不用于批量采集。上游不接受任意目标URL、不转发Key至OSM、不跟随重定向。

## 永久身份与批量刷新

identities 存原始坐标、单调正内部序号（对外负node ID）及可信OSM来源；cache 按身份和语言存文字、过期时间。事务/UNIQUE保证并发稳定。身份不能随TTL删除，OSM来源不能只藏在可删除的缓存里。

lookup 先校验全部本地 N-<id>，外部正数历史身份不盲代理。失效OSM项用持久来源去重后调用官方批量lookup（最多50），按type/id集合匹配，拒绝额外/重复/缺失结果；再展开回各本地负ID和原WGS84。同一OSM对象可对应多个本地坐标。整批响应不返回部分成功列表；失败前已成功缓存可保留。

## 时间与错误

单次网络默认8秒（最大20），reverse总预算 min(25,2*timeout+1)，lookup整批默认20秒（最大25），均小于官方30秒。网络子进程保证DNS/慢滴响应也受墙钟预算控制，Key仅经stdin传入；无自动重试。SQLite等待、OSM锁等待/限流计入总预算。

400非法输入；404身份/端点不存在；422不支持历史身份；503缺配置/存储不可用；502上游失败/不合法响应；504预算超时。固定错误正文不反射上游异常、坐标或Key，不使用会触发官方Unknown的特殊串。

## 构建、许可与恢复

upstream.json固定稳定tag/commit，临时checkout核实commit后严格apply；保留官方LICENSE/NOTICE，不复制完整上游进仓库。CI对PR进行检查和镜像构建。release检测只提议pin，手动main发布版本标签，不提升stable、不部署。

容器非root、无host port，SQLite永久卷。health只验证本地就绪。使用SQLite backup API；恢复需停sidecar并保证与TeslaMate引用的负ID一致。丢映射库不能直接重建继续用。

## 来源结论

mytesla旧实现按Key优先级选provider且无地域分流，不证明普通Key全球可用。高德官方海外服务存在且需申请权限，详见 research/amap-coverage.md；本项目选择OSM是用户产品决定，不是高德能力不存在。
