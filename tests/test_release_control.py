"""Offline API and OCI fixtures; no real merges, dispatches or GHCR writes."""

import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_control as control


REPO = "fixture/georelay"
HEAD, MAIN, MERGED = "a" * 40, "b" * 40, "c" * 40
VERSION = "v4.3.0-georelay-beta-" + HEAD
INDEX = "application/vnd.oci.image.index.v1+json"
IMAGE = "application/vnd.oci.image.manifest.v1+json"


class Fixture:
    def __init__(self):
        self.run = {"id": 10, "run_attempt": 1, "status": "completed", "conclusion": "success", "workflow_id": 3,
                    "event": "pull_request", "head_sha": HEAD, "head_branch": "feature",
                    "repository": {"full_name": REPO}, "head_repository": {"full_name": REPO},
                    "display_title": "images/pull_request/7/" + HEAD + "/publish/-",
                    "html_url": "https://github.com/" + REPO + "/actions/runs/10"}
        self.run["name"] = self.run["display_title"]
        self.workflow = {"id": 3, "name": "Validate and build", "path": ".github/workflows/ci.yml"}
        self.pull = {"number": 7, "state": "open", "draft": False, "merged": False, "merge_commit_sha": None,
                     "head": {"sha": HEAD, "ref": "feature", "repo": {"full_name": REPO}},
                     "base": {"ref": "main", "repo": {"full_name": REPO}}, "mergeable": True, "mergeable_state": "clean"}
        self.jobs = [{"id": 20 + i, "name": name, "run_id": 10, "status": "completed", "conclusion": "success"}
                     for i, name in enumerate(sorted(control.JOBS))]
        verify = next(job for job in self.jobs if job["name"] == "verify")
        verify["check_run_url"] = "https://api.github.com/repos/" + REPO + "/check-runs/" + str(verify["id"])
        self.check = {"app": {"id": 15368}, "name": "verify", "head_sha": HEAD, "status": "completed", "conclusion": "success",
                      "details_url": self.run["html_url"] + "/job/" + str(verify["id"])}
        self.comparison = {"status": "ahead", "merge_base_commit": {"sha": MAIN}}
        self.branch_summary = {"name": "main", "protected": True, "protection": {
            "enabled": True, "required_status_checks": {
                "enforcement_level": "everyone", "checks": [{"context": "verify", "app_id": 15368}],
            },
        }}
        self.calls, self.fetches = [], []
        self.documents = {}
        self.fail, self.merge_result, self.changed_on_last_read = None, True, False
        self.changed_after_protection_read = False
        self.changed_main_after_protection_read = False
        self.main_sha = MAIN
        self.pull_reads = 0
        self.record_exists = True
        self.images()

    def images(self, revision=HEAD, version=VERSION):
        self.documents.clear()
        def store(value, media_type):
            raw = json.dumps(value, sort_keys=True).encode()
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            self.documents[digest] = raw
            return {"mediaType": media_type, "size": len(raw), "digest": digest}
        entries = []
        for architecture in ("amd64", "arm64"):
            config = store({"os": "linux", "architecture": architecture, "config": {"Labels": {
                "org.opencontainers.image.source": "https://github.com/" + REPO,
                "org.opencontainers.image.revision": revision, "org.opencontainers.image.version": version,
            }}}, "application/vnd.oci.image.config.v1+json")
            image = store({"schemaVersion": 2, "mediaType": IMAGE, "config": config, "layers": []}, IMAGE)
            entries.append(dict(image, platform={"os": "linux", "architecture": architecture}))
        self.documents[VERSION] = json.dumps({"schemaVersion": 2, "mediaType": INDEX, "manifests": entries}).encode()

    def api(self, method, path, payload=None):
        path = path.removeprefix("repos/" + REPO)
        self.calls.append((method, path, payload))
        if self.fail == path and not (path.endswith("/merge") and self.fail == "lost_merge_response"):
            raise RuntimeError("private-remote-response")
        if path == "/actions/runs/10/attempts/1":
            return copy.deepcopy(self.run)
        if path == "/actions/workflows/ci.yml":
            return copy.deepcopy(self.workflow)
        if path == "/pulls/7":
            self.pull_reads += 1
            if self.changed_on_last_read and self.pull_reads == 3:
                self.pull["head"]["sha"] = "d" * 40
            return copy.deepcopy(self.pull)
        if path == "/actions/runs/10/attempts/1/jobs?per_page=100":
            return {"total_count": len(self.jobs), "jobs": copy.deepcopy(self.jobs)}
        if path.startswith("/check-runs/"):
            return copy.deepcopy(self.check)
        if path == "/contents/upstream.json?ref=" + HEAD:
            pin = {"tag": "v4.3.0", "commit": MAIN, "repository": "https://github.com/teslamate-org/teslamate.git"}
            return {"type": "file", "encoding": "base64", "content": base64.b64encode(json.dumps(pin).encode()).decode()}
        if path == "graphql":
            raise RuntimeError("Protection rule query forbidden for Actions token")
        if path == "/branches/main":
            if self.changed_after_protection_read:
                self.pull["head"]["sha"] = "d" * 40
            if self.changed_main_after_protection_read:
                self.main_sha = "e" * 40
            return copy.deepcopy(self.branch_summary)
        if path == "/git/ref/heads/main":
            return {"object": {"type": "commit", "sha": self.main_sha}}
        if path == "/git/ref/heads/feature":
            return {"object": {"type": "commit", "sha": HEAD}}
        if path == "/compare/" + MAIN + "..." + HEAD:
            return copy.deepcopy(self.comparison)
        if method == "PUT" and path == "/pulls/7/merge":
            if payload["sha"] != self.pull["head"]["sha"]:
                raise RuntimeError("Expected head mismatch")
            if self.main_sha != MAIN:
                raise RuntimeError("Strict main freshness check failed")
            if self.merge_result:
                self.pull.update(state="closed", merged=True, merge_commit_sha=MERGED)
            if self.fail == "lost_merge_response":
                raise RuntimeError("private-remote-response")
            return {"merged": self.merge_result, "sha": MERGED if self.merge_result else None}
        if method == "POST" and path == "/actions/workflows/ci.yml/dispatches":
            return None  # The pinned GitHub REST version may return 204, no JSON.
        raise AssertionError((method, path, payload))

    def fetch(self, owner, package, reference, kind="manifests"):
        self.fetches.append((owner, package, reference, kind))
        return self.documents[reference]

    def record_verify(self, repository, run_id, attempt, source, version, **kwargs):
        if not self.record_exists or (repository, run_id, attempt, source, version) != (REPO, 10, 1, HEAD, VERSION):
            raise ValueError("Release record absent or mismatched")

    def control(self, apply=True, repair_run_id=None, repair_verify=None):
        return control.control(REPO, 10, 1, self.api, self.fetch, apply=apply, sleep=lambda _: None,
                               record_verify=self.record_verify, repair_run_id=repair_run_id, repair_verify=repair_verify)

    def writes(self):
        return [call for call in self.calls if call[0] != "GET"]


