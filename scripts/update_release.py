#!/usr/bin/env python3
"""Create a pin-only update PR and dispatch checked beta publication."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from check_release import check_release
from prepare_upstream import ROOT, load_pin
from image_context import pull_number


class UpdateError(ValueError):
    """A fixed local explanation safe to report without remote response data."""


def command(*args, input=None):
    result = subprocess.run(
        args, input=input, text=True, capture_output=True, timeout=60, check=False
    )
    if result.returncode:
        # Never print command output: a remote response can contain private data.
        raise RuntimeError("GitHub/git command failed")
    if len(result.stdout) > 1_048_576:
        raise UpdateError("Command response exceeded size limit")
    return result.stdout.strip()


def github(method, path, payload=None):
    # Share bounded native-token API semantics, notably explicit 404 vs permission failure.
    from record_release import github as request
    return request(method, path, payload)


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise UpdateError("Invalid Git object ID")
    return value


def update_release(repository, pin, source, api=github, run=command, detect=check_release, record_verify=None, repair_verify=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise UpdateError("Invalid GitHub repository")
    sha(source)
    report = detect(pin)
    if report["status"] == "current":
        return report
    proposed = report["proposed"]
    branch = "upstream/" + proposed["tag"]
    root = "repos/" + repository

    def ref(name):
        obj = api("GET", root + "/git/ref/heads/" + name)["object"]
        if obj["type"] != "commit":
            raise UpdateError("Branch does not reference a commit")
        return sha(obj["sha"])

    def remote_pin(commit):
        content = api("GET", root + "/contents/upstream.json?ref=" + commit)
        if content["type"] != "file" or content["encoding"] != "base64":
            raise UpdateError("Invalid pin file response")
        return json.loads(base64.b64decode(content["content"].replace("\n", ""), validate=True))

    if ref("main") != source or remote_pin(source) != pin:
        raise UpdateError("Main changed since checkout; retry from current main")
    matches = api("GET", root + "/git/matching-refs/heads/" + branch)
    if not isinstance(matches, list):
        raise UpdateError("Invalid branch response")
    existing = [item for item in matches if item["ref"] == "refs/heads/" + branch]
    if len(existing) > 1:
        raise UpdateError("Ambiguous update branch")
    if not existing:
        base = api("GET", root + "/git/commits/" + source)
        blob = api("POST", root + "/git/blobs", {
            "content": json.dumps(proposed, indent=2) + "\n", "encoding": "utf-8",
        })
        tree = api("POST", root + "/git/trees", {
            "base_tree": sha(base["tree"]["sha"]),
            "tree": [{"path": "upstream.json", "mode": "100644", "type": "blob", "sha": sha(blob["sha"])}],
        })
        commit = api("POST", root + "/git/commits", {
            "message": "chore: update official TeslaMate to " + proposed["tag"],
            "tree": sha(tree["sha"]), "parents": [source],
        })
        api("POST", root + "/git/refs", {"ref": "refs/heads/" + branch, "sha": sha(commit["sha"])})

    revision = ref(branch)
    if remote_pin(revision) != proposed:
        raise UpdateError("Existing update pin differs from the official release; manual review required")
    commit = api("GET", root + "/git/commits/" + revision)
    # ponytail: main drift requires review; design a safe candidate refresh if this becomes routine.
    if [parent["sha"] for parent in commit["parents"]] != [source]:
        raise UpdateError("Update branch no longer comes directly from current main; manual review required")
    diff = api("GET", root + "/compare/" + source + "..." + revision)
    if (
        diff["status"] != "ahead" or diff["total_commits"] != 1
        or [(item["filename"], item["status"]) for item in diff["files"]] != [("upstream.json", "modified")]
    ):
        raise UpdateError("Update branch must change only upstream.json")

    pulls = api("GET", root + "/pulls?state=all&head=" + repository.split("/")[0] + ":" + branch + "&base=main&per_page=100")
    if not isinstance(pulls, list) or len(pulls) > 1:
        raise UpdateError("Ambiguous update pull request")
    if pulls:
        pull = pulls[0]
    else:
        pull = api("POST", root + "/pulls", {
            "title": "chore: update TeslaMate to " + proposed["tag"],
            "head": branch, "base": "main",
            "body": (
                "Official stable release: " + report["release_url"] + "\n\n"
                "Pinned official commit: `" + proposed["commit"] + "`.\n"
                "Source main commit: `" + source + "`. This PR changes only `upstream.json`.\n\n"
                "CI is explicitly dispatched to test the patches and both architectures, then publish checked beta images. "
                "The trusted controller may merge this PR only after beta succeeds and its head and main baseline remain current. "
                "After merge, main is explicitly dispatched to test and publish formal images and latest. "
                "Failures stop the affected stage and trigger Bark when configured. No running services are deployed."
            ),
        })
    if (
        pull["state"] != "open" or pull["head"]["sha"] != revision
        or pull["head"]["ref"] != branch or pull["base"]["ref"] != "main"
        or not re.fullmatch(r"https://github\.com/" + re.escape(repository) + r"/pull/[1-9]\d*", pull["html_url"])
    ):
        raise UpdateError("Update PR is closed or changed; manual review required")

    number = pull_number(pull["number"])
    if pull["html_url"] != "https://github.com/" + repository + "/pull/" + number:
        raise UpdateError("Update PR number does not match its URL")

    # Recheck mutable refs and the official proposal before dispatching.
    if ref("main") != source or ref(branch) != revision or detect(pin)["proposed"] != proposed:
        raise UpdateError("Source or release changed during update; refusing to dispatch")
    runs = json.loads(run(
        "gh", "run", "list", "--repo", repository, "--workflow", "ci.yml",
        "--branch", branch, "--event", "workflow_dispatch", "--commit", revision,
        "--limit", "100", "--json", "databaseId,headSha,status,conclusion",
    ))
    if not isinstance(runs, list) or len(runs) >= 100:
        raise UpdateError("Cannot establish publication run history")
    started = False
    repair_status = None
    # Check all pending runs first so old failures cannot schedule parallel repairs.
    for item in runs:
        if item["headSha"] != revision:
            raise UpdateError("Run history returned a different source commit")
        if item["status"] in ("queued", "requested", "waiting", "pending", "in_progress"):
            pending = api("GET", root + "/actions/runs/" + str(item["databaseId"]))
            expected_title = "images/workflow_dispatch/" + number + "/" + revision + "/publish/-"
            if pending.get("display_title") == expected_title:
                started = True
    for item in ([] if started else runs):
        if item["headSha"] != revision:
            raise UpdateError("Run history returned a different source commit")
        if item["status"] in ("queued", "requested", "waiting", "pending", "in_progress"):
            continue  # An active check-only dispatch does not suppress publication.
        elif item["status"] == "completed":
            original_id = int(item["databaseId"])
            original = api("GET", root + "/actions/runs/" + str(original_id))
            attempt = original["run_attempt"]
            if type(attempt) is not int or attempt < 1:
                raise UpdateError("Invalid original publication attempt")
            jobs = api("GET", root + "/actions/runs/" + str(original_id) + "/attempts/" + str(attempt) + "/jobs?per_page=100")
            if jobs["total_count"] != len(jobs["jobs"]) or len(jobs["jobs"]) > 100:
                raise UpdateError("Cannot establish publication job history")
            selected = {}
            for job in jobs["jobs"]:
                if job["name"] in selected:
                    raise UpdateError("Duplicate publication job")
                selected[job["name"]] = job
            publisher = selected.get("publish", {})
            if publisher.get("conclusion") not in {"success", "failure"}:
                continue  # A publish=false or early failed build is not a publication.
            if any(selected.get(name, {}).get("conclusion") != "success"
                   for name in ("checks", "build-amd64", "build-arm64", "verify")):
                continue
            version = proposed["tag"] + "-georelay-beta-" + revision
            from record_release import APIError, verify_record, repair_proof
            if (item["conclusion"] == "success" and selected.get("release-record", {}).get("conclusion") == "success"):
                try:
                    (record_verify or verify_record)(repository, original_id, attempt, revision, version, api=api)
                except APIError as error:
                    if error.status != 404:
                        raise  # Unknown/permission failures are never an absent Release.
                else:
                    started = True
                    break
            # Once fixed publication may exist, repair its record rather than rebuild.
            # Receipt/registry evidence is validated by trusted main in the repair job.
            history = api("GET", root + "/actions/workflows/release-only.yml/runs?event=workflow_dispatch&branch=main&per_page=100")
            if history["total_count"] != len(history["workflow_runs"]) or len(history["workflow_runs"]) >= 100:
                raise UpdateError("Cannot establish release repair history")
            title = "release-record/" + "/".join(map(str, (original_id, attempt, revision, version)))
            matching = [repair for repair in history["workflow_runs"] if repair.get("display_title") == title]
            if any(repair.get("status") in {"queued", "requested", "waiting", "pending", "in_progress"} for repair in matching):
                started, repair_status = True, "repair_pending"
                break
            successes = [repair for repair in matching if repair.get("status") == "completed" and repair.get("conclusion") == "success"]
            if successes:
                repair_id = max(repair["id"] for repair in successes)
                (repair_verify or repair_proof)(repository, original_id, attempt, revision, version, repair_id, api=api)
                # Explicit re-evaluation also covers bot repairs with no workflow_run event.
                api("POST", root + "/actions/workflows/beta-control.yml/dispatches", {
                    "ref": "main", "inputs": {"original_run_id": str(original_id), "original_attempt": str(attempt), "repair_run_id": str(repair_id)},
                })
                started, repair_status = True, "repaired_reevaluation_requested"
            else:
                api("POST", root + "/actions/workflows/release-only.yml/dispatches", {
                    "ref": "main", "inputs": {"original_run_id": str(original_id), "original_attempt": str(attempt),
                                                 "original_source": revision, "original_version": version},
                })
                started, repair_status = True, "repair_dispatched"
            break
        else:
            raise UpdateError("Unknown workflow run status")
    if not started:
        run("gh", "workflow", "run", "ci.yml", "--repo", repository, "--ref", branch,
            "-f", "publish=true", "-f", "source_pr=" + number)
    report.update({
        "status": repair_status or ("already_started" if started else "dispatched"),
        "branch": branch, "source_main": source, "source_commit": revision, "pull_request": pull["html_url"],
        "next_step": "CI tests both architectures before publishing beta. The trusted controller may merge a still-current PR, then dispatch main for checked formal images/latest. No running services are deployed.",
    })
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if os.environ.get("GITHUB_REF") != "refs/heads/main":
            raise UpdateError("Updater must run from main")
        if args.output and args.output.resolve() == (ROOT / "upstream.json").resolve():
            raise UpdateError("Report cannot replace the pin")
        report = update_release(
            os.environ["GITHUB_REPOSITORY"], load_pin(), command("git", "-C", str(ROOT), "rev-parse", "HEAD")
        )
        text = json.dumps(report, indent=2) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                summary.write("## Official release update\n\n```json\n" + text + "```\n")
        print(text, end="")
        return 0
    except UpdateError as exc:
        print("Release update stopped: " + str(exc) + ". No further publication dispatched.", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, subprocess.SubprocessError):
        print("Release update failed; no further publication was dispatched. Review source, pin, PR and run history before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
