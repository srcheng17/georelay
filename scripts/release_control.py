#!/usr/bin/env python3
"""Trusted-main observer for tested beta merges and failed GHCR publications."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from retain_images import INDEX_TYPES, IMAGE_TYPES, descriptor, registry_token, response_bytes
from update_release import command, sha


JOBS = {"checks", "build-amd64", "build-arm64", "verify", "publish"}
RUN_TITLE = re.compile(r"images/(pull_request|push|workflow_dispatch)/(0|[1-9]\d*)/([0-9a-f]{40})/(publish|check)/(-|[0-9a-f]{40})")
TAG = re.compile(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")


def github(method, path, payload=None):
    args = ["gh", "api", "--method", method, "-H", "X-GitHub-Api-Version: 2022-11-28", path]
    if payload is not None:
        args += ["--input", "-"]
    raw = command(*args, input=None if payload is None else json.dumps(payload))
    return json.loads(raw) if raw else None  # workflow dispatch may return HTTP 204.


def registry_document(owner, package, reference, kind="manifests"):
    return response_bytes("https://ghcr.io/v2/" + owner.lower() + "/" + package + "/" + kind + "/" + reference, {
        "Authorization": "Bearer " + registry_token(owner, package),
        "Accept": ", ".join(sorted(INDEX_TYPES | IMAGE_TYPES)) if kind == "manifests" else "application/octet-stream",
        "User-Agent": "georelay-release-control",
    })


def checked_document(raw, entry):
    if len(raw) != entry["size"] or "sha256:" + hashlib.sha256(raw).hexdigest() != descriptor(entry):
        raise ValueError("Registry content mismatch")
    return json.loads(raw)


def verify_beta(repository, revision, version, fetch=registry_document):
    owner = repository.split("/")[0]
    for package in ("georelay", "georelay-adapter"):
        index = json.loads(fetch(owner, package, version))
        if index.get("schemaVersion") != 2 or index.get("mediaType") not in INDEX_TYPES:
            raise ValueError("Invalid beta index")
        entries = index["manifests"]
        if not isinstance(entries, list) or len(entries) != 2:
            raise ValueError("Incomplete beta index")
        platforms = set()
        for entry in entries:
            platform = entry["platform"]
            architecture = platform.get("architecture")
            if platform.get("os") != "linux" or architecture not in {"amd64", "arm64"} or architecture in platforms:
                raise ValueError("Invalid beta platforms")
            platforms.add(architecture)
            manifest = checked_document(fetch(owner, package, descriptor(entry)), entry)
            if manifest.get("schemaVersion") != 2 or manifest.get("mediaType") not in IMAGE_TYPES:
                raise ValueError("Invalid beta image")
            config = manifest["config"]
            image = checked_document(fetch(owner, package, descriptor(config), "blobs"), config)
            labels = image["config"]["Labels"]
            if (image.get("os") != "linux" or image.get("architecture") != architecture
                    or labels.get("org.opencontainers.image.source") != "https://github.com/" + repository
                    or labels.get("org.opencontainers.image.revision") != revision
                    or labels.get("org.opencontainers.image.version") != version):
                raise ValueError("Beta OCI source mismatch")


def control(repository, run_id, attempt, api=github, fetch=registry_document, apply=False, sleep=time.sleep):
    """Read-only by default. Only a fully checked, current beta can mutate GitHub."""
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or type(run_id) is not int or run_id < 1
            or type(attempt) is not int or attempt < 1):
        raise ValueError("Invalid workflow source")
    root = "repos/" + repository
    report = {"status": "skipped", "reason": "untrusted_or_unrelated_run", "notify": False}
    notice = None
    stage = "source_verification"
    try:
        run = api("GET", root + "/actions/runs/" + str(run_id))
        workflow = api("GET", root + "/actions/workflows/ci.yml")
        title = RUN_TITLE.fullmatch(run.get("display_title", ""))
        if (run.get("id") != run_id or run.get("run_attempt") != attempt or run.get("status") != "completed"
                or run.get("workflow_id") != workflow.get("id") or workflow.get("path") != ".github/workflows/ci.yml"
                or workflow.get("name") != "Validate and build" or not title
                or run.get("repository", {}).get("full_name") != repository
                or run.get("head_repository", {}).get("full_name") != repository):
            return report
        event, pull_number, revision, mode, expected = title.groups()
        pull_number = int(pull_number)
        if run.get("event") != event or run.get("head_sha") != revision or mode != "publish":
            return report
        run_url = "https://github.com/" + repository + "/actions/runs/" + str(run_id)
        if run.get("html_url") != run_url:
            return report
        branch = run.get("head_branch")
        stable = branch == "main"
        if (event == "push" and not stable) or (event == "pull_request" and (stable or pull_number == 0)):
            return report
        if (not stable and expected != "-") or (stable and event != "workflow_dispatch" and (pull_number or expected != "-")):
            return report
        pull = None
        if pull_number:
            pull = api("GET", root + "/pulls/" + str(pull_number))
            if (pull.get("number") != pull_number or pull.get("head", {}).get("repo", {}).get("full_name") != repository
                    or pull.get("base", {}).get("repo", {}).get("full_name") != repository or pull["base"].get("ref") != "main"):
                return report
            if stable:
                if (event != "workflow_dispatch" or expected == "-" or pull.get("merged") is not True
                        or pull.get("merge_commit_sha") != expected):
                    return report
            elif pull["head"].get("ref") != branch:
                return report
        notice = {"repository": repository, "run_id": run_id, "attempt": attempt, "source_pr": pull_number,
                  "sha": revision, "run_url": run_url, "stage": "", "failed_jobs": [], "conclusion": run.get("conclusion")}
        if stable and expected != "-":
            notice["expected_main_sha"] = expected
        stage = "main_publication" if stable else "beta_validation"
        data = None
        try:
            data = api("GET", root + "/actions/runs/" + str(run_id) + "/jobs?filter=latest&per_page=100")
            for job in data["jobs"]:
                if job.get("name") == "checks" and job.get("run_id") == run_id and any(
                    step.get("name") == "Python checks for metadata-only changes" and step.get("status") == "completed"
                    and step.get("conclusion") in {"success", "failure", "cancelled", "timed_out"}
                    for step in job.get("steps", [])
                ):
                    return dict(report, reason="metadata_only_run")
        except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
            data = None  # Early image failures can have no jobs/artifacts; still notify.
        if run.get("conclusion") in {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}:
            if data is not None:
                notice["failed_jobs"] = sorted({job["name"] for job in data["jobs"] if job.get("name") in JOBS and job.get("conclusion") in {"failure", "cancelled", "timed_out"}})
            return dict(report, status="failed", reason=stage, notify=True, notification=dict(notice, stage=stage))
        if run.get("conclusion") != "success":
            return report
        if stable and expected != "-" and expected != revision:
            return dict(report, reason="stale_main_dispatch")
        if stable or pull_number == 0:
            return dict(report, reason="no_candidate_merge")
        if pull.get("state") != "open" or pull.get("draft") is not False or pull["head"].get("sha") != revision:
            return dict(report, reason="stale_or_inactive_candidate")

        stage = "beta_jobs"
        if data is None:
            raise ValueError("Candidate jobs could not be verified")
        jobs = data["jobs"]
        if data["total_count"] != len(jobs) or len(jobs) > 100:
            raise ValueError("Incomplete job inventory")
        selected = {}
        for job in jobs:
            name = job.get("name")
            if job.get("run_id") != run_id or job.get("status") != "completed" or job.get("conclusion") != "success":
                raise ValueError("Candidate job did not succeed")
            if name in JOBS:
                if name in selected:
                    raise ValueError("Duplicate candidate job")
                selected[name] = job
        if set(selected) != JOBS:
            raise ValueError("Required candidate jobs missing")
        verify = selected["verify"]
        check_url = verify.get("check_run_url", "")
        if not re.fullmatch(r"https://api\.github\.com/" + re.escape(root) + r"/check-runs/[1-9]\d*", check_url):
            raise ValueError("Invalid verify check URL")
        check = api("GET", check_url.removeprefix("https://api.github.com/"))
        if (check.get("app", {}).get("id") != 15368 or check.get("name") != "verify"
                or check.get("head_sha") != revision or check.get("status") != "completed" or check.get("conclusion") != "success"
                or check.get("details_url") != run_url + "/job/" + str(verify["id"])):
            raise ValueError("Verify provenance mismatch")

        stage = "beta_index"
        pin_file = api("GET", root + "/contents/upstream.json?ref=" + revision)
        if pin_file.get("type") != "file" or pin_file.get("encoding") != "base64":
            raise ValueError("Invalid candidate pin")
        pin = json.loads(base64.b64decode(pin_file["content"].replace("\n", ""), validate=True))
        if not TAG.fullmatch(pin["tag"]) or pin.get("repository") != "https://github.com/teslamate-org/teslamate.git":
            raise ValueError("Invalid upstream version")
        sha(pin["commit"])
        version = pin["tag"] + "-georelay-beta-" + revision
        verify_beta(repository, revision, version, fetch)

        def current_candidate():
            current = api("GET", root + "/pulls/" + str(pull_number))
            if (current.get("state") != "open" or current.get("draft") is not False or current["head"].get("sha") != revision
                    or current["head"]["repo"]["full_name"] != repository or current["head"].get("ref") != branch
                    or current["base"]["repo"]["full_name"] != repository or current["base"].get("ref") != "main"):
                return None
            base = api("GET", root + "/git/ref/heads/main")["object"]
            if base.get("type") != "commit":
                raise ValueError("Invalid main ref")
            base_sha = sha(base["sha"])
            comparison = api("GET", root + "/compare/" + base_sha + "..." + revision)
            if comparison.get("status") not in {"ahead", "identical"} or comparison.get("merge_base_commit", {}).get("sha") != base_sha:
                return None
            return current

        stage = "merge_readiness"
        for poll in range(3):
            pull = current_candidate()
            if pull is None:
                return dict(report, reason="stale_candidate_base_or_head")
            if pull.get("mergeable") is not None and pull.get("mergeable_state") != "unknown":
                break
            if poll < 2:
                sleep(2)
        if pull.get("mergeable") is not True or pull.get("mergeable_state") not in {"clean", "has_hooks"}:
            return dict(report, reason="merge_not_ready")
        if apply:
            # Re-read head/base immediately before the expected-head merge.
            pull = current_candidate()
            if pull is None or pull.get("mergeable") is not True or pull.get("mergeable_state") not in {"clean", "has_hooks"}:
                return dict(report, reason="candidate_changed_before_merge")
        stage = "branch_protection"
        # GITHUB_TOKEN can read this summary, but cannot inspect strict settings.
        # The ordinary merge endpoint enforces the repository's existing strict
        # policy atomically; this controller never requests an admin bypass.
        branch_summary = api("GET", root + "/branches/main")
        protection = branch_summary["protection"]
        required = protection["required_status_checks"]
        checks = required["checks"]
        if (branch_summary.get("name") != "main" or branch_summary.get("protected") is not True or protection.get("enabled") is not True
                or required.get("enforcement_level") != "everyone" or not isinstance(checks, list)
                or [item.get("app_id") for item in checks if item.get("context") == "verify"] != [15368]):
            raise ValueError("Required verify protection is not established")
        if not apply:
            return dict(report, status="dry_run", reason="candidate_ready", version=version)
        # Strict server protection is the atomic base-freshness gate; no bypass.
        stage = "merge"
        response = None
        try:
            response = api("PUT", root + "/pulls/" + str(pull_number) + "/merge", {"sha": revision, "merge_method": "merge"})
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError):
            pass  # An accepted merge can lose its response. Read back; never re-merge.
        merged = api("GET", root + "/pulls/" + str(pull_number))
        merge_sha = sha(merged.get("merge_commit_sha")) if merged.get("merged") is True else None
        if (not merge_sha or merged["head"].get("sha") != revision
                or (response is not None and (response.get("merged") is not True or response.get("sha") != merge_sha))):
            raise ValueError("Merge was not confirmed")
        report["merged_sha"] = merge_sha
        stage = "main_dispatch"
        api("POST", root + "/actions/workflows/ci.yml/dispatches", {
            "ref": "main", "inputs": {"publish": "true", "expected_main_sha": merge_sha, "source_pr": str(pull_number)},
        })
        return dict(report, status="merged_dispatched", reason="main_publication_requested", version=version)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        if notice is None:
            return dict(report, status="failed", reason="source_verification_failed")
        return dict(report, status="failed", reason=stage, notify=True, notification=dict(notice, stage=stage))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        repository = os.environ["GITHUB_REPOSITORY"]
        if (os.environ.get("GITHUB_EVENT_NAME") != "workflow_run" or os.environ.get("GITHUB_REF") != "refs/heads/main"
                or event["repository"]["full_name"] != repository):
            raise ValueError("Controller must run from trusted main")
        run = event["workflow_run"]
        report = control(repository, run["id"], run["run_attempt"], apply=args.apply)
    except (OSError, ValueError, KeyError, TypeError):
        report = {"status": "failed", "reason": "invalid_controller_context", "notify": False}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write("notify=" + str(report["notify"]).lower() + "\n")
    print(json.dumps(report, separators=(",", ":")))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
