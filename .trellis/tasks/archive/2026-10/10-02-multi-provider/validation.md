# 验证记录

2026-10-02。仅开发隔离环境，无生产部署或数据写入。

## 本地与独立审查

- 全仓 55 项 Python 标准库 unittest 通过，其中 adapter 31 项；包含官方百度 SN 向量、实际本地 HTTP 编码、策略与 API region 缓存隔离、旧 SQLite 事务迁移、OSM 来源/地区证据分离、TTL、重启与语言切换。
- 独立 provider reviewer 复跑全仓 55 项，通过 Python AST、Shell 语法及 git diff --check；无阻断发现。未配置静态类型检查器。
- 双语 README YAML 相同，48 个本地链接/锚点有效；假基础 stack 的 Compose 合并保留原环境、端口和卷，adapter 同网无 host port。4 份文档通过 GitHub GFM 渲染。
- 可达 Git 历史 439 对象及当前 181 文件对用户提供的开发凭据精确扫描无匹配；新个人高德 Key 对当前文件的追加扫描无匹配。

## 真实 API

随机 Docker 网络、独立临时 SQLite 卷、只读根文件系统、UID 10001，无 host port。凭据只经 stdin 写入 tmpfs 0600 文件，不放 argv/env，不保留响应或数据库。

- 百度用户开发 AK/SK 的标准 REST 请求 status=0，真实 SN 验证通过。
- 首次高德开发 Key 返回平台类型不匹配代码 10009；未将其 JS 安全密钥混用为 REST 签名。
- 按此前用户授权，仅从 Dockhand 原生读取变量名/状态；凭据被遮蔽后宿主机只读提取 recorder 的单个高德变量，直接经 stdin 送入测试 tmpfs。此 Web 服务 Key 成功，未改生产配置。与百度、OSM 组成 13 项完整联调：reverse、lookup、provider 切换、TTL、同库重新打开、原坐标/身份、大陆 OSM 不污染 auto 路由以及巴黎 auto OSM，全部通过。
- 用户随后重新申请的个人 Web 服务 Key 返回 status=1、infocode=10000；北京/杭州公共地标 reverse、英文 lookup、过期刷新、同库重新打开、非 root/0600，共 7 项检查全部通过。仅用于个人测试，不写入产品配置或仓库。
- 测试容器日志为空，全部临时容器/网络/卷/镜像标签删除，tmpfs 凭据随容器清理。生产 recorder ID、镜像、启动时间和 restart count 前后一致。

## 技能与限制

旧 amap-jsapi-skill 按用户要求卸载；新官方 REST 技能 amap-map-google-maps-migration 固定 cd14d34ff00340db8958623555b6da2ff070fdb2，4 个文件与官方 Git blob 字节一致，Codex 实际发现一次。百度技能固定 67d85191b91755b447088ee8c492a3fb54d99e8b 保留。技能位于用户 canonical catalog，不复制进本仓库或镜像；原版扩展 frontmatter 的 validator 例外已在私有安装报告如实记录。

高德海外域仅验证固定 host、WGS84 与 cache 隔离的模拟路径；本次个人国内 Key 没有转发海外域，不声称真实海外权限通过。AMap/Baidu 使用服务默认语言；地区确认仍有矩形/行政字段启发式限制，公共地标样本不代表全境覆盖。

## 2026-10-03 CI 与发布续验证（Asia/Shanghai）

[PR #1](https://github.com/srcheng17/teslamate/pull/1) 已按保护流程合并，镜像源码 commit 为 `8f4efa1df503d5a25540d9185fb19ddcbd949d32`。共同发布版本为 `v4.3.0-amap-8f4efa1df503d5a25540d9185fb19ddcbd949d32`。

- [PR CI 37029365291](https://github.com/srcheng17/teslamate/actions/runs/37029365291)：amd64、arm64 build 与 verify 成功，publish 按 PR 事件条件跳过。
- [main CI 37029960665](https://github.com/srcheng17/teslamate/actions/runs/37029960665)：两个架构 build、verify、publish 全部成功；两个 package 的浏览器页面均确认 Public。
- 两版本索引恰含 `linux/amd64`、`linux/arm64`；四个 child manifest 的 OCI source/revision/version 均一致，空临时 Docker config 的四次实际匿名拉取与本地架构/标签回读全部通过。两个索引及四个 child digest 见[镜像发布验收](../10-02-images-release/validation.md)。验证用镜像 references 已清理。
- [updater 37030399601](https://github.com/srcheng17/teslamate/actions/runs/37030399601) 成功，artifact 为 `status=current`，官方 `v4.3.0` pin 保持不变。未来新稳定版的更新 PR 和自动发布路径由模拟测试证明，本次实际 updater 是相同版本 noop。

未部署生产，未修改生产数据库或 Dockhand stack；高德海外权限仍仅有上述模拟验证范围。