class ReleaseControlTests(unittest.TestCase):
    def test_current_beta_merges_once_expected_head_reads_back_then_dispatches(self):
        fixture = Fixture()
        result = fixture.control()
        self.assertEqual(result["status"], "merged_dispatched")
        self.assertFalse(result["notify"])
        self.assertEqual(fixture.writes(), [
            ("PUT", "/pulls/7/merge", {"sha": HEAD, "merge_method": "merge"}),
            ("POST", "/actions/workflows/ci.yml/dispatches", {"ref": "main", "inputs": {"publish": "true", "expected_main_sha": MERGED, "source_pr": "7"}}),
        ])
        self.assertEqual({row[1] for row in fixture.fetches}, {"georelay", "georelay-adapter"})
        self.assertIn(("GET", "/branches/main", None), fixture.calls)
        self.assertFalse(any(path == "graphql" or "/protection" in path for _, path, _ in fixture.calls))
        fixture = Fixture()
        self.assertEqual(fixture.control(apply=False)["status"], "dry_run")
        self.assertEqual(fixture.writes(), [])

    def test_untrusted_workflow_fork_attempt_sha_and_check_only_never_write_or_notify(self):
        for field, value in (("workflow_id", 99), ("head_repository", {"full_name": "fork/georelay"}), ("run_attempt", 2),
                             ("head_sha", MAIN), ("display_title", "images/pull_request/7/" + HEAD + "/check/-"), ("html_url", "https://untrusted.invalid/run")):
            with self.subTest(field=field):
                fixture = Fixture()
                fixture.run[field] = value
                result = fixture.control()
                self.assertEqual(result["status"], "skipped")
                self.assertFalse(result["notify"])
                self.assertEqual(fixture.writes(), [])
        fixture = Fixture()
        fixture.workflow["name"] = "Unexpected workflow"
        result = fixture.control()
        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["notify"])
        self.assertEqual(fixture.writes(), [])

    def test_stale_draft_closed_fork_base_and_last_read_changes_skip(self):
        for edit in (lambda p: p.update(draft=True), lambda p: p.update(state="closed"),
                     lambda p: p["head"].update(sha=MAIN), lambda p: p["base"].update(ref="other"),
                     lambda p: p["head"]["repo"].update(full_name="fork/georelay")):
            fixture = Fixture()
            edit(fixture.pull)
            self.assertFalse(fixture.control()["notify"])
            self.assertEqual(fixture.writes(), [])
        for status in ("behind", "diverged"):
            fixture = Fixture()
            fixture.comparison["status"] = status
            self.assertEqual(fixture.control()["status"], "skipped")
            self.assertEqual(fixture.writes(), [])
        fixture = Fixture()
        fixture.comparison["merge_base_commit"]["sha"] = HEAD
        self.assertEqual(fixture.control()["status"], "skipped")
        fixture = Fixture()
        fixture.changed_on_last_read = True
        self.assertEqual(fixture.control()["reason"], "candidate_changed_before_merge")
        self.assertEqual(fixture.writes(), [])

    def test_verify_skipped_neutral_wrong_app_run_and_missing_architecture_refuse_merge(self):
        for edit in (lambda f: f.check.update(conclusion="skipped"), lambda f: f.check.update(conclusion="neutral"),
                     lambda f: f.check.update(head_sha=MAIN), lambda f: f.check.update(app={"id": 99}),
                     lambda f: f.check.update(details_url="https://github.com/fixture/georelay/actions/runs/11/job/24"),
                     lambda f: f.jobs.pop(0), lambda f: f.jobs[0].update(conclusion="failure")):
            fixture = Fixture()
            edit(fixture)
            result = fixture.control()
            self.assertEqual(result["reason"], "beta_jobs")
            self.assertTrue(result["notify"])
            self.assertEqual(fixture.writes(), [])

    def test_release_record_missing_or_bootstrap_failure_cannot_be_ready(self):
        fixture = Fixture()
        fixture.record_exists = False
        result = fixture.control()
        self.assertEqual(result["reason"], "release_record")
        self.assertEqual(fixture.writes(), [])
        fixture = Fixture()
        fixture.jobs = [job for job in fixture.jobs if job["name"] != "release-record"]
        self.assertEqual(fixture.control()["reason"], "beta_jobs")
        self.assertEqual(fixture.writes(), [])

    def test_only_failed_record_gate_can_be_repaired_other_jobs_still_block(self):
        fixture = Fixture()
        fixture.run["conclusion"] = "failure"
        next(job for job in fixture.jobs if job["name"] == "release-record")["conclusion"] = "failure"
        proof_calls = []
        def proof(*args, **kwargs):
            proof_calls.append(args)
        self.assertEqual(fixture.control(repair_run_id=99, repair_verify=proof)["status"], "merged_dispatched")
        self.assertEqual(proof_calls, [(REPO, 10, 1, HEAD, VERSION, 99)])
        for name in ("publish", "verify", "build-arm64"):
            fixture = Fixture()
            fixture.run["conclusion"] = "failure"
            next(job for job in fixture.jobs if job["name"] == name)["conclusion"] = "failure"
            self.assertEqual(fixture.control(repair_run_id=99, repair_verify=proof)["reason"], "beta_jobs")
            self.assertEqual(fixture.writes(), [])

    def test_registry_incomplete_tampered_or_wrong_oci_source_refuses_merge(self):
        for issue in ("wrong_revision", "wrong_version", "missing_index", "missing_architecture", "tampered_blob"):
            with self.subTest(issue=issue):
                fixture = Fixture()
                if issue == "wrong_revision":
                    fixture.images(revision=MAIN)
                elif issue == "wrong_version":
                    fixture.images(version="wrong")
                elif issue == "missing_index":
                    del fixture.documents[VERSION]
                elif issue == "missing_architecture":
                    index = json.loads(fixture.documents[VERSION])
                    index["manifests"].pop()
                    fixture.documents[VERSION] = json.dumps(index).encode()
                else:
                    key = next(key for key in fixture.documents if key.startswith("sha256:"))
                    fixture.documents[key] += b" "
                result = fixture.control()
                self.assertEqual(result["reason"], "beta_index")
                self.assertEqual(fixture.writes(), [])

    def test_unknown_conflicted_or_blocked_mergeability_does_not_merge(self):
        for mergeable, state in ((None, "unknown"), (False, "dirty"), (True, "blocked")):
            fixture = Fixture()
            fixture.pull.update(mergeable=mergeable, mergeable_state=state)
            self.assertEqual(fixture.control()["reason"], "merge_not_ready")
            self.assertEqual(fixture.writes(), [])
            self.assertLessEqual(fixture.pull_reads, 4)

    def test_missing_loose_admin_exempt_or_wrong_verify_app_protection_blocks_merge(self):
        for change in (lambda f: f.branch_summary.update(name="other"),
                       lambda f: f.branch_summary.update(protected=False),
                       lambda f: f.branch_summary["protection"].update(enabled=False),
                       lambda f: f.branch_summary["protection"]["required_status_checks"].update(enforcement_level="non_admins"),
                       lambda f: f.branch_summary["protection"]["required_status_checks"].update(checks=[]),
                       lambda f: f.branch_summary["protection"]["required_status_checks"]["checks"][0].update(app_id=99),
                       lambda f: f.branch_summary.pop("protection"),
                       lambda f: setattr(f, "branch_summary", None), lambda f: setattr(f, "fail", "/branches/main")):
            fixture = Fixture()
            change(fixture)
            result = fixture.control()
            self.assertEqual(result["reason"], "branch_protection")
            self.assertTrue(result["notify"])
            self.assertEqual(fixture.writes(), [])
            self.assertNotIn("private-remote-response", json.dumps(result))

    def test_head_change_after_protection_read_rejected_by_expected_head_merge(self):
        fixture = Fixture()
        fixture.changed_after_protection_read = True
        result = fixture.control()
        self.assertEqual(fixture.writes(), [("PUT", "/pulls/7/merge", {"sha": HEAD, "merge_method": "merge"})])
        self.assertEqual(fixture.pull["head"]["sha"], "d" * 40)
        self.assertEqual(fixture.pull["state"], "open")
        self.assertFalse(fixture.pull["merged"])
        self.assertIsNone(fixture.pull["merge_commit_sha"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "merge")
        self.assertTrue(result["notify"])
        self.assertEqual(result["notification"]["stage"], "merge")
        self.assertNotIn("merged_sha", result)

    def test_main_change_after_protection_read_rejected_by_server_strict(self):
        fixture = Fixture()
        fixture.changed_main_after_protection_read = True
        result = fixture.control()
        self.assertEqual(fixture.writes(), [("PUT", "/pulls/7/merge", {"sha": HEAD, "merge_method": "merge"})])
        self.assertEqual(fixture.main_sha, "e" * 40)
        self.assertEqual(fixture.pull["head"]["sha"], HEAD)
        self.assertEqual(fixture.pull["state"], "open")
        self.assertFalse(fixture.pull["merged"])
        self.assertIsNone(fixture.pull["merge_commit_sha"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "merge")
        self.assertTrue(result["notify"])
        self.assertEqual(result["notification"]["stage"], "merge")
        self.assertNotIn("merged_sha", result)

    def test_rejected_merge_no_dispatch_uncertain_merge_reads_back_without_retry(self):
        for fail in ("/pulls/7/merge", None):
            fixture = Fixture()
            fixture.merge_result = False
            fixture.fail = fail
            result = fixture.control()
            self.assertEqual(result["reason"], "merge")
            self.assertTrue(result["notify"])
            self.assertEqual(len(fixture.writes()), 1)
        fixture = Fixture()
        fixture.fail = "lost_merge_response"
        self.assertEqual(fixture.control()["status"], "merged_dispatched")
        self.assertEqual(len(fixture.writes()), 2)
        fixture = Fixture()
        fixture.fail = "/actions/workflows/ci.yml/dispatches"
        result = fixture.control()
        self.assertEqual(result["reason"], "main_dispatch")
        self.assertEqual(result["merged_sha"], MERGED)
        self.assertTrue(result["notify"])
        self.assertNotIn("private-remote-response", json.dumps(result))

    def test_metadata_only_success_or_python_failure_skips_without_merge_or_bark(self):
        for conclusion in ("success", "failure", "cancelled", "timed_out"):
            fixture = Fixture()
            fixture.run["conclusion"] = conclusion
            for job in fixture.jobs:
                if job["name"] in {"build-amd64", "build-arm64", "publish"}:
                    job["conclusion"] = "skipped"
                if job["name"] == "checks":
                    job["conclusion"] = conclusion
                    job["steps"] = [{"name": "Python checks for metadata-only changes", "status": "completed", "conclusion": conclusion}]
            result = fixture.control()
            self.assertEqual(result["reason"], "metadata_only_run")
            self.assertFalse(result["notify"])
            self.assertEqual(fixture.writes(), [])
            self.assertEqual(fixture.fetches, [])
            jobs_reads = [call for call in fixture.calls if "/jobs?" in call[1]]
            self.assertEqual(len(jobs_reads), 1)
        fixture = Fixture()
        fixture.run["conclusion"] = "failure"
        for job in fixture.jobs:
            if job["name"] == "checks":
                job["steps"] = [{"name": "Python checks for metadata-only changes", "status": "completed", "conclusion": "skipped"}]
        self.assertTrue(fixture.control()["notify"])

    def test_failure_notifies_without_artifacts_indexes_or_verify_success(self):
        fixture = Fixture()
        fixture.run["conclusion"] = "failure"
        fixture.documents.clear()
        fixture.jobs[0]["conclusion"] = "failure"
        result = fixture.control()
        self.assertTrue(result["notify"])
        self.assertEqual(result["reason"], "beta_validation")
        self.assertTrue(result["notification"]["failed_jobs"])
        self.assertEqual(fixture.fetches, [])
        self.assertEqual(fixture.writes(), [])
        fixture.fail = "/actions/runs/10/attempts/1/jobs?per_page=100"
        self.assertTrue(fixture.control()["notify"])

    def test_main_observer_delegates_all_success_failure_and_stale_paths_before_pr_read(self):
        for event in ("push", "workflow_dispatch"):
            for conclusion in ("success", "failure", "cancelled", "timed_out"):
                fixture = Fixture()
                title = ("images/push/0/" + MAIN + "/publish/-" if event == "push" else
                         "images/workflow_dispatch/7/" + MAIN + "/publish/" + MERGED)
                fixture.run.update(event=event, head_branch="main", head_sha=MAIN,
                                   conclusion=conclusion, display_title=title)
                fixture.fail = "/pulls/7"
                result = fixture.control()
                self.assertEqual(result["reason"], "main_failure_owned_by_ci")
                self.assertFalse(result["notify"])
                self.assertEqual(fixture.writes(), [])
                self.assertEqual(fixture.fetches, [])
                self.assertFalse(any("/pulls/" in path or "/jobs?" in path for _, path, _ in fixture.calls))

    def test_real_failed_beta_still_notifies_after_pr_closed_draft_or_head_changed(self):
        for change in (lambda p: p.update(state="closed"), lambda p: p.update(draft=True), lambda p: p["head"].update(sha=MAIN)):
            fixture = Fixture()
            change(fixture.pull)
            fixture.run["conclusion"] = "failure"
            result = fixture.control()
            self.assertTrue(result["notify"])
            self.assertEqual(result["reason"], "beta_validation")
            self.assertEqual(fixture.writes(), [])

    def test_beta_finalizer_success_is_accepted_but_non_success_still_blocks_merge(self):
        for conclusion in ("success", "failure", "skipped"):
            fixture = Fixture()
            fixture.jobs.append({"id": 30, "name": "main-failure-notification", "run_id": 10,
                                 "status": "completed", "conclusion": conclusion})
            result = fixture.control()
            if conclusion == "success":
                self.assertEqual(result["status"], "merged_dispatched")
                self.assertEqual(len(fixture.writes()), 2)
            else:
                self.assertEqual(result["reason"], "beta_jobs")
                self.assertEqual(fixture.writes(), [])

    def test_no_pr_branch_can_notify_failure_without_auto_merge_and_bad_context_is_secret_safe(self):
        fixture = Fixture()
        fixture.run.update(event="workflow_dispatch", display_title="images/workflow_dispatch/0/" + HEAD + "/publish/-")
        self.assertFalse(fixture.control()["notify"])
        fixture.run["conclusion"] = "failure"
        self.assertTrue(fixture.control()["notify"])
        self.assertEqual(fixture.writes(), [])
        fixture = Fixture()
        fixture.fail = "/actions/runs/10/attempts/1"
        result = fixture.control()
        self.assertFalse(result["notify"])
        self.assertNotIn("private-remote-response", json.dumps(result))


class MainFailureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.fixture.pull.update(state="closed", merged=True, merge_commit_sha=MERGED)
        self.event = {"repository": {"full_name": REPO}, "inputs": {
            "publish": "true", "source_pr": "7", "expected_main_sha": MERGED,
        }}
        self.needs = {"checks": {"result": "success", "outputs": {"image_required": "true"}},
                      "build": {"result": "success"}, "verify": {"result": "success"},
                      "publish": {"result": "failure"}, "release-record": {"result": "success"}}
        self.environment = {"GITHUB_REPOSITORY": REPO, "GITHUB_REF": "refs/heads/main",
                            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_SHA": MERGED,
                            "GITHUB_RUN_ID": "10", "GITHUB_RUN_ATTEMPT": "1"}

    def report(self):
        return control.main_failure(self.event, self.environment, self.needs, api=self.fixture.api)

    def test_current_main_failure_reports_actual_run_without_completed_observer_or_writes(self):
        self.fixture.run["status"] = "in_progress"
        result = self.report()
        self.assertEqual(result["reason"], "main_publication")
        self.assertTrue(result["notify"])
        notice = result["notification"]
        self.assertEqual(notice["source_pr"], 7)
        self.assertEqual(notice["sha"], MERGED)
        self.assertEqual(notice["expected_main_sha"], MERGED)
        self.assertEqual(notice["failed_jobs"], ["publish"])
        self.assertEqual(notice["run_url"], "https://github.com/" + REPO + "/actions/runs/10")
        self.assertEqual(self.fixture.calls, [("GET", "/pulls/7", None)])
        self.assertEqual(self.fixture.writes(), [])

    def test_main_record_failure_is_a_real_failure_and_whitelisted_job(self):
        self.needs["publish"]["result"] = "success"
        self.needs["release-record"]["result"] = "failure"
        self.assertEqual(self.report()["notification"]["failed_jobs"], ["release-record"])

    def test_stale_expected_main_falls_back_to_basic_actual_run_and_preserves_expected(self):
        self.environment["GITHUB_SHA"] = MAIN
        self.needs["checks"] = {"result": "failure", "outputs": {}}
        self.needs["build"]["result"] = "skipped"
        self.needs["verify"]["result"] = "failure"
        self.needs["publish"]["result"] = "skipped"
        notice = self.report()["notification"]
        self.assertEqual(notice["sha"], MAIN)
        self.assertEqual(notice["expected_main_sha"], MERGED)
        self.assertEqual(notice["source_pr"], 0)
        self.assertEqual(notice["failed_jobs"], ["checks", "verify"])
        self.assertEqual(self.fixture.writes(), [])

    def test_unreadable_or_unrelated_pr_does_not_lose_basic_notification(self):
        for edit in (lambda f: setattr(f, "fail", "/pulls/7"), lambda f: f.pull.update(number=8),
                     lambda f: f.pull.update(merged=False), lambda f: f.pull.update(merge_commit_sha=HEAD),
                     lambda f: f.pull["head"]["repo"].update(full_name="fork/georelay"),
                     lambda f: f.pull["base"]["repo"].update(full_name="fork/georelay"),
                     lambda f: f.pull["base"].update(ref="other")):
            with self.subTest(edit=edit):
                self.setUp()
                edit(self.fixture)
                result = self.report()
                self.assertTrue(result["notify"])
                self.assertEqual(result["notification"]["source_pr"], 0)
                self.assertEqual(result["notification"]["expected_main_sha"], MERGED)
                self.assertEqual(self.fixture.writes(), [])
                self.assertNotIn("private-remote-response", json.dumps(result))
        self.event["inputs"].update(source_pr="untrusted-private-text", expected_main_sha="invalid-private-text")
        result = self.report()
        self.assertTrue(result["notify"])
        self.assertEqual(result["notification"]["source_pr"], 0)
        self.assertNotIn("expected_main_sha", result["notification"])
        self.assertNotIn("private-text", json.dumps(result))

    def test_main_push_cancelled_verify_and_build_summary_are_accurate(self):
        self.environment["GITHUB_EVENT_NAME"] = "push"
        self.event.pop("inputs")
        self.needs["build"]["result"] = "cancelled"
        self.needs["verify"]["result"] = "cancelled"
        self.needs["publish"]["result"] = "skipped"
        notice = self.report()["notification"]
        self.assertEqual(notice["source_pr"], 0)
        self.assertEqual(notice["failed_jobs"], ["verify"])
        self.assertEqual(notice["conclusion"], "cancelled")
        self.assertEqual(self.fixture.calls, [])

    def test_unrequested_metadata_success_and_untrusted_native_context_never_notify(self):
        for edit in (lambda: self.event["inputs"].update(publish="false"),
                     lambda: self.needs["checks"]["outputs"].update(image_required="false"),
                     lambda: self.needs["publish"].update(result="success")):
            self.setUp()
            edit()
            self.assertFalse(self.report()["notify"])
            self.assertEqual(self.fixture.calls, [])
        for edit in (lambda: self.environment.update(GITHUB_REF="refs/heads/feature"),
                     lambda: self.environment.update(GITHUB_EVENT_NAME="pull_request"),
                     lambda: self.environment.update(GITHUB_SHA="bad-private-text"),
                     lambda: self.environment.update(GITHUB_RUN_ID="0"),
                     lambda: self.event["repository"].update(full_name="fork/georelay")):
            self.setUp()
            edit()
            with self.assertRaises(ValueError):
                self.report()
            self.assertEqual(self.fixture.calls, [])

    def test_actual_workflow_native_decision_covers_failures_and_excludes_beta_noops(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        finalizer = workflow.split("  main-failure-notification:\n", 1)[1]
        expression = re.search(r'run: echo "notify=\$\{\{ (.*?) \}\}"', finalizer).group(1)
        for ref, event_name, publish, image_required, verify, publication, expected in (
                ("main", "push", False, "true", "success", "failure", True),
                ("main", "workflow_dispatch", True, "true", "success", "failure", True),
                ("main", "workflow_dispatch", True, "", "failure", "skipped", True),
                ("main", "push", False, "true", "failure", "skipped", True),
                ("main", "push", False, "true", "cancelled", "skipped", True),
                ("main", "push", False, "true", "success", "cancelled", True),
                ("main", "push", False, "false", "failure", "skipped", False),
                ("main", "workflow_dispatch", False, "true", "failure", "skipped", False),
                ("main", "push", False, "true", "success", "success", False),
                ("feature", "pull_request", False, "true", "failure", "skipped", False),
                ("feature", "workflow_dispatch", True, "true", "success", "failure", False),
                ("main", "pull_request", False, "true", "failure", "skipped", False)):
            with self.subTest(ref=ref, event=event_name, verify=verify, publication=publication):
                values = {"github.ref": "refs/heads/" + ref, "github.event_name": event_name,
                          "inputs.publish": publish, "needs.checks.outputs.image_required": image_required,
                          "needs.verify.result": verify, "needs.publish.result": publication, "needs.release-record.result": "success"}
                native_condition = expression
                for key, value in values.items():
                    native_condition = native_condition.replace(key, repr(value))
                native_condition = native_condition.replace("&&", "and").replace("||", "or")
                self.assertEqual(eval(native_condition, {"__builtins__": {}}, {}), expected)
        self.assertIn("    needs: [checks, build, verify, publish, release-record]\n    if: always()", finalizer)
        self.assertIn("ref: ${{ github.sha }}", finalizer)
        self.assertEqual(finalizer.count("${{ secrets.BARK_URL }}"), 1)
        self.assertNotIn("${{ secrets.BARK_URL }}", finalizer.split("      - name: Notify main publication failure through Bark")[0])
        self.assertIn("BARK_URL: https://notification.invalid/dry-run", finalizer)

    def test_cli_report_mode_is_readonly_successful_step_and_rejects_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "event.json"
            output_path = Path(directory) / "report.json"
            github_output = Path(directory) / "github-output"
            event_path.write_text(json.dumps(self.event))
            environment = dict(self.environment, GITHUB_EVENT_PATH=str(event_path),
                               GITHUB_OUTPUT=str(github_output), WORKFLOW_NEEDS=json.dumps(self.needs))
            args = ["release_control.py", "--main-failure", "--output", str(output_path)]
            with patch.dict(os.environ, environment, clear=True), patch.object(sys, "argv", args), \
                    patch.object(control, "control") as observer, patch.object(control, "github", self.fixture.api), \
                    patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(control.main(), 0)
            observer.assert_not_called()
            self.assertTrue(json.loads(output_path.read_text())["notify"])
            self.assertEqual(github_output.read_text(), "notify=true\n")
            with patch.object(sys, "argv", args + ["--apply"]), patch("sys.stderr", new_callable=io.StringIO), \
                    patch.object(control, "control") as observer, patch.object(control, "main_failure") as reporter:
                with self.assertRaises(SystemExit) as error:
                    control.main()
                self.assertEqual(error.exception.code, 2)
            observer.assert_not_called()
            reporter.assert_not_called()
            environment["GITHUB_REF"] = "refs/heads/feature"
            with patch.dict(os.environ, environment, clear=True), patch.object(sys, "argv", args), \
                    patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(control.main(), 1)
            self.assertFalse(json.loads(output_path.read_text())["notify"])


if __name__ == "__main__":
    unittest.main()
