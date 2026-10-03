# Research: 镜像版本与 GitHub Release 记录

- Query: 如何为每次真实完成的 GeoRelay 固定镜像发布维护可读、可追溯、幂等的 GitHub Release，并明确自动跟进时的旧→新上游版本。
- Scope: mixed；当前 publisher/updater/controller/CI 源码、现有发布规范及 GitHub 官方 REST/Actions 文档。仅研究与规划，不实现、不调用 GitHub 写 API、不创建 tag/Release、不合并或部署。
- Date: 2026-10-03

## Findings

### First technical gate: exact-source tags with native token

实施的第一项技术门禁是验证默认 GITHUB_TOKEN 是否能给 exact candidate/source SHA 创建 Git tag 并写 Release，尤其 candidate 改动 `.github/workflows/` 的 beta。GitHub 当前官方 Releases 文档明确提示这种 target 可能需要 Workflows:write，而 GITHUB_TOKEN 无此可授予权限。官方也文档化 `POST /git/refs` 创建精确 SHA reference，以及已有 tag 时 Release `target_commitish` 不起作用；这仅提供可验证的 exact-tag-create/readback路径，不证明可以绕过 workflow权限限制。需要以授权的发布验证证明该路径，失败时明确 tag/release permission stage并阻断ready；保留beta覆盖要求，禁止改tag到main、静默换PAT/App凭据或将失败标成功。只读规划阶段不进行此写入probe。

已选方案：独立 in-run trusted-main release-record job；验证当前 run 的 predecessor完成/provenance而不要求整个run completed；结构化 fixed/floating报告；controller/updater/main失败gate同步；release-only补录避免rebuild。浮动推广失败但已验证的双固定镜像可记录事实与failed状态，整体仍未ready。首次 reporter不在main时不能privileged执行候选代码，先完成用户审阅的enablement merge，再启用可信writer。

### Files found

| 文件 | 作用 |
| --- | --- |
| `scripts/image_context.py` | 测试源码 SHA、stable/beta 渠道、固定镜像 tag 与触发输入校验 |
| `scripts/publish_images.sh` | 从已测试双架构 archives 推送两 package 固定索引，验证 digest，再处理 latest/beta PR alias |
| `.github/workflows/ci.yml` | checks、两架构 build、verify、publish，以及直接 main 失败收尾 |
| `.github/workflows/beta-control.yml` | workflow_run 观察器；只运行 main 控制代码，但包含已存在的 merge/dispatch 路径 |
| `scripts/update_release.py` | 自动创建 pin-only 上游更新分支/PR，按既有 CI run 历史决定是否 dispatch |
| `scripts/release_control.py` | 验证 Actions provenance、beta OCI 内容、当前候选和保护，再执行现有条件合并/正式 dispatch；另有当前 main 失败报告 |
| `scripts/check_release.py` | 读取官方 TeslaMate stable Release、解引用官方 tag，生成只读 pin proposal |
| `.github/workflows/upstream-release.yml` | 每六小时/手动运行可信 main 的 updater |
| `tests/test_publish.py` | 执行真实 publisher shell，使用 fake registry/命令，不写真实 GHCR |
| `tests/test_release_control.py` | fake Actions/API/OCI 验证与 main 失败收尾回归 |
| `tests/test_update_release.py` | fake update/run 历史与重试幂等回归 |
| `tests/test_image_context.py` | source/channel/version、fork/dispatch、expected-main binding |
| `upstream.json` | 唯一受审阅的上游 tag/commit pin；当前检索未发现独立 CHANGELOG/VERSION 或 GitHub Release 写入脚本 |

### Existing source contracts

