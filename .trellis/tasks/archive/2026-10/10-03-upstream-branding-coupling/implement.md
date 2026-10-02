# Implementation plan

1. [x] 读取 task/spec/research，核对共享 prepare 所有调用者及品牌测试。
2. [x] 收窄静态资源检查，移除宽泛源码名称和特定 HTML 片段扫描；缺失旧品牌资产可容忍。
3. [x] 从 0003 移除 gettext diff，添加四条语义消息的受控转换，保留其他条目原文。
4. [x] 更新真实 Git fixture 回归和现有多语言渲染检查，不新建测试框架。
5. [x] root 同步 docs/AMAP.md、MODIFICATIONS.md 与后端/前端规范中相应边界。
6. [x] 全仓 Python + whitespace；fresh prepare 当前固定官方 commit；验证所有旧品牌翻译的解码消息与新输出等价。
7. [x] 隔离 Docker 上游格式/ExUnit + 本地原生镜像构建和既有许可/健康检查。双架构验证依赖 CI；本次未 push 时不得报告云端已通过。
8. [x] 派 trellis-check 审阅全任务并修复局部问题；记录 validation，按 Trellis 完成提交/收尾，本轮不 push 或合并。

Scope gate: 用户已明确确认上轮优化范围并要求本分支实施；保留原文法律审核和未知视觉资源复核，不引入新的风险选择。实现如需要改变这些边界，先报告，不扩大。
