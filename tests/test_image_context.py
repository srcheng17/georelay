"""One event interpretation must drive checkout identity, labels and publication."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import image_context as context

SHA, MERGE = "a" * 40, "b" * 40
REPOSITORY = "fixture/georelay"
PIN = {"tag": "v4.3.0"}


def pull_event():
    return {"number": 7, "pull_request": {
        "head": {"sha": SHA, "ref": "feature", "repo": {"full_name": REPOSITORY}},
        "base": {"ref": "main", "repo": {"full_name": REPOSITORY}},
    }}


class ImageContextTests(unittest.TestCase):
    def derive(self, event_name, event, ref="refs/heads/main", sha=SHA):
        return context.image_context(event_name, event, sha, ref, REPOSITORY, PIN)

    def test_stable_and_beta_share_exact_tested_sha_and_full_version(self):
        stable = self.derive("push", {})
        self.assertEqual(stable["version"], "v4.3.0-georelay-" + SHA)
        self.assertTrue(stable["publish_required"])
        beta = self.derive("pull_request", pull_event(), "refs/pull/7/merge", MERGE)
        self.assertEqual(beta["source_sha"], SHA)
        self.assertEqual(beta["version"], "v4.3.0-georelay-beta-" + SHA)
        self.assertEqual(beta["source_ref"], "refs/heads/feature")
        self.assertEqual(beta["pr_number"], "7")
        self.assertTrue(beta["publish_required"])

    def test_fork_nonmain_base_and_branch_push_cannot_request_publication(self):
        for field in ("head", "base"):
            event = pull_event()
            event["pull_request"][field]["repo"]["full_name"] = "fork/georelay"
            self.assertFalse(self.derive("pull_request", event)["publish_required"])
        event = pull_event()
        event["pull_request"]["base"]["ref"] = "different"
        self.assertFalse(self.derive("pull_request", event)["publish_required"])
        self.assertFalse(self.derive("push", {}, "refs/heads/feature")["publish_required"])

    def test_dispatch_inputs_are_strict_and_expected_sha_binds_only_main(self):
        for value, publish in ((True, True), (False, False), ("true", True), ("false", False)):
            self.assertEqual(self.derive("workflow_dispatch", {"inputs": {"publish": value}})["publish_required"], publish)
        for invalid in ("TRUE", "False", "yes", "", None, 0, 1, [], {}):
            with self.subTest(invalid=invalid), self.assertRaises((ValueError, TypeError)):
                self.derive("workflow_dispatch", {"inputs": {"publish": invalid}})
        event = {"inputs": {"publish": "true", "expected_main_sha": SHA, "source_pr": "7"}}
        self.assertEqual(self.derive("workflow_dispatch", event)["expected_main_sha"], SHA)
        for ref, expected in (("refs/heads/feature", SHA), ("refs/heads/main", MERGE)):
            with self.assertRaises(ValueError):
                self.derive("workflow_dispatch", {"inputs": {"expected_main_sha": expected}}, ref)
        self.assertEqual(self.derive("workflow_dispatch", {"inputs": {"publish": "true", "source_pr": "7"}}, "refs/heads/feature")["channel"], "beta")
        self.assertFalse(self.derive("workflow_dispatch", {})["publish_required"])

    def test_malformed_sha_ref_repository_or_pr_number_fail_closed(self):
        for sha in ("0" * 40, MERGE.upper(), "bad", None):
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                self.derive("push", {}, sha=sha)
        for ref in ("refs/tags/v4.3.0", "refs/heads/a..b", "refs/heads/a|b\n", "refs/heads/a.lock", "refs/heads/-/../main", "refs/heads/"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                self.derive("workflow_dispatch", {}, ref)
        for number in (0, -1, True, "01", "7\n", "bad"):
            with self.subTest(number=number), self.assertRaises(ValueError):
                self.derive("workflow_dispatch", {"inputs": {"source_pr": number}})
        with self.assertRaises(ValueError):
            context.image_context("push", {}, SHA, "refs/heads/main", "invalid", PIN)

    def test_cli_appends_outputs_and_rejects_checkout_mismatch_without_remote_data(self):
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory) / "event.json"
            event.write_text(json.dumps(pull_event()))
            output = Path(directory) / "output"
            env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event),
                   "GITHUB_SHA": MERGE, "GITHUB_REF": "refs/pull/7/merge", "GITHUB_REPOSITORY": REPOSITORY,
                   "GITHUB_OUTPUT": str(output)}
            checkout = subprocess.CompletedProcess([], 0, stdout=SHA)
            with patch.dict(os.environ, env), patch.object(context, "load_pin", return_value=PIN), patch.object(context.subprocess, "run", return_value=checkout), patch.object(sys, "argv", ["image_context"]), patch.object(sys, "stdout", new_callable=io.StringIO):
                self.assertEqual(context.main(), 0)
            self.assertIn("source_sha=" + SHA + "\n", output.read_text())
            self.assertIn("publish_required=true\n", output.read_text())
            output.unlink()
            checkout.stdout = "private-checkout-response"
            with patch.dict(os.environ, env), patch.object(context, "load_pin", return_value=PIN), patch.object(context.subprocess, "run", return_value=checkout), patch.object(sys, "argv", ["image_context"]), patch.object(sys, "stderr", new_callable=io.StringIO) as error:
                self.assertEqual(context.main(), 1)
            self.assertFalse(output.exists())
            self.assertNotIn("private-checkout-response", error.getvalue())


if __name__ == "__main__":
    unittest.main()
