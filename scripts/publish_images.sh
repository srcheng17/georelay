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
context=$(python3 "$root/scripts/image_context.py" --json)
IFS=$'\037' read -r source_sha channel version pr_number source_ref publish_required <<< "$(python3 -c '
import json, sys
c = json.loads(sys.argv[1])
print("\x1f".join(str(c[key]).lower() if type(c[key]) is bool else c[key] for key in ("source_sha", "channel", "version", "pr_number", "source_ref", "publish_required")))
' "$context")"
[[ $publish_required == true ]] || {
  echo "This source did not request trusted image publication" >&2
  exit 1
}
tag=$(python3 -c 'import json; print(json.load(open("upstream.json"))["tag"])')
# Keep the updater's pin-only branch contract; other explicitly dispatched branches are beta.
if [[ $GITHUB_EVENT_NAME == workflow_dispatch && $source_ref == refs/heads/upstream/* ]]; then
  [[ $source_ref == "refs/heads/upstream/$tag" ]] || {
    echo "Automatic release branch does not match the pinned stable tag" >&2
    exit 1
  }
  git fetch --quiet --no-tags origin main:refs/remotes/origin/main 2>/dev/null || {
    echo "Publication source could not be verified" >&2
    exit 1
  }
  test "$(git show -s --format=%P HEAD)" = "$(git rev-parse origin/main)" || {
    echo "Automatic release branch must have current main as its sole parent" >&2
    exit 1
  }
  [[ $(git diff --name-only origin/main HEAD) == upstream.json ]] || {
    echo "Automatic release branch must differ from main only in upstream.json" >&2
    exit 1
  }
fi
verify_release_pin() {
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
}
verify_release_pin
for architecture in amd64 arm64; do
  test -s "$artifacts/checked-images-$architecture.tar"
done
registry="ghcr.io/$(printf '%s' "${GITHUB_REPOSITORY%%/*}" | tr '[:upper:]' '[:lower:]')"
app_package="$registry/georelay"
adapter_package="$registry/georelay-adapter"
export SOURCE_SHA="$source_sha" IMAGE_VERSION="$version" IMAGE_SOURCE="https://github.com/$GITHUB_REPOSITORY"
manifest_dir=$(mktemp -d)
trap 'docker logout ghcr.io >/dev/null 2>&1 || true; rm -rf "$manifest_dir"' EXIT
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GITHUB_ACTOR" --password-stdin >/dev/null
for architecture in amd64 arm64; do
  docker load -i "$artifacts/checked-images-$architecture.tar"
  # Both archives use :checked: push this architecture before the next load replaces it.
  for image in georelay georelay-adapter; do
    if [[ $image == georelay ]]; then
      package="$app_package"
    else
      package="$adapter_package"
    fi
    docker image inspect "$image:checked" | python3 -c '
import json, os, sys
image, = json.load(sys.stdin)
assert (image["Os"], image["Architecture"]) == ("linux", sys.argv[1]), "incorrect image architecture"
labels = image["Config"]["Labels"]
for key, value in {"source": os.environ["IMAGE_SOURCE"], "revision": os.environ["SOURCE_SHA"], "version": os.environ["IMAGE_VERSION"]}.items():
    assert labels["org.opencontainers.image." + key] == value, "incorrect OCI " + key
' "$architecture"
    docker tag "$image:checked" "$package:$version-$architecture"
    docker push "$package:$version-$architecture"
  done
done

index_digest() {
  python3 - "$1" <<'PY'
import json, re, sys
with open(sys.argv[1]) as metadata:
    digest = json.load(metadata)["containerimage.descriptor"]["digest"]
assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest), "invalid published index digest"
print(digest)
PY
}
verify_index() {
  python3 - "$1" "$2" <<'PY'
import hashlib, json, sys
from pathlib import Path
raw = Path(sys.argv[1]).read_bytes()
index = json.loads(raw)
platforms = [(entry["platform"]["os"], entry["platform"]["architecture"]) for entry in index["manifests"]]
assert sorted(platforms) == [("linux", "amd64"), ("linux", "arm64")], "index must contain exactly amd64 and arm64"
# Buildx versions may append a display newline to the raw registry bytes.
copies = [raw, raw[:-1]] if raw.endswith(b"\n") else [raw]
assert sys.argv[2] in {"sha256:" + hashlib.sha256(data).hexdigest() for data in copies}, "index differs from the checked version digest"
PY
}
for package in "$app_package" "$adapter_package"; do
  metadata="$manifest_dir/${package##*/}.metadata.json"
  raw_index="$manifest_dir/${package##*/}.json"
  docker buildx imagetools create --metadata-file "$metadata" --tag "$package:$version" "$package:$version-amd64" "$package:$version-arm64"
  docker buildx imagetools inspect --raw "$package:$version" > "$raw_index"
  verify_index "$raw_index" "$(index_digest "$metadata")"
done
if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
  printf 'Published checked linux/amd64 and linux/arm64 images:\n\n- `%s:%s`\n- `%s:%s`\n\nNo deployment performed.\n' "$app_package" "$version" "$adapter_package" "$version" >> "$GITHUB_STEP_SUMMARY"
fi

# Fixed versions survive source drift; only a current main/PR may update a floating tag.
if [[ $channel == beta && -z $pr_number ]]; then
  echo "Beta version images published; no linked PR alias requested."
  exit 0
fi
verify_release_pin
fetch_ref="$source_ref"
if [[ $channel == beta ]]; then
  fetch_ref="refs/pull/$pr_number/head"
fi
git fetch --quiet --no-tags origin "+$fetch_ref:refs/remotes/origin/publication-source" 2>/dev/null || {
  echo "Floating tag promotion failed: publication source could not be verified" >&2
  exit 1
}
current_sha=$(git rev-parse origin/publication-source)
skip_reason=
if [[ $current_sha != "$source_sha" ]]; then
  skip_reason="the publication source branch has changed"
elif [[ $channel == beta ]]; then
  pr_status=$(GH_TOKEN="$GHCR_TOKEN" python3 - "$root" "$GITHUB_REPOSITORY" "$pr_number" "$source_sha" "$source_ref" <<'PYCODE'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from update_release import github
import subprocess
try:
    pull = github("GET", "repos/" + sys.argv[2] + "/pulls/" + sys.argv[3])
    same_source = (
        pull["head"]["repo"]["full_name"].lower() == sys.argv[2].lower()
        and pull["base"]["repo"]["full_name"].lower() == sys.argv[2].lower()
        and pull["base"]["ref"] == "main"
        and "refs/heads/" + pull["head"]["ref"] == sys.argv[5]
        and pull["head"]["sha"] == sys.argv[4]
    )
    print("current" if same_source and pull["state"] == "open" and pull["draft"] is False else "changed")
except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, subprocess.SubprocessError):
    raise SystemExit("Beta alias promotion failed: current PR could not be verified")
PYCODE
)
  if [[ $pr_status != current ]]; then
    skip_reason="the linked PR is no longer a current open candidate"
  fi
fi
if [[ -n $skip_reason ]]; then
  echo "Version images published; floating tag promotion skipped because $skip_reason."
  if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
    printf '\nFloating tag promotion skipped: %s.\n' "$skip_reason" >> "$GITHUB_STEP_SUMMARY"
  fi
  exit 0
fi
floating_tag=latest
if [[ $channel == beta ]]; then
  floating_tag="beta-pr-$pr_number"
fi
for package in "$app_package" "$adapter_package"; do
  digest=$(index_digest "$manifest_dir/${package##*/}.metadata.json")
  # A single index source is copied unchanged; no rebuild or manifest recomposition.
  docker buildx imagetools create --prefer-index=false --tag "$package:$floating_tag" "$package@$digest"
  raw_index="$manifest_dir/${package##*/}.floating.json"
  docker buildx imagetools inspect --raw "$package:$floating_tag" > "$raw_index"
  verify_index "$raw_index" "$digest"
done
if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then
  printf '\nBoth %s tags verified against the checked version indexes.\n' "$floating_tag" >> "$GITHUB_STEP_SUMMARY"
fi
