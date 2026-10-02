# 主应用镜像启动验证证据

## 源码与运行环境

- 日期：2026-10-03；分支 `feat/beta-review-release`，基线 `da6cc08`。
- 官方 pin：TeslaMate v4.3.0 / `33d200b2fba9d5138803916a788cef5eae31b1aa`。
- 本轮通过共享 `scripts/prepare_upstream.py` 准备源码；复核 prepared HEAD 与 pin 一致、当前三份补丁 reverse-check 通过、法律与修改通知文件一致。未复用旧 `/tmp/teslamate-amap-prepared-check`。
- Docker context：orbstack，实际镜像为原生 linux/arm64。
- 主镜像：`georelay-main-smoke:checked-01a0fe28`，ID `sha256:5a73784a17f8349662ea2e7c8634c0f29c8abd05f8dc08aa7d1b0141bff1f123`。
- Probe：`georelay-adapter-main-smoke:checked-01a0fe28`，ID `sha256:554bb4d9265a0e19e24e1f826bdbd7e7a1dbf539eaacdccb7d492b88fbc8a9b8`。
- 官方 Docker 入口 `tini -- /bin/dash /entrypoint.sh`、CMD `bin/teslamate start`；entrypoint `set -e` 并调用 `TeslaMate.Release.wait_for_database_and_migrate()`，未被检查脚本覆盖。
- 当前 pin 的实际路由为 `live "/sign_in", SignInLive.Index`；无车辆登录时直接验证登录 HTML。

## 取消缺口与回归

向 Bash 入口 PID 单独发 TERM，分别阻塞 Docker inspect、HTTP probe 与迁移 exec。修复前三个场景均在 3 秒内无法退出，证明前台包装进程与命令替换会推迟 trap；不是用静态检查推断。修复后阻塞 inspect/probe/SQL 的 TERM 和 inspect 的 INT 回归通过，只向 Bash 入口 PID 发信号，验证 Docker CLI/包装进程消失以及资源/临时文件清理。

## 云端和操作边界

两个 CI 原生 runner（ubuntu-latest/amd64、ubuntu-24.04-arm/arm64）均在保存 artifact 前调用同一脚本；失败不能进入保存和发布。云端两架构结果尚未取得，不能将本机 arm64 当作云端结果。

当前无提交、push 或 PR，未合并、未部署；子任务验收证据独立于父任务 beta/条件合并/Bark 规划，后者尚未实现。品牌解耦另由 enhanced-hedgehog 负责，本项未修改 prepare、品牌补丁或其回归。


## 最终脚本真实镜像复跑（本机原生 arm64）

正常检查实际执行：

```bash
bash scripts/test_main_image.sh \
  georelay-main-smoke:checked-01a0fe28 \
  georelay-adapter-main-smoke:checked-01a0fe28
```

真实默认入口完成全新临时库迁移；不是 ExUnit、脚本静态检查或 fake Docker 成功：

```text
Main image smoke passed: /sign_in HTTP 200, login HTML verified; migrations=105; core tables present
```

| 实际场景 | 退出码 | 秒 | 独立回读清理 |
| --- | --- | --- | --- |
| 默认 release + 新 PostgreSQL | 0 | 4.388 | 容器/网络/临时 stdout 文件均 0 |
| 损坏默认入口 /bin/false | 1 | 0.832 | 容器/网络/临时 stdout 文件均 0 |
| 错误 PORT=4001，5 秒就绪上限 | 1 | 5.102 | 容器/网络/临时 stdout 文件均 0 |
| 启动临时 DB/app 后只向 Bash PID 发 TERM | 143 | 0.661 | 容器/网络/临时 stdout 文件均 0 |

入口损坏的脱敏诊断为 `app state=exited exit=1`；错误端口为 `HTTP readiness timeout`。TERM 到完成清理约 0.359 秒。故障镜像均由同一本次主镜像派生，仅覆盖入口为 /bin/false 或设置 PORT=4001。每次使用新 internal 网络和 tmpfs PostgreSQL，不使用已有卷/数据库、不映射宿主端口。独立回读结果保存在 [runtime-results.json](runtime-results.json)。

## 双架构状态

