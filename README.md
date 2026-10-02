# TeslaMate AMap address adapter

English | [简体中文](README.zh-CN.md)

AMap place names and addresses for your self-hosted [TeslaMate](https://github.com/teslamate-org/teslamate) drive and charging records. This repository contains the source patches, a standalone address adapter and the build workflows.

> This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

[Getting started](#getting-started) · [Features](#features) · [Screenshots](#screenshots) · [Updates](#updates) · [Documentation](#documentation)

## Getting started

Run the patched TeslaMate image built from this repository alongside the address adapter. The official TeslaMate image does not support this project's `NOMINATIM_BASE_URL` setting.

1. Build both images using the [source build instructions (Chinese)](docs/AMAP.md#开发与构建).
2. Configure the adapter with an AMap Web Service API key and a Nominatim User-Agent containing your application name and contact information. The [configuration guide (Chinese)](docs/AMAP.md#配置) includes the adapter Compose example.
3. Connect both services to the same Docker network and set this variable on the patched TeslaMate service:

   ```dotenv
   NOMINATIM_BASE_URL=http://amap-adapter:8080
   ```

Keep the adapter's data volume across restarts and upgrades. It stores persistent address identities as well as cached responses. Read the [backup and existing-address compatibility notes (Chinese)](docs/AMAP.md#永久身份与备份) before replacing an existing setup.

## Features

Address lookup uses AMap in mainland China and OpenStreetMap elsewhere. Results include place names and address components such as province, city and road. The [routing notes (Chinese)](docs/AMAP.md#路由与名称) explain regional detection and name selection.

Coordinates remain WGS84 in storage and responses. The adapter converts them to GCJ-02 only for requests to AMap. TeslaMate continues to manage drive records, charging records and stored addresses.

TeslaMate is written in [Elixir](https://elixir-lang.org/), stores vehicle data in PostgreSQL, uses Grafana for visualization and analysis, and publishes vehicle data to a local [MQTT](https://en.wikipedia.org/wiki/MQTT) broker. The features below are from the [upstream README](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md).

<details>
<summary>General features</summary>

- High-precision drive recording.
- Lets the vehicle sleep as soon as possible to avoid extra standby drain.
- Automatic address lookup and custom geofences.
- MQTT integration with Home Assistant, Node-RED and Telegram.
- Multiple vehicles on one Tesla account.
- Charging cost tracking.
- Data import from TeslaFi and tesla-apiscraper.
- Light, dark and system theme modes.
- A web interface in 19 languages, including Simplified and Traditional Chinese, with English as the fallback for untranslated text.

</details>

<details>
<summary>Built-in dashboards</summary>

Each link opens the official dashboard documentation and sample screenshots.

- [Battery health](https://docs.teslamate.org/docs/screenshots/#battery-health)
- [Charge level](https://docs.teslamate.org/docs/screenshots/#charge-level)
- [Charges](https://docs.teslamate.org/docs/screenshots/#charges)
- [Charge details](https://docs.teslamate.org/docs/screenshots/#charge-details)
- [Charging stats](https://docs.teslamate.org/docs/screenshots/#charging-stats)
- [Database information](https://docs.teslamate.org/docs/screenshots/#database-information)
- [Drive stats](https://docs.teslamate.org/docs/screenshots/#drive-stats)
- [Drives](https://docs.teslamate.org/docs/screenshots/#drives)
- [Drive details](https://docs.teslamate.org/docs/screenshots/#drive-details)
- [Efficiency](https://docs.teslamate.org/docs/screenshots/#efficiency)
- [Locations and addresses](https://docs.teslamate.org/docs/screenshots/#location-addresses)
- [Mileage](https://docs.teslamate.org/docs/screenshots/#mileage)
- [Overview](https://docs.teslamate.org/docs/screenshots/#overview)
- [Projected range and battery degradation](https://docs.teslamate.org/docs/screenshots/#projected-range)
- [Vehicle online and sleep states](https://docs.teslamate.org/docs/screenshots/#states)
- [Statistics](https://docs.teslamate.org/docs/screenshots/#statistics)
- [Temperatures](https://docs.teslamate.org/docs/screenshots/#temperatures)
- [Timeline](https://docs.teslamate.org/docs/screenshots/#timeline)
- [Trip](https://docs.teslamate.org/docs/screenshots/#trip)
- [Software update history](https://docs.teslamate.org/docs/screenshots/#updates)
- [Vampire drain](https://docs.teslamate.org/docs/screenshots/#vampire-drain)
- [Lifetime driving map](https://docs.teslamate.org/docs/screenshots/#visited-lifetime-driving-map)

</details>

## Screenshots

These show the upstream TeslaMate interface and dashboards. More examples are in the [official screenshot documentation](https://docs.teslamate.org/docs/screenshots/).

![Upstream TeslaMate web interface](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/web_interface.png)

<details>
<summary>Drive details and battery health</summary>

![Upstream TeslaMate drive details dashboard](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/drive.png)

![Upstream TeslaMate battery health dashboard](https://raw.githubusercontent.com/teslamate-org/teslamate/33d200b2fba9d5138803916a788cef5eae31b1aa/website/static/screenshots/battery-health.png)

</details>

## Updates

This project follows stable upstream releases. Builds download the source version recorded in [upstream.json](upstream.json) and apply this repository's patches.

An automated check reports new releases each week. A maintainer reviews the changes and updates the pinned version and patches. CI then tests and builds both images; patch conflicts or failing tests stop the build.

Publishing requires a manual workflow run on `main`. The workflow does not deploy services. See the [release maintenance guide (Chinese)](docs/AMAP.md#版本跟进与发布) for the process and image tags.

## Documentation

- [AMap adapter guide (Chinese)](docs/AMAP.md): configuration, API, builds and backups.
- [TeslaMate documentation](https://docs.teslamate.org/): installation and everyday use.
- [Source and modifications](MODIFICATIONS.md): what this repository changes and how to rebuild it.

## License and source

TeslaMate and the code in this repository are licensed under AGPL-3.0-or-later. The upstream [LICENSE](LICENSE), [NOTICE](NOTICE) and [TRADEMARK.md](TRADEMARK.md) are preserved unchanged. They contain the full license, copyright notices, additional terms and trademark requirements. Source for this modified version and rebuild instructions are documented in [MODIFICATIONS.md](MODIFICATIONS.md).

AMap services and data remain subject to their [documentation and terms](https://lbs.amap.com/api/webservice/guide/api/georegeo). OpenStreetMap data is licensed under [ODbL](https://www.openstreetmap.org/copyright). The code license does not replace those service or data terms.

TeslaMate is an independent project and is not affiliated with, endorsed by, or sponsored by Tesla, Inc. Related trademarks belong to their respective owners. Contributions to the official project must follow its [contribution requirements](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md#license), including its FLA/CLA.

## Credits

- Initial TeslaMate author: [Adrian Kumpf](https://github.com/adriankumpf).
- [TeslaMate contributors](https://github.com/teslamate-org/teslamate/graphs/contributors).
- [Contributors to this repository](https://github.com/srcheng17/teslamate/graphs/contributors).
