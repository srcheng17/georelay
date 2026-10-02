# 公开仓库与文档验收

2026-10-02，用户授权公开现有仓库、保护 main，并在当前功能分支以官方 README 为基础补充高德功能。此次仅修改文档、项目约定及任务材料；未合并 PR、发布镜像或操作生产。

## 公开内容审查

以 `9ca2d24f955d8160c21b923f76871b983e61141a` 为基准，检查 6 个本地 refs、12 个提交、183 个唯一历史 blob，以及 141 个跟踪文件和新增任务材料。远端 main/feature 与本地匹配，PR 合并树也在覆盖范围内；PR #1 正文、可见评论及审查、全部 5 次 CI 日志均已覆盖，Actions 产物为 0。取消的运行也取得 verify 日志完成审查。

未发现凭据、私钥、数据库备份、生产配置或私人位置数据。坐标命中为公共测试地标与 GCJ 数学常量。此结论针对当前可达且可读取内容，后续新增内容仍需审查；不因这些排除项重写历史。

新文档、质量约定与任务材料共 9 个文件已完成独立增量审查，敏感项扫描无候选、验收无阻断。另以 GET 核对全部 22 个官方仪表盘文档锚点存在。

## GitHub 设置回读

GitHub 官方 API 写入后另行读取并断言：

| 设置 | 回读结果 |
| --- | --- |
| 仓库 | `srcheng17/teslamate`，`private=false`、`visibility=public` |
| 默认分支 | `main`，`protected=true` |
| 必需检查 | `verify`，绑定 GitHub Actions `app_id=15368` |
| 与 base 同步 | `required_status_checks.strict=true` |
| 合并方式 | 要求 PR；个人维护不要求其他人的审批，批准数为 0 |
| 管理员 | `enforce_admins=true` |
| 强推 / 删除 | 均为 `false` |

main 仍为 `729fbc1f8841db24fa4035e9e976e02bbd79b898`。未更改默认分支或合并现有功能 PR。

## 来源与文档

- README 基础为官方 v4.3.0 / `33d200b2fba9d5138803916a788cef5eae31b1aa`，本地来源与固定提交的 GitHub raw 内容逐字匹配；官方 README SHA256 为 `9ed1e899f74b5ba6172899e03e0fb9229ef3ea999a701261cd3465689dcab9b8`。
- LICENSE、NOTICE、TRADEMARK.md 与固定官方文件逐字一致，未作修改。首页显著保留非官方声明，并保留官方简介、General、22 个仪表盘、三张官方截图、文档、许可和致谢；不复制上游徽章、发布指标或整份源码。
- 新增能力、地址与底图边界、WGS84、名称优先级及当前状态在首页说明；配置、接口、构建、永久身份备份和发布维护集中于 `docs/AMAP.md`。来源和重建说明仍在 MODIFICATIONS.md。
- 三文件 Markdown 结构、30 条相对链接及锚点、PR #1 链接、环境变量、默认值、固定版本和既有验证材料一致性检查通过。三张固定 commit 截图均返回 HTTP 200 和 `image/png`。`git diff --check` 与 task context 校验通过。

此次为文档修改，不另建产品测试；完整产品检查由 PR 的 Validate and build 工作流执行。既有运行 [37001715485](https://github.com/srcheng17/teslamate/actions/runs/37001715485) 对修改前提交的 verify 成功。新增提交的检查结果以 [PR #1 checks](https://github.com/srcheng17/teslamate/pull/1/checks) 为准，交付前独立核对最终提交与实际结论；publish 仅在 main 手动请求发布时执行。
