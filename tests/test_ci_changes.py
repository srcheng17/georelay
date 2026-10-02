"""Real Git transitions and the workflow's actual required-check shell."""

import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_changes


class ChangesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "--quiet")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.write("README.md")
        self.write("docs/guide.md")
        self.write("adapter/server.py")
        self.base = self.commit()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, text=True, capture_output=True).stdout.strip()

    def write(self, path):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture\n", encoding="utf-8")

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", "fixture")
        return self.git("rev-parse", "HEAD")

    def required(self, head, event_name="push", event=None):
        if event is None:
            event = {"before": self.base} if event_name == "push" else {"pull_request": {"base": {"sha": self.base}}}
        return ci_changes.images_required(event_name, event, head, self.root)

    def test_metadata_diff_on_push_and_pr_skips_images(self):
        for path in ("README.zh-CN.md", "AGENTS.md", "paseo.json", ".trellis/tasks/fixture/prd.md", ".agents/skills/fixture/SKILL.md", ".codex/agents/fixture.toml"):
            self.write(path)
        self.git("mv", "docs/guide.md", "docs/renamed guide.md")
        head = self.commit()
        self.assertFalse(self.required(head))
        self.assertFalse(self.required(head, "pull_request"))

    def test_runtime_mixed_unknown_and_deleted_paths_build_images(self):
        for paths in (("adapter/new.py",), ("docs/new.md", "upstream.json"), ("unknown",), ("tests/new.py",), ("scripts/new.sh",)):
            with self.subTest(paths=paths):
                self.git("reset", "--hard", self.base)
                for path in paths:
                    self.write(path)
                self.assertTrue(self.required(self.commit()))
        self.git("reset", "--hard", self.base)
        self.git("rm", "adapter/server.py")
        self.assertTrue(self.required(self.commit()))

    def test_rename_cannot_hide_runtime_and_doc_deletion_is_lightweight(self):
        self.git("mv", "adapter/server.py", "docs/server.txt")
        self.assertTrue(self.required(self.commit()))
        self.git("reset", "--hard", self.base)
        self.git("rm", "docs/guide.md")
        self.assertFalse(self.required(self.commit()))

    def test_missing_or_invalid_base_empty_diff_and_dispatch_build_images(self):
        for event in ({}, {"before": "0" * 40}, {"before": "a" * 40}, {"before": "--invalid"}, []):
            with self.subTest(event=event):
                self.assertTrue(self.required(self.base, event=event))
        self.assertTrue(self.required(self.base))
        self.assertTrue(self.required("b" * 40))
        with patch.object(ci_changes.subprocess, "run") as run:
            self.assertTrue(self.required(self.base, "workflow_dispatch", {"before": self.base}))
            run.assert_not_called()

    def test_cli_writes_an_explicit_decision_and_invalid_event_is_conservative(self):
        self.write("docs/new.md")
        head = self.commit()
        event, output = self.root / "event.json", self.root / "output"
        event.write_text(json.dumps({"before": self.base}))
        env = {"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": str(event), "GITHUB_SHA": head, "GITHUB_OUTPUT": str(output)}
        # The CLI uses the same real Git diff but defaults to this module's checkout.
        detect = ci_changes.images_required
        with patch.dict(os.environ, env), patch.object(sys, "stdout", new_callable=io.StringIO):
            with patch.object(ci_changes, "images_required", wraps=lambda name, data, sha: detect(name, data, sha, self.root)):
                ci_changes.main()
        self.assertEqual(output.read_text(), "image_required=false\n")
        event.write_text("invalid json")
        with patch.dict(os.environ, env), patch.object(sys, "stdout", new_callable=io.StringIO):
            ci_changes.main()
        self.assertEqual(output.read_text(), "image_required=false\nimage_required=true\n")

    def test_actual_verify_shell_accepts_only_successful_selected_validation(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        block = re.search(r"(?s)      - name: Require checks and the selected image validation\n.*?        run: \|\n(.*?)\n\n  publish:", workflow)
        self.assertIsNotNone(block)
        script = textwrap.dedent(block[1])
        for checks in ("success", "failure", "cancelled", "skipped", ""):
            for required in ("true", "false", "", "invalid"):
                for build in ("success", "failure", "cancelled", "skipped", ""):
                    with self.subTest(checks=checks, required=required, build=build):
                        result = subprocess.run(["bash", "-e", "-c", script], env=dict(os.environ, CHECKS_RESULT=checks, IMAGE_REQUIRED=required, BUILD_RESULT=build), capture_output=True)
                        self.assertEqual(result.returncode == 0, (checks, required, build) in (("success", "true", "success"), ("success", "false", "skipped")))


if __name__ == "__main__":
    unittest.main()
