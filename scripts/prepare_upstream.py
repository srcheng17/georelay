#!/usr/bin/env python3
"""Fetch an exact stable release and fail closed before applying local patches."""

import argparse
import ast
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
VISUAL_EXTENSIONS = {
    ".svg", ".svgz", ".ico", ".png", ".apng", ".jpg", ".jpeg", ".gif",
    ".webp", ".avif", ".bmp", ".tif", ".tiff", ".heic", ".heif",
}
# ponytail: four reviewed UI keys; extend this set when public brand copy changes.
BRAND_MESSAGES = {
    "To ensure that your <strong>Tesla API tokens are stored securely</strong>, an encryption key must be provided to TeslaMate via the <code>ENCRYPTION_KEY</code> environment variable. Otherwise, a <strong>login will be required after every restart</strong>.",
    "You are using the API key (%{token}) provided by %{url}. It will allow your TeslaMate to access the official Tesla Fleet API and Tesla Telemetry streaming.",
    "Discard this interrupted import? Its completed-file checkpoints and rejection report will no longer be used. Imported TeslaMate data is kept.",
    "No vehicle was found when TeslaMate started. Once your vehicle shows up in the Tesla app, reload the vehicle list.",
}
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
    unknown = {
        p.relative_to(static).as_posix() for p in static.rglob("*")
        if p.is_file() and p.suffix.lower() in VISUAL_EXTENSIONS
    } - set(BRANDED_ASSETS)
    if unknown:
        raise ValueError("upstream visual assets changed; manual branding review required")


def brand_catalog(path):
    text = path.read_bytes().decode("utf-8")
    fields = list(re.finditer(
        r'^[ \t]*(msgid(?:_plural)?|msgstr(?:\[\d+\])?)[ \t]+'
        r'("(?:[^"\\\r\n]|\\.)*"(?:\r?\n[ \t]*"(?:[^"\\\r\n]|\\.)*")*)',
        text, re.MULTILINE,
    ))
    messages = BRAND_MESSAGES | {m.replace("TeslaMate", "GeoRelay") for m in BRAND_MESSAGES}
    changes = []
    for index, field in enumerate(fields):
        if field[1] != "msgid":
            continue
        message = "".join(ast.literal_eval(line.strip()) for line in field[2].split("\n"))
        if message not in messages:
            continue
        translations = []
        for following in fields[index + 1:]:
            if following[1] == "msgid":
                break
            translations.append(following)
        if [f[1] for f in translations] != ["msgstr"]:
            raise ValueError("known branding message is not singular; manual branding review required")
        for selected in (field, translations[0]):
            value = "".join(ast.literal_eval(line.strip()) for line in selected[2].split("\n"))
            renamed = value.replace("TeslaMate", "GeoRelay")
            if renamed != value:
                changes.append((
                    selected.start(), selected.end(),
                    selected[1] + " " + json.dumps(renamed, ensure_ascii=False),
                ))
    for start, end, replacement in reversed(changes):
        text = text[:start] + replacement + text[end:]
    if changes:
        path.write_bytes(text.encode("utf-8"))


def stage_branding(directory):
    directory = Path(directory)
    for path in (directory / "elixir/priv/gettext").rglob("*"):
        if path.suffix in (".po", ".pot"):
            brand_catalog(path)
    static = directory / "elixir/priv/static"
    static.mkdir(parents=True, exist_ok=True)
    for name in BRANDED_ASSETS:
        (static / name).unlink(missing_ok=True)
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
