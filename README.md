# GeoRelay

English | [简体中文](README.zh-CN.md)

Self-hosted drive and charging records with address lookup through AMap, Baidu Maps and OpenStreetMap. GeoRelay builds a modified application from stable upstream releases and runs address lookup in a standalone adapter.

> This project is an unofficial community tool and is not affiliated with, endorsed by, or supported by the official TeslaMate project.

[Getting started](#getting-started) · [Features](#features) · [Updates](#updates) · [Documentation](#documentation)

## Getting started

Add `georelay-adapter` to your existing TeslaMate stack and use the patched TeslaMate image. Both images support `linux/amd64` and `linux/arm64`. The official TeslaMate image does not support `NOMINATIM_BASE_URL`.

The `georelay` application and `georelay-adapter` images are publicly available on GHCR. Their names cover all supported address providers. Choose a matching Release that includes application-owned addresses; earlier images use a different protocol. The fragment below uses `latest` by default. To pin a release, set `GEORELAY_VERSION` to the same version from the [application image](https://github.com/users/srcheng17/packages/container/package/georelay) and [adapter image](https://github.com/users/srcheng17/packages/container/package/georelay-adapter) pages.

Set `AMAP_KEY` and `NOMINATIM_USER_AGENT` in your stack's `.env`; see [.env.example](.env.example). The default uses AMap Web Services in mainland China and OSM elsewhere. The User-Agent must include your application name and contact information. To use Baidu instead, set `MAINLAND_PROVIDER=baidu`, `BAIDU_AK` and the matching `BAIDU_SK`.

Merge this fragment into your existing Compose configuration. Keep your other TeslaMate environment variables, database, MQTT and Grafana services, and existing volumes.

```yaml
services:
  teslamate:
    image: ghcr.io/srcheng17/georelay:${GEORELAY_VERSION:-latest}
    environment:
      NOMINATIM_BASE_URL: http://georelay-adapter:8080
      GEORELAY_ADDRESS_MODE: application
      # Keep your other TeslaMate settings here.
  georelay-adapter:
    image: ghcr.io/srcheng17/georelay-adapter:${GEORELAY_VERSION:-latest}
    restart: unless-stopped
    environment:
      ADAPTER_CACHE_DB: /data/cache.sqlite3
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

PostgreSQL stores permanent address IDs, original coordinates and provider provenance. The adapter volume holds disposable caches and rate-limit state. Complete [initialization or migration](#existing-addresses-and-backups) before address lookup; retain the existing volume during an upgrade to archive the old identity file. Additional settings are in the [configuration guide (Chinese)](docs/AMAP.md#配置).

Publishing a new `latest` does not update running containers. To update, back up your TeslaMate database and complete any required identity migration, then run these commands from your stack directory:

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

The application owns stable negative address IDs in PostgreSQL and sends IDs, exact WGS84 coordinates and verified provenance to the adapter. The adapter has no database credentials. Its cache can be deleted or recreated without changing permanent addresses. Historical positive IDs are preserved and skipped during local refresh.

For an installation that has never used the old SQLite identity store, start the paired images and explicitly initialize the application:

```sh
docker compose exec -T teslamate bin/teslamate rpc 'IO.inspect(TeslaMate.Locations.LocalIdentities.initialize_fresh(fresh_install: true))'
docker compose exec -T teslamate bin/teslamate rpc 'IO.inspect(TeslaMate.Locations.LocalIdentities.initialize_fresh(apply: true, fresh_install: true))'
```

The first command audits without writing. An empty PostgreSQL address table does not prove a fresh installation. Existing installations must first [audit and import their old identity store (Chinese)](docs/AMAP.md#永久身份与备份). Upgrade both images together; address lookup stays disabled until initialization or import completes.

Cache expiry only refreshes the adapter response. Changing the application's address language explicitly refreshes stored text while preserving IDs, coordinates and drive/charging associations. AMap and Baidu use their service's default language.

Back up PostgreSQL as the permanent data source. Keep the old SQLite snapshot as a migration/rollback archive; the new cache need not be restored alongside the database. After new application-owned IDs are allocated, downgrading images alone cannot safely return to the old identity store. The migration guide explains the matching-backup boundary.

## Features

Address lookup defaults to AMap in mainland China and OpenStreetMap elsewhere. Set `MAINLAND_PROVIDER=baidu` to use Baidu in mainland China, or `GEOCODER_PROVIDER=amap|baidu|osm` to use a single service. The versioned POST interfaces also accept a provider field for an individual request. TeslaMate uses the configured default.

Results include place names and address components such as province, city and road. Switching providers keeps the same address identity and original coordinates. Baidu overseas lookup requires the appropriate API permissions. For AMap overseas service, set `GEOCODER_PROVIDER=amap`, `AMAP_API_REGION=global` and provide its Web Service key; the default AMap profile accepts mainland results. The automatic policy uses OSM elsewhere. The [routing notes (Chinese)](docs/AMAP.md#路由与名称) explain regional detection and name selection.

Coordinates remain WGS84 in storage and responses. The adapter converts mainland query coordinates to GCJ-02 for AMap; Baidu accepts WGS84 directly. Address lookup does not change the map tiles in the web interface. TeslaMate continues to manage drive records, charging records and stored addresses.

## Updates

The project checks official stable releases every six hours and creates a PR with a pinned tag and commit. Same-repository PRs and controlled branch publications produce beta images after native amd64/arm64 tests, including the packaged adapter suite and the application's startup, migrations and address contract. Beta images do not update `latest`. Upstream names, translations, assets, legal text and Dockerfile stay unchanged; preparation only applies the address patches. Patch conflicts and failed checks stop publication.

The release controller merges a successful beta candidate only while its tested PR commit and main baseline remain current and branch protection allows it. It then explicitly starts a main build to publish the formal version and `latest`. Main image-affecting changes also publish checked images; README files, guides, agent instructions, Trellis metadata and Paseo settings use lightweight checks. Successful, metadata-only and check-only runs send no notification; image build, test, merge or publication failures send Bark when the repository's `BARK_URL` Actions Secret is configured. The controller must first be reviewed and merged into main before this automation takes effect.

Each verified pair has a [GitHub Release](https://github.com/srcheng17/georelay/releases) with readable GeoRelay changes, exact image digests, source and upstream version. Automatic updates show the old → new TeslaMate version and official change links; beta entries are prereleases. Missing notes can be repaired without rebuilding images. Fixed publication and floating alias results are separate; a failed alias update keeps the workflow failed.

Both images use the same upstream-version and source-commit tag. A PR's floating beta alias is `beta-pr-N`; stable `latest` follows the reviewed pin on main. Publishing images does not update running services. Weekly retention keeps `latest` and the ten newest complete formal releases and their architecture manifests. Beta and other unrecognized records remain protected; beta cleanup is deferred. See the [release guide (Chinese)](docs/AMAP.md#版本跟进与发布) for setup, tags and maintenance.

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
