#!/usr/bin/env python3
"""Fetch an exact stable release and fail closed before applying local patches."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

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


def git(directory, *args, env=None):
    return subprocess.run(
        ["git", "-C", str(directory), *args], check=True, text=True, stdout=subprocess.PIPE, env=env
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
    # Later patches may depend on earlier ones. Validate the whole series in an
    # isolated index first so a conflict in patch N cannot leave patches 1..N-1
    # applied to the source. This never modifies the real index or working tree.
    with tempfile.TemporaryDirectory(prefix="georelay-patch-check-") as temporary:
        environment = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
        git(destination, "read-tree", "HEAD", env=environment)
        for patch in patch_args:
            git(destination, "apply", "--cached", "--check", patch, env=environment)
            git(destination, "apply", "--cached", patch, env=environment)
    for patch in patch_args:
        git(destination, "apply", "--check", patch)
        git(destination, "apply", patch)
    git(destination, "diff", "--check")
    print("Prepared " + pin["tag"] + " at " + actual)


def verify_patched(directory, patches_dir=ROOT / "patches", pin_path=ROOT / "upstream.json"):
    """Verify the exact ordered patch result using a disposable index only."""
    if git(directory, "rev-parse", "HEAD") != load_pin(pin_path)["commit"]:
        raise ValueError("incorrect upstream commit")
    patches = sorted(Path(patches_dir).glob("*.patch"))
    if not patches:
        raise ValueError("no upstream patch found")
    with tempfile.TemporaryDirectory(prefix="georelay-patch-check-") as temporary:
        environment = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
        git(directory, "read-tree", "HEAD", env=environment)
        git(directory, "add", "--all", env=environment)
        for patch in reversed(patches):
            args = ["apply", "--cached", "--reverse", str(patch.resolve())]
            git(directory, *args[:2], "--check", *args[2:], env=environment)
            git(directory, *args, env=environment)
        if git(directory, "write-tree", env=environment) != git(directory, "rev-parse", "HEAD^{tree}"):
            raise ValueError("prepared source differs from the expected patch series")


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
