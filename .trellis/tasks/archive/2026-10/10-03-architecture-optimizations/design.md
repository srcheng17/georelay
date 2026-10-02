# 设计与边界

## 当前行为与缺口

lookup 对任何正身份报422，官方语言刷新因此中止整批。大陆本地身份串行回源，50条冷批次共享20秒；缓存已更新也不能让上游刷新 name/road/house_number/raw。prepare 只校验源码 pin 和补丁，无法识别法律原文变化。

## 最小改动

- adapter 在解析 lookup 后忽略合法正身份，返回其余请求的本地负身份；全正返回空列表。绝不猜测旧身份来源或访问上游正身份。不存在的本地负身份仍404、非法身份仍400/422。
- 复用 address 与 deadline，以标准库小型固定线程池并发本地刷新。可信 OSM 仍先批量请求，OSM flock保留。并发数固定保守上限，不增加任务框架或新配置。
- 最小 Locations 补丁扩充显式 refresh 写回字段；保留原坐标、身份和关联。上游会对lookup缺项执行reverse回退，故新增显式 NOMINATIM_LOCAL_IDENTITIES_ONLY=true：仅该模式跳过缺项正身份，不猜测自定义URL含义。缺省false保留官方及自定义OSM回退；true/false以外配置拒绝。默认OSM也受同一受测字段改进，reverse find_address行为不变。
- prepare 在checkout后、apply前逐字比较上游三个法律文件与仓库已复核原文；缺失或变更明确失败。人工更新原文后再继续正常pin更新流程。
- 将带日期 MODIFICATIONS 带入修改版镜像，保留上游法律原文。
- 文档在首页直接说明旧身份被跳过、TTL仅更新sidecar；备份使用实际stack参数，保留英文必要步骤。

## 分工与回滚

adapter/server.py 与 tests/test_adapter.py 由 adapter worker负责；patches 与 scripts/test_upstream.sh 由 upstream worker负责；prepare、upstream测试及通知携带由 release worker负责。根agent负责文档、规范、品牌选择及最终集成。每组独立测试后可git revert，不迁移生产库。品牌改动在选择明确后另列具体文件和公开资源范围。

## 已确认品牌范围

用户选择GeoRelay。仓库将改为srcheng17/georelay，两公开镜像为ghcr.io/srcheng17/georelay和georelay-adapter，版本后缀georelay；保留旧package。第三份小补丁替换用户可见标题/名称和品牌图标，保留上游模块名、数据库及MQTT标识以兼容既有数据。不修改原始法律文件。release worker额外拥有0003品牌补丁及最小品牌资产/检查；root统一发布引用。README保留现有amap-data卷名以免引导丢失永久身份，并说明旧stack更新名称时保留实际卷和project。
