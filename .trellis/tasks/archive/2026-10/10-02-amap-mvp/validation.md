# 验收记录

日期：2026-10-02。仅开发隔离环境，无生产变更；以下先记录无 Key 验证，真实 Key 联调见后文。

- 全量31项Python测试通过，包括真实本地HTTP、硬超时、稳定身份、并发/重启/TTL/语言、50项OSM批量刷新、境外/港澳和在线备份。
- 固定官方v4.3.0 / 33d200b2fba9d5138803916a788cef5eae31b1aa的fresh fetch/apply通过；错pin/缺补丁/冲突/非空目录保护有real-git检查。
- 隔离Elixir1.20.3/OTP29 + PostgreSQL18：编译warnings-as-errors、格式检查和105项ExUnit通过，包含负signed bigint实际数据库roundtrip。
- Python编译、Shell语法、Compose、git diff --check通过；项目未配置独立类型检查器。
- adapter镜像构建通过；UID10001、只读rootfs、无网络/Key/host port、独立临时卷下health和许可检查通过；容器与卷已清理。
- 独立reviewer全范围复核通过。GitHub完整检查已通过：https://github.com/srcheng17/teslamate/actions/runs/36995771539 ，对应代码提交 f09ecd0594b60177fae61b93d8de7c425f5735ce；耗时5分30秒，包含两个linux/amd64镜像构建、上游测试和无Key容器健康检查。publish按预期跳过，未推送镜像或部署。

## 真实 Key 联调

2026-10-02，用户授权参考 Dockhand 的现有 Key 测试。通过官方 v1.0.49 只读 API 定位 Mac mini 的 TeslaMate stack 和对应容器；变量及 inspect API 均遮蔽秘密，因此仅在宿主机只读提取该容器的 `AMAP_API_KEY`。未读取车辆记录或查询生产数据库，全部查询使用公共地标。

测试镜像由当前代码构建，运行在随机命名的独立 Docker 网络和临时 SQLite 卷中；UID/GID 10001、只读根文件系统、无 host port、不挂载生产卷。Key 不在命令行或环境变量中，经标准输入写入容器 `/run` 的 tmpfs 文件，权限0600。

18项断言全部通过，无失败：

| 验证 | 实际结果 |
| --- | --- |
| 北京、杭州 reverse | HTTP 200，高德地址字段有效；直辖市 city 正常回填 |
| 巴黎、首尔 reverse | HTTP 200，OSM 来源及国家字段正确；首尔验证 GCJ 矩形内境外分流 |
| 香港、澳门 reverse | HTTP 200，OSM 来源及国家/地区字段正确 |
| 六点身份与坐标 | 均为负数 node，响应保留原始 WGS84；SQLite 保存四个可信 OSM 来源 |
| 等价坐标文本 | 复用同一永久身份 |
| zh-cn → en 混合 lookup | 只返回六个请求身份，原坐标不变；包含港澳实际批量 OSM lookup |
| 测试容器重启 | 同一卷内身份、坐标、来源及缓存 lookup 不变 |
| 测试缓存过期后混合 lookup | 真实上游刷新成功，永久映射不变；只过期隔离库 cache 行 |
| 测试网络断开 | 有效缓存 lookup 为200；北京/巴黎过期缓存返回明确502/503/504，27秒以内，无 Unknown 地址 |
| 上游不可达时 health | 本地检查仍为200，符合仅检测SQLite的约定 |
| 恢复测试网络 | 地址刷新成功，仍为原请求身份与坐标 |

测试结束后容器、网络、临时数据卷、专用镜像标签均已清理，tmpfs 中的 Key 随容器删除。前后比较现有容器 ID、镜像、启动时间和重启计数一致，未更改生产配置或部署。本次只提交脱敏记录，不保留真实 Key、完整上游响应、运行配置或测试数据库。

独立 reviewer 再次运行31项 Python 测试通过（9.900秒），Python 编译与 `git diff --check` 通过，未发现新的确定性缺陷。本次无需产品代码修改。高德请求当前不传语言参数，语言切换验证身份和刷新闭环，不要求英文翻译；六个公共样本不能证明全球或全部边界覆盖。

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
