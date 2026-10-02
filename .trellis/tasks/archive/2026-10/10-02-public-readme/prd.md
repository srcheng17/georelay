# 公开仓库与 README 整理

## 目标

用户授权将现有仓库公开，并在当前feat/amap-adapter分支以固定官方v4.3.0 README为基础补充高德新增能力；承接上一请求落实main保护，保留PR审查与未部署边界。

## 范围

- 先只读检查所有可达Git历史、当前文件和现有GitHub PR/CI公开内容；仅报告疑似泄露类别，不打印秘密。发现真实凭据或私人位置时先处理，不能直接公开。
- 官方README保留/准确转述项目简介、原功能、dashboard、截图、文档、来源与许可；清楚标注社区修改版本，不能把官方徽章/发布指标当成本仓库结果。截图使用固定上游绝对URL，不复制截图/完整源码。
- README突出新增能力、地址与底图边界、固定版本和验证状态。配置/构建/身份备份/发布维护细节移至docs/AMAP.md，保持当前接口与未迁移限制准确。MODIFICATIONS.md去除过时的私有仓库表述，LICENSE/NOTICE/TRADEMARK原样保留。
- 在审计无阻断后通过GitHub官方API将现有仓库设为public，读取核对；不创建新仓库或重写Git历史。
- main保护要求PR、由GitHub Actions的verify通过且与base同步；包括管理员，禁止force push/删除。个人维护仓库不引入他人审批数量要求，仅verify必需，publish不是必需检查。
- 不合并PR，不发布镜像，不部署，不操作生产。

## 验收

- 正文无运行日记/私人操作路径/真实数据，来源与修改声明清楚；新增功能与实际实现及示例一致。
- 相对文档链接、固定截图和Markdown结构可验证，git diff检查通过。
- 当前分支可审查提交并推送现有PR，最终CI实际结论成功。
- GitHub回读private=false；main protected=true且所选规则与verify app绑定准确。
