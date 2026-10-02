# 实施计划

1. CI worker：原生双架构 matrix、verify 汇总、已测试 tar、多架构版本发布及受控自动分支发布。
2. updater worker：复用稳定版检测，自动 pin 分支/PR、显式 dispatch、幂等/失败检查；每六小时轮询。
3. root：同步约定与双语 README/指南，验证假配置/链接，配置 Actions PR 创建权限。
4. 独立全范围审查，本地 Python/diff 检查，推送现有 PR，等待双架构 CI。
5. 正常合并 PR，main 自动发布；设置两个 package public，验证索引与匿名拉取，无生产操作。
6. 按实际标签更新使用示例和验收材料，归档/记录，验证最终提交与自动检测结果。

复用 python3 -m unittest discover -s tests -v、git diff --check 和 GitHub CI。上游构建/测试由各原生 runner 执行；只因新改动或失败重复检查。匿名拉取使用临时 Docker 配置及隔离测试容器，无 host port，结束清理。
