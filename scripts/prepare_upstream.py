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
LEGAL_FILES = ("LICENSE", "NOTICE", "TRADEMARK.md")
BRANDED_ASSETS = (
    "images/logo.svg", "images/logo_icon.svg", "favicon.ico",
    "favicon-16x16.png", "favicon-32x32.png", "apple-touch-icon.png",
    "android-chrome-192x192.png", "android-chrome-512x512.png",
    "mstile-150x150.png", "safari-pinned-tab.svg", "browserconfig.xml", "site.webmanifest",
)
DISCLAIMER = (
    "This project is an unofficial community tool and is not affiliated with, endorsed by, "
    "or supported by the official TeslaMate project."
)


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


def check_legal_files(directory):
    for name in LEGAL_FILES:
        try:
            unchanged = (Path(directory) / name).read_bytes() == (ROOT / name).read_bytes()
        except OSError:
            unchanged = False
        if not unchanged:
            raise ValueError(
                name + " is missing or differs from the reviewed legal text; manual review required"
            )


def check_branding_assets(directory):
    static = Path(directory) / "elixir/priv/static"
    actual = {p.relative_to(static).as_posix() for p in static.rglob("*") if p.is_file()}
    if actual != set(BRANDED_ASSETS) | {"robots.txt"}:
        raise ValueError("upstream static assets changed; manual branding review required")


def stage_branding(directory):
    directory = Path(directory)
    layout = (directory / "elixir/lib/teslamate_web/templates/layout/root.html.heex").read_text()
    if not all(value in layout for value in (
        'suffix=" · GeoRelay"', '>GeoRelay</strong>',
        "https://github.com/srcheng17/georelay", DISCLAIMER,
    )):
        raise ValueError("independent application branding is missing; manual review required")
    for relative in ("elixir/lib/teslamate_web", "elixir/priv/gettext"):
        for path in (directory / relative).rglob("*"):
            if path.suffix not in (".heex", ".eex", ".po", ".pot"):
                continue
            text = path.read_text()
            if path.suffix in (".po", ".pot"):
                text = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
            for credit in (DISCLAIMER, "© the TeslaMate contributors", "Upstream TeslaMate: "):
                text = text.replace(credit, "")
            text = text.replace(":teslamate,", "")
            if re.search(r"(?<![\w/.-])TeslaMate(?![\w.-])", text, re.IGNORECASE):
                raise ValueError("unreviewed application branding in " + str(path.relative_to(directory)))
    static = directory / "elixir/priv/static"
    for name in BRANDED_ASSETS:
        (static / name).unlink()
    (static / "favicon.svg").write_bytes((ROOT / "branding/favicon.svg").read_bytes())


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
    check_legal_files(destination)
    check_branding_assets(destination)
    patch_args = [str(p.resolve()) for p in patches]
    git(destination, "apply", "--check", *patch_args)
    git(destination, "apply", *patch_args)
    stage_branding(destination)
    (destination / "MODIFICATIONS.md").write_bytes((ROOT / "MODIFICATIONS.md").read_bytes())
    with (destination / "Dockerfile").open("a") as dockerfile:
        dockerfile.write(
            "\nCOPY --chmod=444 MODIFICATIONS.md TRADEMARK.md /usr/share/doc/teslamate/\n"
        )
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
