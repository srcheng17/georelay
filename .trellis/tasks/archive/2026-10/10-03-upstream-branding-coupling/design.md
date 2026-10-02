# Design

## Boundary
保持固定上游源码 + 少量功能/模板补丁 + Python sidecar 架构。优化集中在共享 prepare 路径，CI 和本地构建自然复用；无需新增依赖或配置框架。

## Preparation flow
1. Fetch/check reviewed stable tag and exact commit；法律文件保持现有逐字审核门禁。
2. 资产检查只要求新增未知视觉资源复核，不要求整个 static 目录文件集合永久不变；删除已知品牌资源时允许文件已经不存在。
3. 严格检查并应用补丁，保留品牌模板、布局、GPX 和对应测试改动；从 0003 删除 20 个 gettext diff sections。
4. 按解码后完整 msgid 精确选择当前四条应用名称文案，更新 msgid 及对应 msgstr 中的品牌字面值。不全文替换源代码，不修改未知条目、评论或必要法律署名；多行 PO 字符串先组合为语义字符串。
5. 生成 GeoRelay favicon、携带修改说明和商标政策；取消依赖具体 HTML 源码写法的品牌扫描，由既有实际渲染测试验证公开效果。

## Compatibility and checks
地址补丁和运行行为不变；品牌模板效果保持，翻译只改变四条已知消息的品牌。使用既有 Python unittest 和现有 Floki/ExUnit，扩展品牌渲染循环到实际已知 locales。新增 UI 品牌文案需显式更新受控映射及渲染用例；不构造通用 PO 编辑器或语法树框架。

新增未知视觉资源仍人工复核：目录全等可取消，未知 Logo 不能未经审查发布。法律文本变化继续停止并要求复核。

## Ownership / rollback
Implementation worker owns prepare_upstream.py、0003 patch、test_upstream.py；root owns docs、specs、task artifacts and validation integration。指定外部 agent owns startup/CI work in another worktree。各自兼容他人工作，不回滚其他任务。
回滚本任务只需恢复上述脚本/patch；不涉及数据迁移。
