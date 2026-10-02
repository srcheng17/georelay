# Beta 标签与镜像保留策略

## 当前行为

- `scripts/retain_images.py:22` 将正式完整发布组保留数固定为 `KEEP_RELEASES = 10`。
- `scripts/retain_images.py:23` 的 `RELEASE` 只匹配 `v<major>.<minor>.<patch>-georelay-<40 位小写 hex commit>`，以及可选的 `-amd64`、`-arm64` 后缀。
- `scripts/retain_images.py:165` 只把匹配该正则的标签纳入发布分组；`:172-185` 要求两个 package 都有双架构标签与正确索引，才视为完整组。
- `scripts/retain_images.py:187-192` 按完整组创建时间保留最新 10 组，并额外保护任一 package 的 `latest` 所指向的完整组。
- `scripts/retain_images.py:199-204` 仅考虑淘汰完整组的 digest；其余 digest 默认保护。候选 digest 上出现未知标签或保留组标签时，也会重新加入保护集合。
- `scripts/retain_images.py:205-210` 沿受保护 manifest 的子节点计算依赖闭包，保证未知索引引用的双架构 manifest 不被删除。

因此 `v<upstream>-georelay-beta-<40hex>`、其双架构标签、`beta-<branch>` 和 `beta-pr-<number>` 都不会被当前正式发布正则识别。它们不挤占正式版 10 组额度，也会暂时永久保留。即便 beta 与过期正式标签共用 digest，未知标签保护及依赖闭包也会保护 beta 实际需要的 manifest。

## 最小变更边界

本次不需要修改 retention 逻辑。继续把 beta 视为未知且受保护的标签，即满足 beta 不挤占正式版保留额度的要求；增长限制与 beta 清理单独处理。

未来若增加 beta 自动清理，应独立计算 stable/beta 的保留额度，并保护 beta 浮动别名及其依赖。不能只将 beta 加入现有 `RELEASE` 正则，否则 beta 会与正式版竞争同一个 10 组额度。现有两 package 完整组、索引、共享子节点和删除顺序检查应复用。

## 标签限制

- `scripts/retain_images.py:90-95` 接受 `[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}`，即最多 128 字符。
- Git 分支中的 `/` 无法直接用于 Docker tag。若选择分支别名，应规定规范化和重名处理；按 PR 编号生成 `beta-pr-<number>` 更简单，也能直接关联审阅目标。
- 不可变 beta 标签中的上游版本、完整 commit 与双架构后缀均需保持一致。浮动别名的更新应只指向已测试且仍对应当前 PR head 的成功候选。

## 可复用的回归检查

`tests/test_retain_images.py` 已提供 `PackageFixture`、`group()`、`tagged()` 和 `run()`。最小新增测试可复用这些构件：

1. 建立 13 组 fixture，把最旧组的索引及双架构标签改为 `v<upstream>-georelay-beta-<40hex>`，并给索引添加 `beta-pr-42`。
2. 执行实际 planner 的 `fixture.run(apply=True)`，断言完整正式组为 12 组，只淘汰正式组 1、2；两个 package 的 beta 索引及双架构 digest 均未进入删除计划。
3. 如需覆盖共用 digest，可沿用 `test_shared_children_and_unknown_retained_indexes_are_protected`：未知 beta 索引引用过期正式子 manifest 时，子 manifest 仍保留。

现有 `test_legacy_release_tags_are_preserved_and_legacy_packages_are_untouched` 已覆盖非当前命名标签保护；`test_shared_children_and_unknown_retained_indexes_are_protected` 已覆盖共享子节点与未知索引依赖闭包。

已执行不写文件的 inline fixture 验证：13 组中将第 0 组改为 beta 后，报告仅淘汰正式组 1、2，beta 索引及双架构均保留。未执行实际 GHCR 删除或其他线上变更。
