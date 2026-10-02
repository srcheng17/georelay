# GeoRelay

English | [简体中文](README.zh-CN.md)

Self-hosted drive and charging records with address lookup through AMap, Baidu Maps and OpenStreetMap. GeoRelay builds a modified application from stable upstream releases and runs address lookup in a standalone adapter.

> This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

[Getting started](#getting-started) · [Features](#features) · [Screenshots](#screenshots) · [Updates](#updates) · [Documentation](#documentation)

## Getting started

Add `georelay-adapter` to your existing TeslaMate stack and use the patched TeslaMate image. Both images support `linux/amd64` and `linux/arm64`. The official TeslaMate image does not support `NOMINATIM_BASE_URL`.

The `georelay` application and `georelay-adapter` images are publicly available on GHCR. Their names cover all supported address providers. The fragment below uses `latest` by default. To pin a release, set `GEORELAY_VERSION` to the same version from the [application image](https://github.com/users/srcheng17/packages/container/package/georelay) and [adapter image](https://github.com/users/srcheng17/packages/container/package/georelay-adapter) pages.

Set `AMAP_KEY` and `NOMINATIM_USER_AGENT` in your stack's `.env`; see [.env.example](.env.example). The default uses AMap Web Services in mainland China and OSM elsewhere. The User-Agent must include your application name and contact information. To use Baidu instead, set `MAINLAND_PROVIDER=baidu`, `BAIDU_AK` and the matching `BAIDU_SK`.

Merge this fragment into your existing Compose configuration. Keep your other TeslaMate environment variables, database, MQTT and Grafana services, and existing volumes.

```yaml
services:
  teslamate:
    image: ghcr.io/srcheng17/georelay:${GEORELAY_VERSION:-latest}
    environment:
      NOMINATIM_BASE_URL: http://georelay-adapter:8080
      NOMINATIM_LOCAL_IDENTITIES_ONLY: "true"
      # Keep your other TeslaMate settings here.
  georelay-adapter:
    image: ghcr.io/srcheng17/georelay-adapter:${GEORELAY_VERSION:-latest}
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

Keep `amap-data` across restarts and upgrades: it stores persistent address identities as well as cached responses. Read [existing addresses and backups](#existing-addresses-and-backups) before replacing an existing setup. Additional settings are in the [configuration guide (Chinese)](docs/AMAP.md#配置).

If you already use the earlier `teslamate-amap` images, change the two image references to `georelay` and `georelay-adapter` and add the local-identities setting above. Keep your existing Compose project, data volume and sidecar service name; when that name is `amap-adapter`, retain `http://amap-adapter:8080` and use `amap-adapter` in the commands below. Existing image packages remain available, but new releases use the GeoRelay names. `GEORELAY_VERSION` replaces the earlier `TESLAMATE_AMAP_VERSION` example variable.

Publishing a new `latest` does not update running containers. To update, back up your TeslaMate database and adapter data, then run these commands from your stack directory:

```sh
docker compose pull teslamate georelay-adapter
docker compose up -d teslamate georelay-adapter
```

<details>
<summary>Build the images from source</summary>

For a local build, run these commands from the repository root and use `georelay:local` and `georelay-adapter:local` in the Compose fragment. The target directory `/tmp/georelay-build` must not exist or must be empty.

```sh
python3 scripts/prepare_upstream.py /tmp/georelay-build
docker build -t georelay:local /tmp/georelay-build
docker build -t georelay-adapter:local adapter
```

</details>

### Existing addresses and backups

New addresses use permanent local negative IDs. With `NOMINATIM_LOCAL_IDENTITIES_ONLY=true` in the patched application, existing positive IDs are left unchanged and skipped during language refresh, so they cannot block new addresses in the same batch. The adapter does not forward them to OSM: some third-party versions use positive hashes that look like OSM IDs. Importing or repairing those addresses requires a separate migration.

Cache expiry refreshes the adapter's response only. It does not update existing PostgreSQL rows. Changing the address language in the application triggers an explicit refresh of local addresses, including place names, roads, house numbers and raw responses; their IDs and coordinates stay unchanged. AMap and Baidu currently return their default language even when another language is selected.

Back up the adapter's identity database together with your application database. From your actual stack directory, use the same Compose file and project options you use to run that stack:

```sh
snapshot="adapter-snapshot-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
docker compose exec -T georelay-adapter python -m adapter.server --backup "/data/$snapshot"
docker compose cp "georelay-adapter:/data/$snapshot" "./$snapshot"
chmod 600 "./$snapshot"
```

The backup contains location data. Store it securely off the Docker host, then remove the temporary snapshot inside `/data` when you have verified the copy. The command uses SQLite's online backup API; do not copy the active database file. To restore, stop the adapter and restore the complete identity database that matches your application data before restarting it.

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

GeoRelay uses its own name and removes the upstream logos. The interface and dashboard features come from the upstream application; its [screenshot documentation](https://docs.teslamate.org/docs/screenshots/) shows those features under the upstream branding.

## Updates

The project checks for official stable releases every six hours. When a new version appears, automation pins its tag and commit in an update PR, checks the upstream legal files, applies the patches, and runs tests and builds on both CPU architectures. Successful builds publish new version tags to GHCR. Both version indexes must pass verification before `latest` is updated. Changes to LICENSE, NOTICE or TRADEMARK.md require manual review; patch conflicts or failed checks stop publication.

Image-affecting changes on `main` also build and publish checked images. README files, guides, agent instructions, Trellis metadata, and Paseo settings run lightweight checks; other changes, including image legal files and modification notices, run the full dual-architecture checks. Manual validation always runs the full build. Version tags include the upstream version and source commit; `latest` follows verified releases. The workflow does not merge PRs or update running services.

Weekly retention keeps `latest` and the ten newest complete releases, including their architecture manifests. Incomplete or unrecognized records remain for review. Mirror older releases you need to keep pulling. See the [release guide (Chinese)](docs/AMAP.md#版本跟进与发布) for tag selection, cleanup previews, and maintenance.

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
- [Contributors to this repository](https://github.com/srcheng17/georelay/graphs/contributors).
