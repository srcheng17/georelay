# 最小设计

复用 test_upstream.sh 的 Docker 隔离与 trap 清理模式，新增 scripts/test_main_image.sh；同一 CI build job 在镜像构建后调用，在 artifact 保存前门控。

启动一个 internal 测试网络和全新 postgres:18-trixie（tmpfs）。georelay:checked 使用默认入口/CMD启动，测试环境禁用 MQTT，使用固定虚构 encryption key 和数据库凭据。用已构建 adapter 镜像的 Python 标准库探测主应用 /sign_in 的状态、HTML/品牌与登录页面内容。数据库启动前不注入任何 schema，成功后用 psql 校验 schema_migrations 非空及核心表存在。

等待有界，每次检查主应用与数据库状态；探测请求和 Docker 操作需合理超时。默认不输出原始日志，仅状态/固定失败原因及成功的迁移计数与 HTTP 结果。CI 使用 exec bash 直接接收 runner 信号，所有 Docker 操作通过后台 Python 与可中断 wait 执行，stdout 只存一个临时文件；取消先回收子进程再清理。trap 清理所有独立名字的容器（含 probe）、网络、隐式卷；测试储存只用 tmpfs。

scripts/test_main_image.sh 与 tests/test_main_image.py 由实现 worker 拥有；root 拥有 ci.yml、文档/规范、任务证据和实际构建运行。不对父任务现有发布规则做顺带改动。