1. 固定版本已包含完整源码身份，无需再引入独立递增版本号：`<official-tag>-georelay-<40hex>` 与 `<official-tag>-georelay-beta-<40hex>`；`image_context.py:48-90`。PR 使用 head SHA 而非 synthetic merge SHA，同仓 main-base PR 才准发布；checkout HEAD 必须等于绑定 SHA：`image_context.py:56-65,103-105`。
2. 当前 publisher preflight 校验上游为正式 Release、tag 未移动，受控 upstream 分支必须只改 `upstream.json`：`publish_images.sh:23-63`。每架构 artifact 验证 OS/architecture 与 OCI source/revision/version，然后推送：`:74-94`。
3. 双固定索引逐一创建并验证且仅含 linux/amd64、linux/arm64，内容须匹配 published digest：`publish_images.sh:96-124`。两 package 均验证后才有可认定的固定发布版本。
4. 固定版本与浮动 alias 是不同状态。无 linked PR 的 beta 在 `:129-133` 成功退出；source/PR 陈旧在 `:172-177` 成功退出并保留固定版本；其余路径在 `:183-190` 按 exact digest 复制并回读浮动索引。任一 alias 写入/回读失败使 shell 非零退出，但在该阶段之前两固定索引可能已完成。
5. 目前只有 Actions summary，未产出面向可信 Release recorder 的结构化结果：`publish_images.sh:125-127,191-193`。因此 recorder 不能用 run success 推断 latest，也不能把某单包成功当作完整发布。
6. 当前 CI publish job 执行候选 checkout 的 `publish_images.sh`，权限是 `contents:read`、`pull-requests:read`、`packages:write`：`ci.yml:162-188`。直接增加 `contents:write` 会把仓库写权限交给未审阅候选脚本。
7. 可信 controller 使用 main checkout 且不下载候选 executable/artifacts：`beta-control.yml:21-40`。但它只监听 `workflow_run`。规范已记录真实 GITHUB_TOKEN-dispatched main run 可能不产生 observer，因此 main CI 自己负责 directly-owned completion/failure：`ci.yml:190-225`，`quality-guidelines.md:146-148`。Release 不能只依赖该 observer，否则 bot 自动更新的正式版会漏记。
8. `release_control.JOBS` 目前仅要求 checks/build-amd64/build-arm64/verify/publish：`:19`；此外每个本 run job 都必须 success，缺失重复 required job 拒绝：`:183-199`。verify 必须来自 Actions app 15368、对应 SHA/run/job：`:200-208`。beta 的最终 Release 记录必须纳入 ready，而不是仅靠 verify success。
9. updater 目前看到 completed success run 中 `publish success` 即认为 started，不会补 dispatch：`update_release.py:140-163`。加入 Release 后必须区分 images published 与 release recorded，否则前者成功、后者失败会永久被误视为已完成。
10. main failure report 当前在 verify+publish 均 success 时跳过，failed_jobs 只看 checks/verify/publish：`release_control.py:87-97`；CI needs 与通知表达式同样只含现有 jobs：`ci.yml:191-215`。需要包含 Release 失败，且维持 beta/no-op finalizer success 与 main bot direct notification 行为。

### Recommended minimal integration

