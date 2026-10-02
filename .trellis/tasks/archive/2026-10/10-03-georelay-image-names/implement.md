# 实施

1. 从 origin/main 建立隔离分支，完整验证 baseline；只读核对公开注册表和 CI。
2. 修改 publisher/retention 公开包映射及回归；同步双语文档和规范，保留历史任务记录。
3. 全量 Python、bash/actionlint、链接/Compose 检查及独立审查。
4. 使用已成功发布镜像、生产备份的隔离恢复副本验证启动、迁移与认证兼容；清副本 tokens 并禁 recorder，隔离生产 DB/MQTT。真实解析只用公共地标，Key 通过 stdin 临时文件传入。
5. 对已经成功发布的 main 0b0e6ac 固定镜像完成隔离验证，备份并通过 Dockhand 保存、部署，独立回读容器与应用状态。确认数据库/MQTT/Grafana 等未重启，凭据、端口和挂载按既有行为保留。
6. 提交任务分支并创建 PR，核对真实 CI，不合并。运行镜像的源码与该 PR 的发布元数据优化分别记录。
7. 脱敏记录状态与恢复点，清理测试资源。
