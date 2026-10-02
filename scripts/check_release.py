#!/usr/bin/env python3
"""Report a pin proposal for review; never modify the pin, patches, or GitHub."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

from prepare_upstream import ROOT, load_pin


API = "https://api.github.com/repos/teslamate-org/teslamate"


def github_json(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "teslamate-amap-release-check",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urlopen(Request(API + path, headers=headers), timeout=20) as response:
        data = response.read(1_048_577)
    if len(data) > 1_048_576:
        raise ValueError("GitHub response exceeded size limit")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("GitHub response is not an object")
    return result


def version(tag):
    if not isinstance(tag, str) or not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("Expected a stable vMAJOR.MINOR.PATCH release")
    return tuple(map(int, tag[1:].split(".")))


def check_release(pin, fetch=github_json):
    release = fetch("/releases/latest")
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Latest release is not a published stable release")
    tag = release.get("tag_name")
    if version(tag) < version(pin["tag"]):
        raise ValueError("Latest release is older than the reviewed pin")

    obj = fetch("/git/ref/tags/" + tag).get("object", {})
    seen = set()
    for _ in range(5):
        sha, kind = obj.get("sha"), obj.get("type")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid Git object ID")
        if kind == "commit":
            break
        if kind != "tag" or sha in seen:
            raise ValueError("Release tag does not resolve to a commit")
        seen.add(sha)
        obj = fetch("/git/tags/" + sha).get("object", {})
    else:
        raise ValueError("Release tag exceeded dereference limit")

    if tag == pin["tag"] and sha != pin["commit"]:
        raise ValueError("Pinned release tag moved; manual investigation required")
    return {
        "status": "current" if tag == pin["tag"] else "update_available",
        "current": pin,
        "proposed": {"repository": pin["repository"], "tag": tag, "commit": sha},
        "release_url": "https://github.com/teslamate-org/teslamate/releases/tag/" + tag,
        "next_step": "Review source and patches, then edit upstream.json and pass all CI gates. No automatic update or deployment.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", type=Path, default=ROOT / "upstream.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.output and args.output.resolve() == args.pin.resolve():
            raise ValueError("The reviewed pin cannot be used as report output")
        report = check_release(load_pin(args.pin))
        text = json.dumps(report, indent=2) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                summary.write("## Upstream release check\n\n```json\n" + text + "```\n")
        print(text, end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # No remote bodies, authorization headers, or exception URLs in logs.
        print("Release check failed; no update proposed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
