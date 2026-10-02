# teslamate

基于官方 [TeslaMate](https://github.com/teslamate-org/teslamate) 的高德地图适配项目。

计划通过独立的 Nominatim 兼容服务接入高德地址解析，并为官方源码维护最小的服务地址配置补丁，便于持续跟进官方版本。

当前已初始化 Git 与 Trellis 开发环境；高德适配器、补丁和自动更新流程尚未实现。

地图底图切换需要单独处理。项目初始化不会修改现有 TeslaMate 部署或数据库。

不要提交 API Key、Tesla 凭据、运行配置、数据库备份或车辆位置数据。
