"""Offline GitHub fixtures verify update/retry gates without touching a remote."""

import base64
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_release
import update_release as updater


MAIN = "a" * 40
BRANCH = "b" * 40
OFFICIAL = "c" * 40
REPOSITORY = "fixture/teslamate"
PIN = {"repository": "https://github.com/teslamate-org/teslamate.git", "tag": "v4.3.0", "commit": MAIN}
PROPOSED = dict(PIN, tag="v4.3.1", commit=OFFICIAL)


class GitHubFixture:
    def __init__(self):
        self.branch = None
        self.branch_pin = copy.deepcopy(PROPOSED)
        self.parent = MAIN
        self.files = [{"filename": "upstream.json", "status": "modified"}]
        self.pull = None
        self.runs = []
        self.published = True
        self.fail = None
        self.calls = []
        self.commands = []
        self.main = MAIN

    def detect(self, pin):
        responses = {
            "/releases/latest": {"tag_name": PROPOSED["tag"], "draft": False, "prerelease": False},
            "/git/ref/tags/" + PROPOSED["tag"]: {"object": {"type": "commit", "sha": OFFICIAL}},
        }
        return check_release.check_release(pin, responses.__getitem__)

    def api(self, method, path, payload=None):
        path = path.removeprefix("repos/" + REPOSITORY)
        self.calls.append((method, path, payload))
        if self.fail == (method, path):
            raise RuntimeError("private-token-response")
        if path == "/git/ref/heads/main":
            return {"object": {"type": "commit", "sha": self.main}}
        if path == "/git/ref/heads/upstream/v4.3.1":
            return {"object": {"type": "commit", "sha": self.branch}}
        if path.startswith("/contents/upstream.json?ref="):
            pin = PIN if path.endswith(MAIN) else self.branch_pin
            return {"type": "file", "encoding": "base64", "content": base64.b64encode(json.dumps(pin).encode()).decode()}
        if path == "/git/matching-refs/heads/upstream/v4.3.1":
            return [] if self.branch is None else [{"ref": "refs/heads/upstream/v4.3.1", "object": {"sha": self.branch}}]
        if method == "GET" and path == "/git/commits/" + MAIN:
            return {"tree": {"sha": "d" * 40}}
        if method == "GET" and path == "/git/commits/" + BRANCH:
            return {"parents": [{"sha": self.parent}]}
        if method == "POST" and path == "/git/blobs":
            self.branch_pin = json.loads(payload["content"])
            return {"sha": "e" * 40}
        if method == "POST" and path == "/git/trees":
            return {"sha": "f" * 40}
        if method == "POST" and path == "/git/commits":
            self.parent = payload["parents"][0]
            return {"sha": BRANCH}
        if method == "POST" and path == "/git/refs":
            self.branch = payload["sha"]
            return {}
        if path == "/compare/" + MAIN + "..." + BRANCH:
            return {"status": "ahead", "total_commits": 1, "files": self.files}
        if method == "GET" and path.startswith("/pulls?"):
            return [] if self.pull is None else [self.pull]
        if method == "POST" and path == "/pulls":
            self.pull = {
                "state": "open", "head": {"sha": self.branch, "ref": payload["head"]},
                "base": {"ref": "main"}, "html_url": "https://github.com/fixture/teslamate/pull/1",
            }
            return self.pull
        if path == "/actions/runs/1/jobs?per_page=100":
            return {"total_count": 1, "jobs": [{"name": "publish", "conclusion": "success" if self.published else "skipped"}]}
        raise AssertionError((method, path))

    def run(self, *args):
        self.commands.append(args)
        if args[:3] == ("gh", "run", "list"):
            if self.fail == "list":
                raise RuntimeError("private-token-response")
            return json.dumps(self.runs)
        if args[:3] == ("gh", "workflow", "run"):
            if self.fail == "dispatch":
                raise RuntimeError("private-token-response")
            self.runs = [{"databaseId": 1, "headSha": BRANCH, "status": "queued", "conclusion": ""}]
            if self.fail == "dispatch_accepted":
                raise RuntimeError("private-token-response")
            return ""
        raise AssertionError(args)

    def update(self):
        return updater.update_release(REPOSITORY, PIN, MAIN, api=self.api, run=self.run, detect=self.detect)

    def dispatches(self):
        return [args for args in self.commands if args[:3] == ("gh", "workflow", "run")]


