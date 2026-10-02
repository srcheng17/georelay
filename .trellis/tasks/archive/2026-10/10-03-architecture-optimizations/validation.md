# 优化验证

日期：2026-10-03。固定上游：upstream.json 的稳定 tag/commit；模拟数据均为虚构或公共地标，不使用车辆数据和真实凭据。

## 已完成

- 全 Python：68项 / 40.117秒 / OK，含50项大陆延迟模拟、非首项先失败的取消回归、身份/缓存/重启/语言、法律原文与品牌变化拒绝、发布及updater失败路径。
- adapter早期顺序等待缺陷由独立评审复现：首项慢、第二项失败时旧实现启动全部50项。FIRST_EXCEPTION修复后34项adapter测试通过，取消排队且成功结果保序。
- 第2份上游补丁单独集成：130项ExUnit通过，实际隔离PostgreSQL验证字段刷新、引用/身份/原坐标保持、仅本地模式及默认OSM回退。
- 合成Compose验证：双语例子相同；默认两镜像名/true旗标正确；原数据库、其他环境变量和依赖及amap-data保留，不开放host port。只运行config，不启动任何stack。
- 相对文件链接、shell语法、git diff --check通过。
- GitHub仓库已改名srcheng17/georelay，保持public；main的verify/strict/admin/禁强推/禁删除保护回读保持。
- 最终独立只读审查通过代码/三补丁/原文通知/品牌资产范围；补齐受影响settings测试到CI入口。

## 完整本地集成

- 最终固定官方commit33d200b2fba9d5138803916a788cef5eae31b1aa的三份补丁检查/应用通过，法律原文逐字相同，品牌资产与日期通知正确暂存。
- 隔离脚本编译warnings-as-errors、所有修改HEEX/测试格式检查通过；175项ExUnit全通过，含en/de/zh_Hans实际渲染、免责声明/来源/版权、图标文件、Settings/GPX/已有地址写回。
- adapter linux/arm64 Docker构建通过，非root UID10001可读0444许可/修改通知；source与Docker label回读正确。完整主应用双架构镜像交由PR CI检验。
- 独立最终check无未解决发现。发现的settings检查遗漏与两项旧品牌断言已补齐。

## 远端构建与发布

- PR #3提交22b2e82648e741bfcefa5f6a32b2802b3655985a通过[37042779977](https://github.com/srcheng17/georelay/actions/runs/37042779977)：两个原生架构均完成68项Python、175项ExUnit、adapter及应用镜像构建和健康检查，verify成功。PR事件按设计不发布。
- 用户明确授权后，PR #3于2026-10-02T17:54:53Z合并；main发布源码3e6cbfac755f8811b6de76dbba069a702e1ca82a。其[37043924235](https://github.com/srcheng17/georelay/actions/runs/37043924235)的amd64/arm64、verify、publish全部成功。
- 发布版本：v4.3.0-georelay-3e6cbfac755f8811b6de76dbba069a702e1ca82a。两个package网页均回读Public，匿名registry核验每个版本索引仅含linux/amd64和linux/arm64，且各自latest逐字匹配其版本索引。
- georelay索引：sha256:4995d7e183ff5172d71f0b54e2c2757c68ae5df75264a062cb21c6e49e16f5a0；georelay-adapter索引：sha256:7e21879b0038737f3cfb6ada21b7b6cb6ced7c25f9ed4b0076ac2432556870b2。
- 使用临时空Docker配置实际匿名拉取两镜像的两个平台，共四次；每个子digest的OS/架构、source、revision、version和非root运行用户正确。仅创建未启动的隔离检查容器读取文件，许可/修改通知与审阅源码逐字一致。临时容器、镜像引用和认证配置已清理，未挂载生产卷。

## 发布与生产边界

main的AGENTS.md和paseo.json要求用户明确批准合并当前PR/分支。PR #3已获独立授权并正常合并，未绕过保护或开启auto-merge。两个新package已公开发布并完成匿名验证；旧镜像保留。首次发布说明与本记录的收尾文档PR保持开放，合并授权不延用于该PR。未修改生产容器、数据库、Dockhand或车辆数据，未执行历史迁移。
