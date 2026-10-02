#!/usr/bin/env python3
"""Skip image builds only for an established metadata-only Git diff."""

import json
import os
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
METADATA_FILES = {
    "AGENTS.md", "README.md", "README.zh-CN.md", "MODIFICATIONS.md",
    "TRADEMARK.md", "paseo.json",
}
METADATA_DIRECTORIES = ("docs/", ".trellis/", ".agents/", ".codex/")


def images_required(event_name, event, head, root=ROOT):
    if event_name not in ("pull_request", "push"):
        return True
    try:
        base = event["pull_request"]["base"]["sha"] if event_name == "pull_request" else event["before"]
        if any(not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha)
               or sha == "0" * 40 for sha in (base, head)):
            return True
        result = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "-z", "--no-renames", base, head, "--"],
            capture_output=True, timeout=20, check=False,
        )
        if result.returncode or len(result.stdout) > 1_048_576:
            return True
        paths = result.stdout.decode("utf-8").split("\0")
        if paths[-1] != "":
            return True
        # An empty diff is ambiguous (for example a retry with the wrong base).
        return not paths[:-1] or any(
            path not in METADATA_FILES and not path.startswith(METADATA_DIRECTORIES)
            for path in paths[:-1]
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return True


def main():
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        event = {}
    required = images_required(os.environ.get("GITHUB_EVENT_NAME"), event, os.environ.get("GITHUB_SHA"))
    decision = "image_required=" + str(required).lower()
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(decision + "\n")
    print(decision)


if __name__ == "__main__":
    main()
