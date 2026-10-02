#!/usr/bin/env bash
# Run the built release with its default ENTRYPOINT/CMD against a fresh database.
set -euo pipefail

if [[ $# != 2 ]]; then
  echo "Usage: scripts/test_main_image.sh <app-image> <probe-image>" >&2
  exit 2
fi
script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
wait_seconds=${MAIN_IMAGE_TIMEOUT_SECONDS:-120}
if [[ ! $wait_seconds =~ ^[1-9][0-9]{0,2}$ ]] || (( wait_seconds > 600 )); then
  echo "MAIN_IMAGE_TIMEOUT_SECONDS must be an integer from 1 to 600" >&2
  exit 2
fi

# Keep Docker outside command substitution so Bash can interrupt wait immediately.
command_output=$(mktemp)
command_timeout=20
active_pid=
docker_command() {
  local result=0
  python3 -c '
import signal, subprocess, sys
def cancel(signum, _frame):
    # subprocess.run terminates and reaps its child when this interrupts it.
    raise SystemExit(128 + signum)
signal.signal(signal.SIGTERM, cancel)
signal.signal(signal.SIGINT, cancel)
try:
    result = subprocess.run(["docker", *sys.argv[2:]], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=int(sys.argv[1]))
    sys.stdout.buffer.write(result.stdout)
    sys.exit(result.returncode)
except subprocess.TimeoutExpired:
    sys.exit(124)
except OSError:
    sys.exit(125)
' "$command_timeout" "$@" >"$command_output" &
  active_pid=$!
  wait "$active_pid" || result=$?
  active_pid=
  docker_output=$(<"$command_output")
  return "$result"
}
name="georelay-main-smoke-$(date +%s)-$$"
network_created=false
cleanup() {
  local result=$? command_timeout=2
  trap '' INT TERM
  docker_command rm -fv "$name-probe" "$name-app" "$name-stub" "$name-db" >/dev/null || true
  if ! docker_command container ls --all --filter "name=^/${name}-(probe|app|stub|db)$" --format '{{.Names}}' || [[ -n $docker_output ]]; then
    echo "Main image smoke failed: isolated resource cleanup" >&2
    result=1
  fi
  if ! docker_command network rm "$name" >/dev/null && [[ $network_created == true ]]; then
    echo "Main image smoke failed: isolated resource cleanup" >&2
    result=1
  fi
  rm -f "$command_output"
  if (( result == 0 )); then
    echo "Main image smoke passed: /sign_in HTTP 200, login HTML verified; migrations=$migration_count; core tables present; /notice and /license verified; compiled address checks passed"
  fi
  exit "$result"
}
cancel() {
  if [[ -n $active_pid ]]; then
    kill -TERM "$active_pid" >/dev/null 2>&1 || true
    wait "$active_pid" || true
    active_pid=
  fi
  exit "$1"
}
trap cleanup EXIT
trap 'cancel 130' INT
trap 'cancel 143' TERM
fail() { echo "Main image smoke failed: $1" >&2; exit 1; }
require_running() {
  local component state
  for component in db stub app; do
    docker_command inspect --format '{{.State.Status}} {{.State.ExitCode}}' "$name-$component" || fail "$component state unavailable"
    state=$docker_output
    if [[ $state != 'running 0' ]]; then
      [[ $state =~ ^(created|running|paused|restarting|removing|exited|dead)\ ([0-9]+)$ ]] || fail "$component state invalid"
      fail "$component state=${BASH_REMATCH[1]} exit=${BASH_REMATCH[2]}"
    fi
  done
}

docker_command network create --internal "$name" >/dev/null || fail "isolated network creation"
network_created=true
docker_command run --detach --name "$name-db" --network "$name" --network-alias db \
  --tmpfs /var/lib/postgresql --env POSTGRES_PASSWORD=isolated-test-only \
  --env POSTGRES_DB=georelay_smoke postgres:18-trixie >/dev/null || fail "temporary database start"
docker_command run --detach --pull=never --name "$name-stub" --network "$name" --network-alias stub \
  --mount "type=bind,src=$script_directory/runtime_geocoder_stub.py,dst=/checks/runtime_geocoder_stub.py,readonly" \
  --entrypoint python "$2" /checks/runtime_geocoder_stub.py >/dev/null || fail "fixture service start"
# Do not wait here: the actual release entrypoint must wait and migrate the new DB.
docker_command run --detach --pull=never --name "$name-app" --network "$name" --network-alias app \
  --env DATABASE_HOST=db --env DATABASE_USER=postgres --env DATABASE_PASS=isolated-test-only \
  --env DATABASE_NAME=georelay_smoke --env DISABLE_MQTT=true \
  --env HTTP_BINDING_ADDRESS=0.0.0.0 --env ENCRYPTION_KEY=isolated-smoke-test-only \
  --env NOMINATIM_BASE_URL=http://stub:8080 --env NOMINATIM_LOCAL_IDENTITIES_ONLY=true \
  --mount "type=bind,src=$script_directory/runtime_locations.exs,dst=/checks/runtime_locations.exs,readonly" \
  "$1" >/dev/null || fail "application start"

probe='
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
url = "http://app:4000/sign_in"
try:
    with urlopen(Request(url, headers={"Accept": "text/html", "Accept-Language": "en"}), timeout=2) as response:
        body = response.read(262145).decode("utf-8")
        valid = (response.status == 200 and response.geturl() == url
                 and response.headers.get_content_type() == "text/html"
                 and len(body) <= 262144 and "GeoRelay" in body
                 and all(marker in body for marker in (
                     "id=\"tokens\"", "phx-submit=\"sign_in\"",
                     "name=\"tokens[access]\"", "name=\"tokens[refresh]\"")))
        if not valid:
            sys.exit(2)
    for path, markers in (
        ("notice", ("Copyright", "the TeslaMate contributors", "SPDX-License-Identifier: AGPL-3.0-or-later")),
        ("license", ("GNU AFFERO GENERAL PUBLIC LICENSE", "Version 3, 19 November 2007")),
    ):
        legal_url = "http://app:4000/" + path
        with urlopen(Request(legal_url, headers={"Accept": "text/html"}), timeout=2) as response:
            body = response.read(262145).decode("utf-8")
            if not (response.status == 200 and response.geturl() == legal_url
                    and response.headers.get_content_type() == "text/plain"
                    and len(body) <= 262144 and all(marker in body for marker in markers)):
                sys.exit(2)
    with urlopen("http://stub:8080/health", timeout=2) as response:
        if response.status != 200 or response.read(64) != b"{\"ok\": true}":
            sys.exit(2)
except HTTPError:
    sys.exit(2)
except (URLError, OSError):
    sys.exit(1)
except (UnicodeError, ValueError):
    sys.exit(2)
'
deadline=$((SECONDS + wait_seconds))
while (( SECONDS < deadline )); do
  require_running
  if docker_command run --rm --pull=never --name "$name-probe" --network "$name" \
    --entrypoint python "$2" -c "$probe" >/dev/null; then
    break
  else
    status=$?
    [[ $status == 1 ]] || fail "HTTP login/legal response or fixture probe execution invalid"
  fi
  sleep 1
done
(( SECONDS < deadline )) || fail "HTTP readiness timeout"
require_running
sql="SELECT count(*), to_regclass('public.cars') IS NOT NULL
  AND to_regclass('public.addresses') IS NOT NULL
  AND to_regclass('public.positions') IS NOT NULL
  AND to_regclass('public.drives') IS NOT NULL
  AND to_regclass('public.charging_processes') IS NOT NULL
  AND to_regclass('public.settings') IS NOT NULL FROM schema_migrations;"
docker_command exec --env 'PGOPTIONS=-c statement_timeout=5000 -c lock_timeout=5000' \
  "$name-db" psql --username postgres --dbname georelay_smoke --no-psqlrc \
  --tuples-only --no-align --set ON_ERROR_STOP=1 --command "$sql" || fail "migration query failed"
migrations=$docker_output
[[ $migrations =~ ^([1-9][0-9]*)\|t$ ]] || fail "missing migrations or core tables"
migration_count=${BASH_REMATCH[1]}
require_running
docker_command exec "$name-app" bin/teslamate rpc 'Code.eval_file("/checks/runtime_locations.exs"); :ok' \
  || fail "compiled address RPC failed"
[[ $'\n'$docker_output$'\n' == *$'\nGEORELAY_RUNTIME_LOCATIONS_OK\n'* ]] || fail "compiled address RPC success marker missing"
require_running
exit 0
