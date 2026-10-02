# TeslaMate address adapter

English | [简体中文](README.zh-CN.md)

AMap, Baidu Maps and OpenStreetMap address lookup for your self-hosted [TeslaMate](https://github.com/teslamate-org/teslamate) drive and charging records. This repository contains the source patches, a standalone address adapter and the build workflows.

> This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

[Getting started](#getting-started) · [Features](#features) · [Screenshots](#screenshots) · [Updates](#updates) · [Documentation](#documentation)

## Getting started

Add `amap-adapter` to your existing TeslaMate stack and use the patched TeslaMate image. Both images support `linux/amd64` and `linux/arm64`. The official TeslaMate image does not support `NOMINATIM_BASE_URL`.

The fragment below uses the published `latest` images by default. To pin a release, set `TESLAMATE_AMAP_VERSION` to the same version from the [TeslaMate image](https://github.com/users/srcheng17/packages/container/package/teslamate-amap) and [adapter image](https://github.com/users/srcheng17/packages/container/package/teslamate-amap-adapter) pages.

Set `AMAP_KEY` and `NOMINATIM_USER_AGENT` in your stack's `.env`; see [.env.example](.env.example). The default uses AMap Web Services in mainland China and OSM elsewhere. The User-Agent must include your application name and contact information. To use Baidu instead, set `MAINLAND_PROVIDER=baidu`, `BAIDU_AK` and the matching `BAIDU_SK`.

Merge this fragment into your existing Compose configuration. Keep your other TeslaMate environment variables, database, MQTT and Grafana services, and existing volumes.

```yaml
services:
  teslamate:
    image: ghcr.io/srcheng17/teslamate-amap:${TESLAMATE_AMAP_VERSION:-latest}
    environment:
      NOMINATIM_BASE_URL: http://amap-adapter:8080
      # Keep your other TeslaMate settings here.
  amap-adapter:
    image: ghcr.io/srcheng17/teslamate-amap-adapter:${TESLAMATE_AMAP_VERSION:-latest}
    restart: unless-stopped
    environment:
      GEOCODER_PROVIDER: "${GEOCODER_PROVIDER:-auto}"
      MAINLAND_PROVIDER: "${MAINLAND_PROVIDER:-amap}"
      AMAP_API_REGION: "${AMAP_API_REGION:-mainland}"
      AMAP_KEY: "${AMAP_KEY:-}"
      BAIDU_AK: "${BAIDU_AK:-}"
      BAIDU_SK: "${BAIDU_SK:-}"
      NOMINATIM_USER_AGENT: "${NOMINATIM_USER_AGENT:?Set NOMINATIM_USER_AGENT in .env}"
    volumes:
      - amap-data:/data
    read_only: true
    tmpfs:
      - /tmp:size=16m,mode=1777
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
volumes:
  amap-data:
```

Compose's default network lets the two services reach each other. If TeslaMate uses a custom network, add the adapter to that network and keep outbound access to the address services. The adapter does not need a host port.

Keep `amap-data` across restarts and upgrades: it stores persistent address identities as well as cached responses. Read the [backup and existing-address compatibility notes (Chinese)](docs/AMAP.md#永久身份与备份) before replacing an existing setup. Additional settings are in the [configuration guide (Chinese)](docs/AMAP.md#配置).

Publishing a new `latest` does not update running containers. To update, back up your TeslaMate database and adapter data, then run these commands from your stack directory:

```sh
docker compose pull teslamate amap-adapter
docker compose up -d teslamate amap-adapter
```

<details>
<summary>Build the images from source</summary>

For a local build, run these commands from the repository root and use `teslamate-amap:local` and `amap-adapter:local` in the Compose fragment. The target directory `/tmp/teslamate-amap-build` must not exist or must be empty.

```sh
python3 scripts/prepare_upstream.py /tmp/teslamate-amap-build
docker build -t teslamate-amap:local /tmp/teslamate-amap-build
docker build -t amap-adapter:local adapter
```

</details>

## Features

Address lookup defaults to AMap in mainland China and OpenStreetMap elsewhere. Set `MAINLAND_PROVIDER=baidu` to use Baidu in mainland China, or `GEOCODER_PROVIDER=amap|baidu|osm` to use a single service. `/reverse` and `/lookup` also accept `provider=amap|baidu|osm` for an individual request. TeslaMate uses the configured default.

Results include place names and address components such as province, city and road. Switching providers keeps the same address identity and original coordinates. Baidu overseas lookup requires the appropriate API permissions. For AMap overseas service, set `GEOCODER_PROVIDER=amap`, `AMAP_API_REGION=global` and provide its Web Service key; the default AMap profile accepts mainland results. The automatic policy uses OSM elsewhere. The [routing notes (Chinese)](docs/AMAP.md#路由与名称) explain regional detection and name selection.

Coordinates remain WGS84 in storage and responses. The adapter converts mainland query coordinates to GCJ-02 for AMap; Baidu accepts WGS84 directly. Address lookup does not change the map tiles in the web interface. TeslaMate continues to manage drive records, charging records and stored addresses.

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

The project checks for official stable releases every six hours. When a new version appears, automation pins its tag and commit in an update PR, applies the patches, and runs tests and builds on both CPU architectures. Successful builds publish new version tags to GHCR. Both version indexes must pass verification before `latest` is updated. Patch conflicts or failed checks stop publication.

Updates to this repository's `main` branch also build and publish checked images. Version tags include the upstream version and source commit; an update PR records the pin for that build. `latest` follows successful releases, while a version tag or digest lets you choose when to upgrade. The workflow does not merge update PRs or update running services. See the [release guide (Chinese)](docs/AMAP.md#版本跟进与发布) for tag selection and maintenance.

## Documentation

- [Address adapter guide (Chinese)](docs/AMAP.md): configuration, API, builds and backups.
- [TeslaMate documentation](https://docs.teslamate.org/): installation and everyday use.
- [Source and modifications](MODIFICATIONS.md): what this repository changes and how to rebuild it.

## License and source

TeslaMate and the code in this repository are licensed under AGPL-3.0-or-later. The upstream [LICENSE](LICENSE), [NOTICE](NOTICE) and [TRADEMARK.md](TRADEMARK.md) are preserved unchanged. They contain the full license, copyright notices, additional terms and trademark requirements. Source for this modified version and rebuild instructions are documented in [MODIFICATIONS.md](MODIFICATIONS.md).

AMap and Baidu Maps services and data remain subject to their [AMap](https://lbs.amap.com/api/webservice/guide/api/georegeo) and [Baidu Maps](https://lbs.baidu.com/faq/api?title=webapi/guide/webservice-geocoding-abroad-base) documentation and terms. OpenStreetMap data is licensed under [ODbL](https://www.openstreetmap.org/copyright). The code license does not replace those service or data terms.

TeslaMate is an independent project and is not affiliated with, endorsed by, or sponsored by Tesla, Inc. Related trademarks belong to their respective owners. Contributions to the official project must follow its [contribution requirements](https://github.com/teslamate-org/teslamate/blob/33d200b2fba9d5138803916a788cef5eae31b1aa/README.md#license), including its FLA/CLA.

## Credits

- Initial TeslaMate author: [Adrian Kumpf](https://github.com/adriankumpf).
- [TeslaMate contributors](https://github.com/teslamate-org/teslamate/graphs/contributors).
- [Contributors to this repository](https://github.com/srcheng17/teslamate/graphs/contributors).
