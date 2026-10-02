# 高德逆地理编码与海外能力证据

核查日期：2026-10-02。仅读取官方公开文档、FAQ 及页面直接加载的公开内容；没有使用 Key、没有调用 geocode/regeo 数据接口、没有访问生产。

## 结论

用户在本次核查期间已明确选择：**大陆地址使用高德，境外使用 OSM**。这是产品路由决定；不应写成“高德不存在海外逆地理编码能力”。本任务按该决定推进，海外高德接入不再属于 MVP 范围。

不能把高德海外能力一概限定为 App 或底图：官方世界地图服务明确包含“正/逆地理编码”。也不能据此承诺普通个人 Web Service Key 的 `v3/geocode/regeo` 全球可用：官方海外接入说明要求企业开发者、申请开通，且不支持免费试用。

本次公开资料未明确解释海外权限与 `https://restapi.amap.com/v3/geocode/regeo` 的具体关系，未列出该 endpoint 的逐国家覆盖、地址细度或海外输入坐标系。因此“v3 必定只支持大陆”和“普通 Key 调 v3 即可全球使用”均缺乏足够证据。fork 把所有 reverse 请求发往高德，仅证明其路由实现，不能证明供应商实际覆盖与账户权限。

## 1. 当前 Web Service v3 文档

URL：<https://lbs.amap.com/api/webservice/guide/api/georegeo>

页面注明“最后更新时间: 2026年02月02日”。明确列出逆地理编码地址：`https://restapi.amap.com/v3/geocode/regeo?parameters`，GET；Key 为 Web 服务 API 类型。

原文摘录：

> 地理编码/逆地理编码 API 是通过 HTTP/HTTPS 协议访问远程服务的接口，提供结构化地址与经纬度之间的相互转化的能力。

> 注意：针对大陆、港、澳地区的地理编码转换时可以将国家信息选择性的忽略，但省、市、城镇等级别的地址构成是不能忽略的。暂时不支持返回台湾省的详细地址信息。

逆地理编码返回字段 `addressComponent.country` 的说明为“坐标点所在国家名称”，示例“中国”。这些文字未构成全球覆盖保证，也没有明确声明逆地理编码仅限大陆。文档中的“全国范围内”出现在**正向地理编码 city 参数**，不能自动套用为逆地理编码覆盖范围。

## 2. Web Service FAQ：海外权限需单独申请

URL：<https://lbs.amap.com/faq/webservice/webservice-api/basic-configuration/45900>

标题：“海外权限如何开通？”

> 海外服务需要申请开通高德海外LBS服务权限，关于海外服务相关说明请参考这里。

> 申请开通海外权限，请参考高德海外LBS服务申请须知，提交工单申请开通。

“这里”指向 `https://lbs.amap.com/getting-started/abroad`，当前重定向到 `/solution/abroad`。旧“申请须知”链接 `https://lbs.amap.com/faq/advisory/overseas-advisory/40515` 本次返回 HTTP 404；未用失效页面推断现行要求。

## 3. 当前海外产品接入 FAQ

URL：<https://lbs.amap.com/faq/overseas/1000038285/1060253384>

由官方当前 FAQ 的“海外”→“产品接入”索引 `/faq/overseas/1000038285` 链接，标题：“国际化产品接入-官网版本”。

> 申请海外LBS服务，需先认证成为高德地图企业开发者。

> 请提交工单申请海外LBS服务，试用期间每个平台限一个Key。

> 海外LBS服务不支持免费试用。

该页同时写一般 2 个工作日内可完成审批，线上使用需联系海外商务负责人。未提供本项目可直接调用的海外 endpoint、Key 权限或计费承诺。

相关商务 FAQ：<https://lbs.amap.com/faq/advisory/overseas-advisory/46724>，说明测试用量不能满足上线需求时可通过工单获取报价。两个页面的试用措辞不完全一致；不能据旧商务页宣称免费试用，具体开通方案需以供应商确认结果为准。

## 4. 世界地图服务确实包含正/逆地理编码

URL：<https://lbs.amap.com/solution/abroad>

官方页面文字：“面向开发者提供全球范围内LBS服务”。其当前页面直接加载的内容配置中：

> 地图覆盖全球 200+ 个国家和地区，超 1.2亿 海外 POI 总量

“核心功能”栏目含：

> 正/逆地理编码

这属于高德开放平台世界地图服务介绍，不能缩窄为消费者 App 功能；也不能把世界地图整体宣传的国家数自动当成 v3/regeo 的逐国家保证。

内容来源链：页面 HTML → `https://g.alicdn.com/legao-comp/abroad_new/1.3.0/web.js` → `https://g.alicdn.com/legao/abroad_new/1.3.0/env-release-faa8cbff-beb3-4b7f-ad25-55e37655974d/FORM-9J766LD1-OT9LRKZ1EU8UA7595MGZ2-C0HHYIXL-G7__nav.js?t=1i0qc4ja2`。本次直接读取页面所引用的公开配置文本，没有执行其中脚本；没有把其他无关库字符串当成产品说明。

## 仍待验证

- 开通海外权限后，是否继续使用同一 Web Service v3 regeo endpoint、是否需要独立 Key 或参数。
- 所需国家/地区的地址精细度、语言、输入坐标系和商业费用。
- 用户现有 Key 是否已获对应权限。本次没有读取或请求该 Key。

这些应作为供应商接入确认与获得授权后的非生产真实 Key 验证；不应以猜测写成硬编码产品边界。
