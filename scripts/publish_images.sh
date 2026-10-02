#!/usr/bin/env bash
# Publish the checked artifacts only; never rebuild or deploy.
set -euo pipefail

if [[ $# != 1 ]]; then
  echo "Usage: scripts/publish_images.sh <checked-artifacts-directory>" >&2
  exit 2
fi
root=$(cd "$(dirname "$0")/.." && pwd)
artifacts=$1
: "${GITHUB_SHA:?}" "${GITHUB_REF:?}" "${GITHUB_EVENT_NAME:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_ACTOR:?}" "${GHCR_TOKEN:?}"
[[ $GITHUB_SHA =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ $GITHUB_REPOSITORY =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || exit 1
test "$(git rev-parse HEAD)" = "$GITHUB_SHA" || {
  echo "Checked-out source does not match the publication commit" >&2
  exit 1
}
tag=$(python3 - "$root" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from prepare_upstream import load_pin
print(load_pin(Path("upstream.json"))["tag"])
PY
)
if [[ $GITHUB_EVENT_NAME == push && $GITHUB_REF == refs/heads/main ]]; then
  :
elif [[ $GITHUB_EVENT_NAME == workflow_dispatch && ${PUBLISH_REQUESTED:-false} == true ]]; then
  if [[ $GITHUB_REF == "refs/heads/upstream/$tag" ]]; then
    git fetch --quiet --no-tags origin main:refs/remotes/origin/main
    test "$(git show -s --format=%P HEAD)" = "$(git rev-parse origin/main)" || {
      echo "Automatic release branch must have current main as its sole parent" >&2
      exit 1
    }
    [[ $(git diff --name-only origin/main HEAD) == upstream.json ]] || {
      echo "Automatic release branch must differ from main only in upstream.json" >&2
      exit 1
    }
  elif [[ $GITHUB_REF != refs/heads/main ]]; then
    echo "Publication requires main or the matching upstream/<stable-tag> branch" >&2
    exit 1
  fi
else
  echo "Publication requires a main push or an explicit publish dispatch" >&2
  exit 1
fi
GITHUB_TOKEN="$GHCR_TOKEN" python3 - "$root" "$tag" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from check_release import github_json, resolve_tag
from prepare_upstream import load_pin
try:
    pin = load_pin(Path("upstream.json"))
    release = github_json("/releases/tags/" + sys.argv[2])
    if (pin["tag"] != sys.argv[2]
            or release.get("tag_name") != sys.argv[2]
            or release.get("draft") is not False
            or release.get("prerelease") is not False):
        raise ValueError("not a published stable release")
    if resolve_tag(pin["tag"], github_json) != pin["commit"]:
        raise ValueError("pinned official release tag moved")
except (OSError, ValueError, KeyError, TypeError, AttributeError):
    raise SystemExit("Publication requires the pinned official stable release and unchanged tag commit")
PY
for architecture in amd64 arm64; do
  test -s "$artifacts/checked-images-$architecture.tar"
done
version="$tag-amap-$GITHUB_SHA"
repository="ghcr.io/$(printf '%s' "$GITHUB_REPOSITORY" | tr '[:upper:]' '[:lower:]')"
export IMAGE_VERSION="$version" IMAGE_SOURCE="https://github.com/$GITHUB_REPOSITORY"
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin >/dev/null
trap 'docker logout ghcr.io >/dev/null 2>&1 || true' EXIT
for architecture in amd64 arm64; do
  docker load -i "$artifacts/checked-images-$architecture.tar"
  # Both archives use :checked: push this architecture before the next load replaces it.
  for image in teslamate-amap amap-adapter; do
    if [[ $image == teslamate-amap ]]; then
      package="$repository-amap"
    else
      package="$repository-amap-adapter"
    fi
    docker image inspect "$image:checked" | python3 -c '
import json, os, sys
image, = json.load(sys.stdin)
assert (image["Os"], image["Architecture"]) == ("linux", sys.argv[1]), "incorrect image architecture"
labels = image["Config"]["Labels"]
for key, value in {"source": os.environ["IMAGE_SOURCE"], "revision": os.environ["GITHUB_SHA"], "version": os.environ["IMAGE_VERSION"]}.items():
    assert labels["org.opencontainers.image." + key] == value, "incorrect OCI " + key
' "$architecture"
    docker tag "$image:checked" "$package:$version-$architecture"
    docker push "$package:$version-$architecture"
  done
done
for package in "$repository-amap" "$repository-amap-adapter"; do
  docker buildx imagetools create --tag "$package:$version" "$package:$version-amd64" "$package:$version-arm64"
  docker buildx imagetools inspect --raw "$package:$version" | python3 -c '
import json, sys
index = json.load(sys.stdin)
platforms = [(entry["platform"]["os"], entry["platform"]["architecture"]) for entry in index["manifests"]]
assert sorted(platforms) == [("linux", "amd64"), ("linux", "arm64")], "index must contain exactly amd64 and arm64"
'
done
if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
  printf 'Published checked linux/amd64 and linux/arm64 images:\n\n- `%s-amap:%s`\n- `%s-amap-adapter:%s`\n\nNo deployment performed.\n' "$repository" "$version" "$repository" "$version" >> "$GITHUB_STEP_SUMMARY"
fi
