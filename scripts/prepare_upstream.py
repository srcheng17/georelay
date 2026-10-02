#!/usr/bin/env python3
"""Fetch an exact stable release and fail closed before applying local patches."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/teslamate-org/teslamate.git"


def load_pin(path=ROOT / "upstream.json"):
    pin = json.loads(Path(path).read_text())
    if (
        not isinstance(pin, dict)
        or pin.get("repository") != REPOSITORY
        or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", str(pin.get("tag", "")))
        or not isinstance(pin.get("commit"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", pin["commit"])
    ):
        raise ValueError("upstream.json must pin the official repository, stable tag and full commit")
    return pin


def git(directory, *args):
    return subprocess.run(
        ["git", "-C", str(directory), *args], check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def prepare(destination, pin_path=ROOT / "upstream.json", patches_dir=ROOT / "patches"):
    pin = load_pin(pin_path)
    patches = sorted(Path(patches_dir).glob("*.patch"))
    if not patches:
        raise ValueError("no upstream patch found")
    destination = Path(destination)
    if destination.is_symlink() or (
        destination.exists() and (not destination.is_dir() or any(destination.iterdir()))
    ):
        raise ValueError("destination must be absent or an empty directory")
    destination.mkdir(parents=True, exist_ok=True)
    git(destination, "init", "--quiet")
    git(destination, "remote", "add", "origin", pin["repository"])
    git(destination, "fetch", "--quiet", "--depth", "1", "origin", "refs/tags/" + pin["tag"])
    actual = git(destination, "rev-parse", "FETCH_HEAD^{commit}")
    if actual != pin["commit"]:
        raise ValueError("release tag does not resolve to the pinned commit; refusing to patch")
    git(destination, "checkout", "--quiet", "--detach", actual)
    patch_args = [str(p.resolve()) for p in patches]
    git(destination, "apply", "--check", *patch_args)
    git(destination, "apply", *patch_args)
    git(destination, "diff", "--check")
    print("Prepared " + pin["tag"] + " at " + actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        prepare(args.destination)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("Upstream preparation failed: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
