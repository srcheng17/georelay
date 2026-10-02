# 验证与发布

使用 Python 标准库实现和 unittest，优先直接函数与 SQLite 约束。非平凡逻辑留下能复现实际失败的测试；mock 使用虚构公共地标坐标，禁止生产数据。覆盖 reverse/lookup 身份闭环、重启、TTL、语言、并发、境外、错误与超时；真实本地 HTTP 测试验证 JSON/status/log 隐私。

固定 `upstream.json` 中稳定 tag 和解引用 commit，下载到临时/忽略目录；先校验 commit 再 `git apply --check`，任何失败停止。保留上游 LICENSE/NOTICE。GitHub release 检测只提出 pin 更新；校验、构建与可选镜像发布互相依赖，发布仅可信分支手动触发且不得绕过测试。不自动部署、不自动提升 stable、不 force push。

改动最少的必要文件，不引入框架/ORM/插件层。构建流程本身要有失败测试。新增测试路径必须与 workflow 和 README 命令一致。

统一补丁的空白上下文行必须保留单个空格前缀；`.gitattributes`只对此类文件关闭blank-at-eol检查，实际应用后的上游源码仍由prepare脚本执行git diff --check。
