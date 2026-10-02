# 设计

公开镜像包由仓库 owner 和明确常量组成：`georelay`、`georelay-adapter`。本地 checked artifact 标签保持 georelay/georelay-adapter；版本保持 `vX.Y.Z-georelay-源码SHA`，OCI labels 对应实际构建来源。publisher 与 retention 使用一致包映射及现有失败保护，回归覆盖仓库名称变化。

双语 README、配置指南与发布规范同步公开引用。历史包保留现有发布内容；服务名、数据卷、provider 环境变量、GeoRelay 品牌和上游内部标识不重命名。

改动边界为 publish/retention 入口、对应 tests、双语文档和发布规范。不改变运行代码或补丁、不迁移旧地址身份，不引入部署自动化。运行备份在用户私有目录，测试使用独立临时资源。生产切换使用已成功发布的 main 源码 0b0e6ac 镜像，命名解耦改动不改变运行内容，也不需要先合并当前 PR。
