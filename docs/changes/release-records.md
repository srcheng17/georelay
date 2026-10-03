# 镜像版本与 Release 更新记录

GeoRelay 的完整双镜像固定版本会对应一份 GitHub Release，列出本项目更新、TeslaMate 上游版本、精确源码和两个镜像的 digest。跟随官方更新时显示上游旧版本 → 新版本及官方变更链接；同上游版本的发布显示 GeoRelay 改动。beta 使用预发布 Release，只有实际当前正式双镜像 latest 才能成为 GitHub latest。

固定镜像和浮动标签的结果分别记录。固定镜像成功、浮动标签跳过或失败时，Release 保留已验证镜像事实；浮动标签失败仍使发布流程失败。缺少 Release 的发行不算完整完成。补录只验证现存镜像和原 CI 证据，不重建镜像、不重新推送固定标签，不触发运行容器更新。

现有版本格式保持不变：正式版为 `<upstream-tag>-georelay-<full-source-sha>`，beta 为 `<upstream-tag>-georelay-beta-<full-source-sha>`。Release 的 Git tag 指向该精确源码，不移动已有 tag。首次可信记录器需要经审阅合入 main 后才能启用；之前的 beta 显示 `bootstrap_not_enabled`，不能作为完整发布通过。默认 GitHub 令牌对修改 workflow 的 beta 源码创建精确 tag/Release 的能力仍需获授权后实测；权限失败明确阻断，不替换凭据或改用 main 源码。
