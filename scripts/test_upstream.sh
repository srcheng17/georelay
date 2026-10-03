#!/usr/bin/env bash
# Isolated upstream ExUnit checks. No production containers, ports or volumes.
set -euo pipefail

if [[ $# != 1 ]]; then
  echo "Usage: scripts/test_upstream.sh <prepared-upstream-directory>" >&2
  exit 2
fi
root=$(cd "$(dirname "$0")/.." && pwd)
source_dir=$(cd "$1" && pwd)
python3 - "$root" "$source_dir" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from prepare_upstream import verify_patched
verify_patched(sys.argv[2])
PY

name="georelay-check-$(date +%s)-$$"
cleanup() {
  docker rm -fv "$name-elixir" "$name-db" >/dev/null 2>&1 || true
  docker network rm "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$name" >/dev/null
docker run --detach --name "$name-db" --network "$name" --network-alias db \
  --tmpfs /var/lib/postgresql --env POSTGRES_PASSWORD=isolated-test-only \
  postgres:18-trixie >/dev/null
for attempt in {1..60}; do
  if docker exec "$name-db" pg_isready --username postgres >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" == 60 ]]; then
    echo "Isolated test database did not become ready" >&2
    exit 1
  fi
  sleep 1
done
docker run --rm --name "$name-elixir" --network "$name" \
  --mount "type=bind,src=$source_dir,dst=/upstream" --workdir /upstream/elixir \
  --env MIX_ENV=test --env DATABASE_HOST=db --env DATABASE_USER=postgres \
  --env DATABASE_PASS=isolated-test-only --env DATABASE_NAME=teslamate_adapter_test \
  --env ELIXIR_ASSERT_TIMEOUT=1000 --env 'ERL_FLAGS=+S 4:4' \
  elixir:1.20.3-otp-29 bash -euc '
    mix local.hex --force
    mix local.rebar --force
    mix deps.get
    mix compile --warnings-as-errors
    mix format --check-formatted \
      lib/teslamate/http.ex lib/teslamate/locations.ex lib/teslamate/locations/geocoder.ex \
      lib/teslamate/locations/address.ex lib/teslamate/locations/local_identities.ex \
      priv/repo/migrations/20261003000000_prepare_application_address_identities.exs \
      test/teslamate/http_test.exs test/teslamate/settings_test.exs \
      test/teslamate/locations/geocoder_adapter_test.exs \
      test/teslamate/locations/addresses_adapter_test.exs \
      test/teslamate/locations/addresses_test.exs \
      test/teslamate/locations/local_identities_test.exs
    mix test --warnings-as-errors \
      test/teslamate/http_test.exs test/teslamate/settings_test.exs \
      test/teslamate/locations/addresses_test.exs \
      test/teslamate/locations/geocoder_test.exs \
      test/teslamate/locations/geocoder_adapter_test.exs \
      test/teslamate/locations/addresses_adapter_test.exs \
      test/teslamate/locations/local_identities_test.exs
  '
