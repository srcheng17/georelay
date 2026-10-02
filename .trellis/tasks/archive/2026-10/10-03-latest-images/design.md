# 设计

在现有 publish_images.sh 末尾推广已检查的两个多架构版本索引，latest 不构建新镜像。复用 check_release 的官方最新稳定版校验，并在推广前回读 origin/main 与运行源码分支，跳过在发布期间变旧的来源；启动时已过期的 upstream 分支沿用原先严格 preflight 拒绝，不放宽版本发布权限。ci.yml 的 publish job 使用同一 concurrency group 串行。

先完成所有架构 push、两个版本索引验证，再更新两个 latest 并回读内容。注册表不提供两个 package 的原子更新；任何推广/回读失败使 workflow 失败，不能宣称交付成功，固定版本仍可使用。GitHub 本身的 pending job 队列不承诺 FIFO；新鲜度校验防止旧任务倒退。

改动仅涉及发布脚本、已有发布检查、workflow concurrency、updater PR说明、双语使用文档、环境示例和发布规范。地址服务与上游补丁不变；不新增部署自动化或依赖。
