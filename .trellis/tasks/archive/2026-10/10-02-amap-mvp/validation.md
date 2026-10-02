# 验收记录

日期：2026-10-02。仅开发隔离环境，无生产变更、无真实 Key。

- 全量31项Python测试通过，包括真实本地HTTP、硬超时、稳定身份、并发/重启/TTL/语言、50项OSM批量刷新、境外/港澳和在线备份。
- 固定官方v4.3.0 / 33d200b2fba9d5138803916a788cef5eae31b1aa的fresh fetch/apply通过；错pin/缺补丁/冲突/非空目录保护有real-git检查。
- 隔离Elixir1.20.3/OTP29 + PostgreSQL18：编译warnings-as-errors、格式检查和105项ExUnit通过，包含负signed bigint实际数据库roundtrip。
- Python编译、Shell语法、Compose、git diff --check通过；项目未配置独立类型检查器。
- adapter镜像构建通过；UID10001、只读rootfs、无网络/Key/host port、独立临时卷下health和许可检查通过；容器与卷已清理。
- 独立reviewer全范围复核通过。GitHub完整检查已通过：https://github.com/srcheng17/teslamate/actions/runs/36995771539 ，对应代码提交 f09ecd0594b60177fae61b93d8de7c425f5735ce；耗时5分30秒，包含两个linux/amd64镜像构建、上游测试和无Key容器健康检查。publish按预期跳过，未推送镜像或部署。

## 官方锁定依赖公告

mix deps.get对未经本项目修改的官方mix.lock发出以下Hex公告。未做利用验证或修复版本研究；未私自升级依赖或部署。

| 包 | 关系 | 级别 | 公告 |
| --- | --- | --- | --- |
| cowlib 2.20.0 | plug_cowboy→cowboy生产传递依赖 | MEDIUM | GHSA-w4f7-4cxr-rv3c / EEF-CVE-2026-43966 |
| cowlib 2.20.0 | 同上 | LOW | GHSA-g2wm-735q-3f56 / EEF-CVE-2026-43969 |
| lazy_html 0.1.12 | only:test | LOW | GHSA-8rqp-v692-v82q / EEF-CVE-2026-92106 |
| mint 1.10.1 | Finch生产传递依赖 | MEDIUM | GHSA-gvrc-75rc-7gj9 / EEF-CVE-2026-94194 |
| mint 1.10.1 | 同上 | HIGH | GHSA-9x8p-qrf4-jq7g / EEF-CVE-2026-91043 |
| mint 1.10.1 | 同上 | MEDIUM | GHSA-q95c-ccq6-j5j6 / EEF-CVE-2026-92103 |

实际上线前应结合官方后续稳定版重新评估。构建成功不等于已消除已知依赖风险；公告可按ID在 https://osv.dev 查询。
