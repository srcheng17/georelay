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

## 等待最后回读

- 更新PR #3并核实准确提交的双架构build和verify。

## 发布与生产边界

main新增AGENTS.md和paseo.json要求用户明确批准合并当前PR/分支。PR保持开放，不开启auto-merge；GeoRelay新包未发布，不声称已匿名拉取。批准合并后由main CI发布，再设置新package public并验证匿名双架构拉取、标签/索引/许可。旧镜像不删除。未修改生产容器、数据库、Dockhand或车辆数据，未执行历史迁移。