- 保留现有 immutable image tag 和 OCI labels；每个完整固定发布组使用同名 Git tag/Release。正式 `prerelease=false`，beta `prerelease=true`。不对 check-only/fork/metadata-only/build failure 或不完整双索引创建成功记录。
- publisher 在两索引验证成功后输出受限结构化 publication result：version/channel/source SHA、两 package/index digest、fixed_verified、floating tag/status/reason；必须在无 alias/陈旧 ref 的 early success exits 之前留下结果。不得输出 registry token、远端异常原文、精确位置或应用运行配置。
- 新增独立直接 `release-record` job，依赖原发布门禁，执行可信 main checkout 的 recorder；checkout `persist-credentials:false`，新 runner，不加载候选 Python module、cache、venv、脚本或 executable artifact。候选版本说明只能从指定 SHA 以 API 读取作文本数据。job 最小权限预计为 `contents:write`、`actions:read`、`packages:read`，需要 PR 信息时加 `pull-requests:read`；publish/build job 不加 contents write。独立 `@main` reusable workflow 可进一步把所执行工作流代码也固定在可信 main，而非仅固定 recorder checkout，是否采用按实现复杂度评估。
- recorder 不相信候选 job outputs：回读 run ID/attempt/workflow/event/source repository、对应已完成 prerequisite jobs、verify provenance、immutable pin，并重新核验两包 OCI/index digest。复用/generalize `verify_beta` 的只读 registry 结构校验，而非复制另一套弱校验。
- 直接 job 执行时所属 run 仍 `in_progress`：不能把现有 `control()` 的 completed/run-success 条件搬过来而造成循环等待。此阶段验证同 attempt prerequisite jobs 完成；run 结束后 controller 再要求 release-record success。
- Release 必须覆盖合法 early-success 固定版本，哪怕 source 已陈旧/PR 已关闭/没有 PR alias；这类 Release `make_latest=false`，说明固定镜像存在但浮动标签未更新。默认显式 `make_latest=false`，不得使用 API 默认 true 或 legacy。
- 正式 Release 仅在当前 main/pin/SHA 仍符合推广条件且两 GHCR latest 均回读为该固定双索引时 `make_latest=true`。release-record 与 publisher/retention 使用同一 `ghcr-publication-<repo>` job concurrency；因为 publish 和 recorder 是不同 job，其他 publish 可能插入，recorder 必须重新回读，而不能信任先前 promotion flag。
- 若 alias 失败但两固定索引已验证，存在两种可评估行为：a) 本次不记 Release，任务失败并通过重试补齐；b) 以 `fixed_verified=true` 在 always recorder 中记录固定发布事实并写明 alias failed、`make_latest=false`，全链路仍失败。用户要求“每次发布的镜像”更支持 b；两种都不得把 alias failure 变成整体成功。PRD/design 需明确此选项。
- 补齐 `release_control.JOBS`、updater completed-run readiness 与 main failure needs/判定。若已有完整固定镜像但 Release 不在，优先只重试可信 recorder，避免以 rebuild 同 tag 当作补文案手段；若暂时只支持 CI rerun，必须重核源/digest，不把新 digest 静默替代既有固定版。

### Content and baseline contract

每份 Release 至少包含：

- 完整固定 version、stable/beta、两镜像 tag 与 immutable digest、linux/amd64 + linux/arm64。
- 精确 source commit/link、关联 PR/link（可验证时）、Actions run/attempt/link。
- 当前 TeslaMate official tag + commit，以及上一有效 baseline 的上游 tag；变更时明确 `vOLD → vNEW`、官方 Releases/link 与官方 compare/link。同 upstream 说明上游版本未变，列本项目可读变更。
- 浮动标签状态（promoted/skipped/failed）和有限固定原因；不要暗示镜像发布已部署服务。
- 用户可读的本项目变化。建议建立轻量 source-controlled `CHANGELOG.md`/release-note 条目，为有用户影响的本地改动留说明；候选 SHA 的条目只当数据读取。GitHub generated notes 可作有来源的 PR/commit 补充，但不能替代“上游旧→新版本”或自动声称具体功能改动。
- 只改 pin 的自动跟进可明确“本次跟随上游 TeslaMate vOLD → vNEW，本项目补丁/adapter 功能未新增”，但该说法应由 source diff 校验支撑，不能只凭 `upstream/` 分支名。

baseline 不得简单选 REST newest created release：beta 会污染正式基线，陈旧 run 也可能晚到。正式用已记录且 source 为当前 source ancestor 的前一 stable Release；beta 用同候选流的 previous release 或可信 main/merge-base，并注明语义。若跨分支无可证明 baseline，则明确 baseline unavailable，不制造可读差异。分页与 compare inventory 必须有界并拒绝 truncation/重复。

首次启用且没有历史 GeoRelay Release：标明“首个有发布记录的版本”，列当前 upstream、有效本地条目及确切 source；旧 upstream 若可由可信源父 commit pin证明可以注明，其余不虚构“上次发布”。无需未经验证回填所有历史 GHCR 组。

### Source tag and idempotency