| 架构 | 本机真实最终镜像运行 | 云端原生 CI |
| --- | --- | --- |
| arm64 | 上述正常/故障/超时/TERM 全部符合预期 | 待 PR/CI 验证 |
| amd64 | 未在本机执行 | 待 PR/CI 验证 |


## 最终质量门禁

- Trellis full-scope check：通过；复核脚本、CI、测试、文档、任务契约与实际运行证据。
- 完整 `python3 -m unittest discover -s tests -v`：98/98 通过，62.749 秒；随后仅完善 probe 生命周期的离线 fixture，最终专项 9/9 通过，12.908 秒。
- `bash -n scripts/test_main_image.sh`、actionlint v1.7.12（`-shellcheck=`）、`git diff --check` 与 Python 语法检查均通过。
- 仓库未配置独立 typechecker；shellcheck 未执行，不将 actionlint 的禁用 shellcheck 记成 shellcheck 通过。
- 取消回归之外，审查补齐了 Docker 删除失败的残留容器回读和超长超时输入拒绝；只有清理通过才打印 passed。rm/残留查询/network rm 三项各有 2 秒上限，引擎失联或残留时非零退出，不能声明清理成功。

## 当前交付状态

本地实现与必要验证完成，保持任务 in_progress，等待 Trellis 3.4 的一次提交计划确认；尚未提交/push/创建 PR。没有运行云端、开启 auto-merge、合入 main 或生产部署。父任务的 beta/条件合并/失败 Bark 授权与规划保留；用户后续已确认部署仅指 GHCR 正式镜像/latest，不更新运行容器。


## 父任务最终整合补充

父任务已获用户“开始”实施授权，beta/条件合并/失败通知代码已实施并进入最终审查；上文“父任务尚未实现”为子任务完成时的历史状态。最终脚本现增加 `/notice`、`/license` 和编译后地址 RPC 检查，正常输出含 `compiled address checks passed`；父任务实际本机 arm64 整链复跑仍完成105项迁移，默认/坏入口/错误端口/TERM均符合预期且零容器/网络残留。最新结果见 [父任务 runtime-results.json](../10-03-beta-review-release/runtime-results.json)，完整最终集成结果见父任务 validation.md。云端双架构仍待验证。

## Final shared-preparation cloud acceptance (2026-10-03)

The final shared prepare path uses the address-only official source and two strict patches. Historical local branded-image evidence above does not establish the final image result.

- PR10 exact head `4dce3a817fd0608fe7e9e3b271e4cd4562dd0ed6`, beta run [37071951401](https://github.com/srcheng17/georelay/actions/runs/37071951401): native amd64 and arm64 each passed default release startup, `/sign_in` HTTP 200 and meaningful login HTML, 105 database migrations, core tables and compiled address runtime checks. Adapter packaged code passed 34/34 on each architecture. verify and publication passed.
- User-authorized ordinary expected-head merge produced `5727c65a9eda47869bfea1b79679e6899ce829a5`; main run [37072746968](https://github.com/srcheng17/georelay/actions/runs/37072746968) independently repeated the same actual two-architecture runtime and adapter checks before formal publication. Both stable indexes, OCI revision/version/source and all manifest/config digests were verified, and `latest` matched the checked formal indexes.
- CI calls `scripts/test_main_image.sh` before `docker save` and upload; the script retains the main image default ENTRYPOINT/CMD, starts a fresh PostgreSQL on an internal temporary network without host ports or production mounts, and only returns success after HTTP/SQL/compiled-address checks and resource cleanup. Failure runs demonstrate that tests failing earlier prevent publication; they are not claimed as main startup successes.

Parent cloud acceptance details and fixed digests: `../10-03-beta-review-release/cloud-validation.json`. The parent still verifies conditional default-token merge/dispatch; running production containers remain outside scope.

Final native-protection candidate172f855 beta37077079430 repeated the actual default-entrypoint startup on native amd64/arm64: login HTTP200, 105 migrations, core tables and compiled address checks. Both packaged adapter suites and verify/publication succeeded. PR11 normally installed this exact tested candidate at main02c4262; main37077752055 remains pending and is not reported as completed here.

Installer main run37077752055 at02c4262 completed successfully with both native main runtime and packaged adapter suites, verify and publication. Both stable/latest indexes and child/config/OCI digests were independently verified. Subsequent automatic candidate/main runs are final integration acceptance, not required to replace this actual main runtime evidence.
