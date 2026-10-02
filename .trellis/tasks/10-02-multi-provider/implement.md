# 实施

1. 研究官方 SN 编码、坐标语义和供应商映射并存 research/provider-apis.md。
2. implement worker 修改 adapter/server.py 和 tests/test_adapter.py，模拟验证实际行为。
3. root 同步配置与双语说明、接口 spec，验证 Compose 合并与文档。
4. 隔离容器 tmpfs 0600 凭据，公共地标真实联调；无 host port，结束清理。
5. 独立审查新增与自动发布全范围，运行 Python/diff/actionlint，更新现有 PR。
6. 核对最终 SHA 的双架构 CI，正常保护流程合并并发布，核对双索引及匿名拉取。