- Git tag 名等于固定 image version，必须解引用到 exact source SHA。`target_commitish=source SHA` 对已有 tag 会被 API 忽略，因此创建前后都须回读 tag，而不能仅比较 Release target_commitish 字段。
- 按 exact tag 查询；不存在才创建。只有明确 404 表示 absent，权限/网络错误不应触发替代创建。tag 存在但指向错 source、已有 foreign/malformed Release 或 provenance/digest 不匹配必须 fail closed，不移动 tag、不 force、不覆盖他人 Release。
- 使用结构化 ownership/provenance marker 绑定 source/upstream/channel/digests/baseline，后续重跑匹配则复用，允许安全完成此前缺失步骤。POST/PATCH 响应丢失后回读 exact tag/id 确认，不盲目重复创建；422 collision 也回读核对。
- Release markdown 通过 JSON payload/stdin 交给 gh API，不插入 shell 或 GitHub expression 执行；PR title/upstream body/候选 changelog 均是文本数据。错误只固定分类，不打印 API 响应、secret 或远端日志。
- 若维护已有 body，明确只操作本 recorder-owned block，保留人工补充；immutable enabled Release 的限制应通过 readback检测。至少不要默默覆盖有人工修改/错误归属的 body。

### Bootstrap and security caveats

1. 首个引入 recorder 的 PR 中可信 main 尚无新脚本。不能为了给该 PR beta 创建 Release 而 privileged checkout 候选实现。规划应明确首次任务 beta 的 bootstrap 边界：离线/CI mock 验证，用户明确审阅合并后首次 main 正式 Release 才启用 trusted recorder；不以此为自动合并授权，不把 bootstrap skip 当作完整发布链成功。
2. 固定 main recorder 与 job isolation 解决“候选脚本获得 contents write”，不等于任何同仓恶意 workflow 修改都安全。若 job workflow 本身来自可编辑候选，仓库已有 workflow 审阅规则仍是权限边界；reusable trusted workflow 更强。不要用 pull_request_target 执行候选。
3. 当前 GitHub 官方 Releases 文档明确指出：若 resolved target commit 相对 default branch 增改 `.github/workflows/`，create/update Release 可能要求 Workflows:write；GITHUB_TOKEN 无法被授予该权限。包括修改 CI 的 beta 候选和某些陈旧 formal source。因此不能未经验证保证仅 contents write 的 token 可创建每种 exact-source tag/Release，也不能把 target 改 main 掩盖 source mismatch。
4. Git refs 官方页说明可先创建 exact SHA ref；但本次只读研究没有实际 GITHUB_TOKEN tag写入测试，未证明提前创建 tag可合法解决上述限制。实现需用 repo native token 在授权的发布验证阶段验证 exact ref + existing-tag Release 路径，不引入未经授权 PAT、App token 或 token 扩权；失败应报告 tag/release permission stage 并阻断 ready。官方页面目前展示 API 2026-03-10 信息，即便 query 为 2022-11-28；源码仍 pin 2022-11-28，因此行为差异需要 live 验证，不能把文档推断当实测结论。

### Related specs

- `.trellis/spec/backend/index.md`：标准库/现有 scripts 结构、最少必要改动、禁止生产操作。
- `.trellis/spec/backend/quality-guidelines.md:9-15`：双架构 gating、已测试 artifact、immutable/latest、 source freshness、失败传播、不部署。
- 同文件 `:29-82`：verify 汇总、shared publication/retention lock、不可把单包/缺架构当完整组。
- 同文件 `:125-174`：beta/source/OCI/Actions provenance、可信 main controller、bot直接main收尾、secret-safe失败通知与精确 tests。
- `.trellis/workflow.md` Phase 1：规划文档完成后仍需 review gate；本研究不构成实施或合并批准。
- 用户 AGENTS.md：只有明确要求合并当前 PR/分支才可入 main。研究建议只分析既有自动化流程如何保持 ready 的完整性，不触发或扩张当前任务合并权限。

### External references (read live, 2026-10-03)

- GitHub REST Releases — create/update/get by tag/latest/generate notes：<https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#create-a-release>。`make_latest` 默认 true，prerelease不可latest；已有 tag 时 target_commitish无效；有 workflow target 权限注记。
- Generated notes：<https://docs.github.com/en/rest/releases/releases?apiVersion=2022-11-28#generate-release-notes-content-for-a-release>。返回内容不保存；`previous_tag_name` 明确差异基线。
- Git references：<https://docs.github.com/en/rest/git/refs?apiVersion=2022-11-28#create-a-reference>。reference绑定 SHA，创建前后需读回；未测试 live 写权限。
- Git tag objects：<https://docs.github.com/en/rest/git/tags?apiVersion=2022-11-28#create-a-tag-object>。annotated tags需解引用，不把 tag object SHA当source commit。
- Actions workflow_run：<https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run>。default-branch observer 可以有 write权限，即便前序无权限；官方警告不要在 privileged observer 执行 untrusted code。
- GITHUB_TOKEN-triggered events：<https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow#triggering-a-workflow-from-a-workflow>。workflow_dispatch/repository_dispatch例外；不能用普通 bot write事件保证递归observer链，现有直接main实践继续保留。