class UpdateReleaseTests(unittest.TestCase):
    def test_current_is_report_only(self):
        fixture = GitHubFixture()
        with patch.dict(PROPOSED, PIN, clear=True):
            # The official pinned tag must resolve to the pinned commit.
            with patch(__name__ + ".OFFICIAL", MAIN):
                report = fixture.update()
        self.assertEqual(report["status"], "current")
        self.assertEqual(fixture.calls, [])
        self.assertEqual(fixture.commands, [])

    def test_new_release_creates_only_pin_commit_pr_and_explicit_dispatch(self):
        fixture = GitHubFixture()
        original = copy.deepcopy(PIN)
        report = fixture.update()
        self.assertEqual(report["status"], "dispatched")
        self.assertEqual(report["source_main"], MAIN)
        self.assertEqual(PIN, original)
        mutations = [(path, payload) for method, path, payload in fixture.calls if method == "POST"]
        self.assertEqual([path for path, _ in mutations], ["/git/blobs", "/git/trees", "/git/commits", "/git/refs", "/pulls"])
        self.assertEqual(json.loads(mutations[0][1]["content"]), PROPOSED)
        self.assertEqual(mutations[1][1]["tree"], [{"path": "upstream.json", "mode": "100644", "type": "blob", "sha": "e" * 40}])
        self.assertEqual(mutations[2][1]["parents"], [MAIN])
        self.assertEqual(mutations[3][1]["ref"], "refs/heads/upstream/v4.3.1")
        self.assertIn(MAIN, mutations[4][1]["body"])
        self.assertEqual(fixture.dispatches(), [("gh", "workflow", "run", "ci.yml", "--repo", REPOSITORY, "--ref", "upstream/v4.3.1", "-f", "publish=true")])

    def test_existing_queued_running_and_published_builds_are_idempotent(self):
        for status, conclusion in (("queued", ""), ("in_progress", ""), ("completed", "success")):
            with self.subTest(status=status):
                fixture = GitHubFixture()
                fixture.update()
                fixture.calls.clear()
                fixture.commands.clear()
                fixture.runs = [{"databaseId": 1, "headSha": BRANCH, "status": status, "conclusion": conclusion}]
                self.assertEqual(fixture.update()["status"], "already_started")
                self.assertFalse(any(method != "GET" for method, _, _ in fixture.calls))
                self.assertEqual(fixture.dispatches(), [])

    def test_moved_tag_branch_mismatch_main_drift_and_extra_files_stop(self):
        fixture = GitHubFixture()
        with patch(__name__ + ".OFFICIAL", "9" * 40):
            with patch.dict(PROPOSED, PIN, clear=True), self.assertRaises(ValueError):
                fixture.update()
        self.assertEqual(fixture.calls, [])
        for attribute, value in (
            ("branch_pin", dict(PROPOSED, commit="9" * 40)),
            ("parent", "9" * 40),
            ("main", "9" * 40),
            ("files", [{"filename": "ci.yml", "status": "modified"}]),
        ):
            with self.subTest(attribute=attribute):
                fixture = GitHubFixture()
                fixture.branch = BRANCH
                setattr(fixture, attribute, value)
                with self.assertRaises(ValueError):
                    fixture.update()
                self.assertEqual(fixture.dispatches(), [])
                self.assertFalse(any(method != "GET" for method, _, _ in fixture.calls))

    def test_creation_failure_never_dispatches_and_recovers_missing_steps(self):
        for failure in (("POST", "/git/refs"), ("POST", "/pulls"), "list", "dispatch"):
            with self.subTest(failure=failure):
                fixture = GitHubFixture()
                fixture.fail = failure
                with self.assertRaises(RuntimeError):
                    fixture.update()
                if failure != "dispatch":
                    self.assertEqual(fixture.dispatches(), [])
                retained_branch, retained_pull = fixture.branch, fixture.pull
                fixture.calls.clear()
                fixture.commands.clear()
                fixture.fail = None
                self.assertEqual(fixture.update()["status"], "dispatched")
                paths = [path for method, path, _ in fixture.calls if method == "POST"]
                if retained_branch:
                    self.assertNotIn("/git/refs", paths)
                    self.assertNotIn("/git/commits", paths)
                if retained_pull:
                    self.assertNotIn("/pulls", paths)

        # An accepted dispatch whose response was lost must not be dispatched twice.
        fixture = GitHubFixture()
        fixture.fail = "dispatch_accepted"
        with self.assertRaises(RuntimeError):
            fixture.update()
        fixture.commands.clear()
        fixture.fail = None
        self.assertEqual(fixture.update()["status"], "already_started")
        self.assertEqual(fixture.dispatches(), [])

    def test_failed_or_successful_nonpublication_build_can_retry_but_closed_pr_cannot(self):
        for conclusion, published in (("failure", False), ("success", False)):
            with self.subTest(conclusion=conclusion):
                fixture = GitHubFixture()
                fixture.update()
                fixture.commands.clear()
                fixture.runs = [{"databaseId": 1, "headSha": BRANCH, "status": "completed", "conclusion": conclusion}]
                fixture.published = published
                self.assertEqual(fixture.update()["status"], "dispatched")
                self.assertEqual(len(fixture.dispatches()), 1)
        fixture.pull["state"] = "closed"
        fixture.commands.clear()
        with self.assertRaises(ValueError):
            fixture.update()
        self.assertEqual(fixture.dispatches(), [])

    def test_mutable_ref_or_official_proposal_change_before_dispatch_stops(self):
        fixture = GitHubFixture()
        original = fixture.detect
        count = 0

        def changed(pin):
            nonlocal count
            count += 1
            report = original(pin)
            if count > 1:
                report["proposed"]["commit"] = "9" * 40
            return report

        fixture.detect = changed
        with self.assertRaises(ValueError):
            fixture.update()
        self.assertEqual(fixture.dispatches(), [])

    def test_cli_and_command_failures_do_not_leak_remote_output_or_token(self):
        result = subprocess.CompletedProcess([], 1, stdout="private-token-response", stderr="private-token-response")
        with patch.object(updater.subprocess, "run", return_value=result) as run, self.assertRaises(RuntimeError) as error:
            updater.command("gh", "api", "repos/fixture/teslamate", input='{"value":"example"}')
        self.assertNotIn("private-token-response", str(error.exception))
        self.assertEqual(run.call_args.args[0], ("gh", "api", "repos/fixture/teslamate"))
        self.assertEqual(run.call_args.kwargs["timeout"], 60)
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        with (
            patch.object(sys, "argv", ["update_release"]),
            patch.dict(os.environ, {"GITHUB_REF": "refs/heads/main", "GITHUB_REPOSITORY": REPOSITORY}),
            patch.object(updater, "command", side_effect=RuntimeError("private-token-response")),
            patch.object(sys, "stderr", new_callable=io.StringIO) as output,
        ):
            self.assertEqual(updater.main(), 1)
        self.assertNotIn("private-token-response", output.getvalue())
        with (
            patch.object(sys, "argv", ["update_release"]),
            patch.dict(os.environ, {"GITHUB_REF": "refs/heads/upstream/v4.3.1"}),
            patch.object(sys, "stderr", new_callable=io.StringIO) as output,
        ):
            self.assertEqual(updater.main(), 1)
        self.assertIn("Updater must run from main", output.getvalue())


if __name__ == "__main__":
    unittest.main()
