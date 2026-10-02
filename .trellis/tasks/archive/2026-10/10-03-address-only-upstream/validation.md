# 验证

## 本地实证
- 完整 Python unittest：87/87；准备路径专项 6/6。
- Python compile、bash -n、git diff --check 通过。
- 固定 v4.3.0 / 33d200b2fba9d5138803916a788cef5eae31b1aa 新目录准备成功。
- 实际生产源码仅修改 3 个地址文件：elixir/lib/teslamate/http.ex、locations.ex、locations/geocoder.ex。
- 上游 LICENSE、NOTICE、TRADEMARK.md、Dockerfile 与固定 commit 逐字一致；UI/gettext/static 无 diff。仅新增两个地址契约测试。
- 隔离 PostgreSQL/Elixir 编译、地址路径格式与 ExUnit：130 passed。原 Settings/HTTP/Addresses/Geocoder 及新增地址测试保持；退出后无测试容器或网络残留。
- 改动文档相对链接存在检查通过。adapter、两个地址补丁、publisher/updater/retention 相对 main 未改。

- 独立 Trellis review：未发现范围内问题；准备专项 6/6、语法与空白复核通过，无残留活跃品牌/法律快照门禁。

## 云端门禁
当前本地证据不能代替 PR 原生 linux/amd64、linux/arm64 和 verify；push 后核对当前 head 的全部结论，全部成功才允许按用户“push合并”授权合并。main 构建与 publish 的实际状态在最终回复报告，不把发布当作生产部署。

## 边界
没有使用真实地图 Key 或生产数据；没有合并独立启动 smoke agent 的分支。取消额外法律/品牌审核，不删除或改写上游原生许可与署名，也不保证上游自身 Dockerfile 的任意变更均兼容。