### Focused test matrix

| 类别 | 必须复现的行为 |
| --- | --- |
| 实际发行组 | 两包各精确 amd64/arm64 +合法OCI才可记录；缺包/缺架构/重复平台/tampered manifest/config/错source或version零Release写入 |
| 源码绑定 | PR head≠synthetic merge SHA；tag指错source、annotated tag未解引用、source/pin与payload不符均拒绝；现有 wrongtag不移动 |
| 权限隔离 | Release job/reusable workflow运行main源码，candidate只通过API读文本；publish无contents write；checkout不持久credential、无candidate executable/cache/artifact加载 |
| 触发 | stable push/publish dispatch、same-repo PR、linked/unlinked beta；fork/check-only/metadata-only/failed build零记录；bot main无需workflow_run observer仍直接完成 |
| 当前run | recorder允许run in_progress但拒绝wrong run/attempt/workflow/jobs/verify provenance；最终 controller缺/失败release-record不ready |
| 浮动状态 | 无PR和陈旧source合法固定版本仍记录但不latest；两alias部分失败不latest且总体失败；source变化后重读避免旧Release抢latest |
| 版本说明 | 自动pin-only显示精确old→new +官方Release/compare；sameupstream显示本地可读变化；mixed update两类分别说明；首次无prior明确baseline；beta不成为formal baseline |
| 幂等/修复 | exact Release重跑零重复；tag-only/缺Release只补所需步骤；POST响应丢失/422回读确认；wrongmarker/digest/foreign/人工body不被覆盖；unknown API failure不当404 |
| updater | publish success但Release缺/失败不能already_started；真正完整success不重复dispatch；queued/inprogress仍抑制重复；check-only不抑制publish |
| controller/通知 | 新required job纳入 ready；main direct finalizer包含Release失败且beta/no-op仍success；通知不重复、不泄secret；旧main observer提前退出仍成立 |
| bootstrap | 初始任务PR无main recorder明确未启用；没有fallback候选privileged execution或隐式merge；合并后首次Release正确标明baseline |
| GitHub权限 | live授权阶段核实native GITHUB_TOKEN exact SHA tag与existing-tag Release，包括workflow修改beta/陈旧source；失败保留truthful stage且不换main/tag、不偷偷PAT |
| 输入与有界 | PR/title/changelog中的shell/Markdown边界只能作为文本；结构化JSON正文；API pagination/size/deadline限界、重复及truncation拒绝；stderr无远端body/token |

复用 Python unittest/fake API/OCI、真实 publisher shell fake registry 和现有 workflow门控回归；新逻辑不需要框架、ORM、独立版本服务或额外外部模型。真实 GitHub Release 写入、双架构线上结论和新 token权限尚未执行，应明确待验证。

## Caveats / Not Found

- 未执行 git 操作、GitHub写请求、真实Release/tag创建、真实镜像发布、合并或部署；本文件为静态/官方文档只读研究。
- 当前 code 没有 GitHub Release writer、source-controlled CHANGELOG、structured publication report，因此内容输入、bootstrap与alias-failure记录策略需要在 design 中定案。
- 本次使用历史 memory 的 release安全线索作检索提示，并完全以当前源码复核；历史包名/仅main发布规则已过时，不采用为当前事实。若主会话引用memory需单独正确citation；本研究结论依据上列当前源码与live官方文档。
- Workflows:write注记与源码固定 API版本存在可能行为差异，提前创建tag的native-token可行性未实测，是实现发布验证前需解决的关键限制。

补充集成证据：`scripts/notify_bark.py:17,54` 当前 stage与failed_jobs白名单不含release-record；若记录该job失败，必须同步允许有限固定值并测试，避免通知器拒绝新job而吞掉失败通知。
