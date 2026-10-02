# Validation

## Naming and source changes

The user confirmed `georelay` and `georelay-adapter` after review of the upstream trademark policy. Both packages already exist publicly. Publication and retention now use these fixed names within the repository owner's namespace, independently of the repository basename. Old packages remain untouched. Runtime, patches, GeoRelay branding, service names and version format are unchanged.

Independent Trellis check passed 89 Python tests in 48.016 seconds, including publication failure gates, repository renaming and mixed-case owner cross-boundary regressions. Bash syntax for two scripts, compilation/AST of 14 Python files, 48 local documentation links/anchors, example Compose validation and checksum-verified actionlint 1.7.12 on three workflows passed. No separate type checker is configured.

## Published content and isolated runtime validation

Main source `0b0e6ac58dc8cc196e6d43210d929e9cd3e8a3e7` passed native amd64/arm64 builds, verify and publication in [run 37049425314](https://github.com/srcheng17/georelay/actions/runs/37049425314). Anonymous registry reads confirmed both latest indexes exactly match their fixed version `v4.3.0-georelay-0b0e6ac58dc8cc196e6d43210d929e9cd3e8a3e7`:

- georelay: `sha256:ed61e9f5145d7e857860f3306d78c5a118496159b4d82f883d2d6871c734de2b`
- georelay-adapter: `sha256:b50570d50fe27b04ffb436be39116a58f04951952d9baeafb658545a297b2499`

A verified private dump was fully restored into an isolated PostgreSQL 18 instance. Before app startup, the clone's private tokens were removed and vehicle recording disabled. The app/database network blocked external TCP; only the adapter had an external network. A separate offline Repo/Vault evaluation successfully decrypted the old token with the existing encryption key without starting the Tesla API or printing plaintext.

Five migrations completed on the clone, from 100 to 105. Four historical charging-energy values changed; VIN, phase and cost changes were zero. Counts of existing relevant tables were preserved, and every field of all 1,087 existing addresses remained unchanged. No old negative identities existed. New import tables were empty.

Real AMap requests used a public landmark. Reverse/lookup, language identity continuity, adapter restart persistence and app geocoder-to-signed-bigint database roundtrip passed. The adapter ran without a host port as a nonroot user with a read-only root filesystem. Its test key was passed through stdin into a private tmpfs file. Four test containers, two networks and two volumes were deleted; no test resources or keys remain.

## Authorized Dockhand deployment

The original image-switch request remained authorized after naming confirmation. Production had no active drive/charge and no negative address identities. The old recorder was stopped through Dockhand, and a fresh 58,278,521-byte custom-format dump was validated with pg_restore listing before deployment. The earlier dump's full isolated restoration establishes the recovery mechanism; neither backup is committed to Git.

Compose was saved and read back through the native API. Dockhand deployment job `c7ab7381-8eb6-415f-a9c7-97b39ad454f2` completed successfully with pull/build/force-recreate disabled. The locally pulled latest images match the exact tested digests. The application now uses georelay and the new georelay-adapter service; map credentials reside only in the adapter, with local-identity mode enabled and a permanent private volume.

Both new containers are healthy with zero restart count. Database and MQTT container IDs/start times are unchanged. Compose dependency changes also recreated Grafana; its image, configuration, bind data and readiness remain unchanged. Existing service environment values, ports, mounts, restart policies and native encrypted variables were compared without exposing values. Native schedule definitions remain unchanged; the new adapter was not enrolled in automatic updates. Separate 03:00 native updates changed Komga/MyTessAPI during this session and are not deployment actions from this task.

Production migration count is 105. Address, drive, charge and charging-process counts match the stopped-writer backup baseline; the complete address hash remains identical. Auth, recorder-owner/process-health and loaded-response booleans are true. A production read-only geocoder RPC confirmed real public-landmark reverse/lookup through the adapter without inserting PostgreSQL addresses. Web, Grafana and the existing TeslaMate API returned HTTP 200. Bounded private log inspection found no unauthorized, fatal or geocoder-error categories.

Energy/phase migrations cannot be undone by image downgrade; rollback requires the verified full database backup with a single writer. No real Tesla command/wake was issued, and no new location-record claim is made. Baidu credentials and overseas provider permissions were not part of live validation.

## Pull request

The package-name source optimization is separate from the already published runtime content used above. [PR #8](https://github.com/srcheng17/georelay/pull/8) is open from `feat/georelay-image-names`; auto-merge is disabled and no main/PR merge is authorized or performed. Local/full-scope checks passed; native PR checks are tracked on the PR and will be reported to the user when they finish.
