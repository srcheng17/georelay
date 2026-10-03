#!/usr/bin/env python3
"""Use one tested commit and channel for CI labels and checked-image publication."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from check_release import version as stable_version
from prepare_upstream import load_pin


def commit(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value) or value == "0" * 40:
        raise ValueError("Invalid source commit")
    return value


def pull_number(value):
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]*", str(value)):
        raise ValueError("Invalid source PR number")
    return str(value)


def requested(value):
    if type(value) is bool:
        return value
    if value in ("true", "false"):
        return value == "true"
    raise ValueError("Publish input must be true or false")


def branch_ref(value):
    if (
        not isinstance(value, str) or not value.startswith("refs/heads/")
        or not value.removeprefix("refs/heads/")
        or re.search(r"[\x00-\x20\x7f~^:?*\[\\]", value)
        or any(part.startswith(".") or part.endswith((".lock", ".")) or not part for part in value.split("/"))
        or ".." in value or "@{" in value
    ):
        raise ValueError("Publication source must be a branch")
    return value


def image_context(event_name, event, sha, ref, repository, pin):
    if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid source repository")
    source_sha = commit(sha)
    channel = "stable" if ref == "refs/heads/main" else "beta"
    pr_number = expected_main_sha = ""
    publish = False
    source_ref = ref
    if event_name == "pull_request":
        pull = event["pull_request"]
        source_sha = commit(pull["head"]["sha"])
        source_ref = branch_ref("refs/heads/" + pull["head"]["ref"])
        pr_number = pull_number(event["number"])
        channel = "beta"
        publish = (
            pull["head"]["repo"]["full_name"].lower() == repository.lower()
            and pull["base"]["repo"]["full_name"].lower() == repository.lower()
            and pull["base"]["ref"] == "main"
        )
    elif event_name == "push":
        source_ref = branch_ref(ref)
        publish = ref == "refs/heads/main"
    elif event_name == "workflow_dispatch":
        source_ref = branch_ref(ref)
        inputs = event.get("inputs", {})
        publish = requested(inputs.get("publish", "false"))
        if inputs.get("source_pr", "") != "":
            pr_number = pull_number(inputs["source_pr"])
        expected_main_sha = inputs.get("expected_main_sha", "")
        if expected_main_sha != "":
            if channel != "stable" or commit(expected_main_sha) != source_sha:
                raise ValueError("Main dispatch no longer matches the expected commit")
    else:
        raise ValueError("Unsupported image source event")
    stable_version(pin["tag"])
    image_version = pin["tag"] + "-georelay-" + ("beta-" if channel == "beta" else "") + source_sha
    if len(image_version + "-amd64") > 128:
        raise ValueError("Image version exceeds registry tag limit")
    return {
        "source_sha": source_sha, "channel": channel, "version": image_version,
        "pr_number": pr_number, "publish_required": publish,
        "source_ref": source_ref, "expected_main_sha": expected_main_sha,
    }


def publication_receipt(context, pin, digests, floating, run_id, attempt):
    """Small data-only receipt. Registry and Actions must independently prove it."""
    source = commit(context["source_sha"])
    channel = context["channel"]
    version = pin["tag"] + "-georelay-" + ("beta-" if channel == "beta" else "") + source
    if channel not in {"stable", "beta"} or context["version"] != version:
        raise ValueError("Invalid receipt version")
    stable_version(pin["tag"])
    commit(pin["commit"])
    if (set(digests) != {"georelay", "georelay-adapter"}
            or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", value) for value in digests.values())
            or type(run_id) is not int or run_id < 1 or type(attempt) is not int or attempt < 1):
        raise ValueError("Invalid receipt identity")
    if (set(floating) != {"tag", "status", "reason"}
            or floating["status"] not in {"promoted", "skipped", "failed"}
            or floating["reason"] not in {"verified", "no_pr", "stale_source", "stale_pr", "promotion_incomplete"}
            or not re.fullmatch(r"(?:latest|beta-pr-[1-9][0-9]*)?", floating["tag"])
            or (channel == "beta" and floating["tag"] == "latest")
            or (channel == "stable" and floating["tag"] != "latest")
            or (floating["status"] == "promoted" and (floating["reason"] != "verified" or not floating["tag"]))
            or (floating["status"] == "failed" and floating["reason"] != "promotion_incomplete")
            or (floating["status"] == "skipped" and floating["reason"] not in {"no_pr", "stale_source", "stale_pr"})):
        raise ValueError("Invalid receipt outcome")
    return {"schema": 1, "run_id": run_id, "attempt": attempt, "source_sha": source,
            "channel": channel, "version": version, "upstream": {"tag": pin["tag"], "commit": pin["commit"]},
            "digests": digests, "fixed_verified": True, "floating": floating}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        context = image_context(
            os.environ["GITHUB_EVENT_NAME"], event, os.environ["GITHUB_SHA"],
            os.environ["GITHUB_REF"], os.environ["GITHUB_REPOSITORY"], load_pin(Path("upstream.json")),
        )
        head = subprocess.run(["git", "rev-parse", "HEAD"], text=True, capture_output=True, timeout=20, check=True).stdout.strip()
        if head != context["source_sha"]:
            raise ValueError("Checked-out source does not match the tested commit")
        if args.json:
            print(json.dumps(context))
        else:
            text = "\n".join(key + "=" + (str(value).lower() if type(value) is bool else value) for key, value in context.items()) + "\n"
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write(text)
            print(text, end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        print("Image source validation failed; no publication context produced.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
