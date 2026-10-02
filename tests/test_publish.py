"""Exercise the real publish shell with a fake registry, without credentials/network."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAKE_DOCKER = '''#!/usr/bin/env python3
import json, os
from pathlib import Path
import sys
args = sys.argv[1:]
state_path = Path(os.environ["FAKE_STATE"])
state = json.loads(state_path.read_text()) if state_path.exists() else {"commands": [], "tags": {}}
state["commands"].append(args)
if args[0] == "load":
    state["architecture"] = Path(args[-1]).stem.removeprefix("checked-images-")
elif args[0] == "tag":
    state["tags"][args[-1]] = state["architecture"]
state_path.write_text(json.dumps(state))
if args[0] == "login":
    sys.stdin.read()
elif args[:2] == ["image", "inspect"] and "--format" in args:
    print("linux/" + os.environ["IMAGE_ARCHITECTURE"])
elif args[:2] == ["image", "inspect"]:
    labels = {"org.opencontainers.image." + key: value for key, value in {
        "source": os.environ["IMAGE_SOURCE"], "revision": os.environ["GITHUB_SHA"],
        "version": os.environ["IMAGE_VERSION"]}.items()}
    if os.environ.get("FAKE_BAD_LABEL"):
        labels["org.opencontainers.image.revision"] = "wrong"
    print(json.dumps([{"Os": "linux", "Architecture": state["architecture"], "Config": {"Labels": labels}}]))
elif args[0] == "run":
    if os.environ.get("FAKE_UID_FAIL"):
        sys.exit(1)
    print(os.environ.get("FAKE_UID_OUTPUT", "10001"))
elif args[0] == "push":
    assert args[-1].endswith("-" + state["tags"][args[-1]]), "checked image was overwritten before push"
    if args[-1].endswith("-" + os.environ.get("FAKE_FAIL_PUSH", "none")):
        sys.exit(1)
elif args[:3] == ["buildx", "imagetools", "inspect"]:
    architectures = ["amd64"] if os.environ.get("FAKE_BAD_INDEX") else ["amd64", "arm64"]
    print(json.dumps({"manifests": [{"platform": {"os": "linux", "architecture": arch}} for arch in architectures]}))
'''


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.repo = self.directory / "repo"
        self.repo.mkdir()
        self.git("init", "--quiet", "-b", "main")
        self.git("config", "user.email", "isolated-test@example.invalid")
        self.git("config", "user.name", "Publication test")
        (self.repo / "upstream.json").write_text((ROOT / "upstream.json").read_text())
        self.git("add", "upstream.json")
        self.git("commit", "--quiet", "-m", "test base")
        origin = self.directory / "origin.git"
        self.git("clone", "--quiet", "--bare", str(self.repo), str(origin))
        self.git("remote", "add", "origin", str(origin))
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        docker = self.bin / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        self.artifacts = self.directory / "artifacts"
        self.artifacts.mkdir()
        for architecture in ("amd64", "arm64"):
            (self.artifacts / f"checked-images-{architecture}.tar").write_bytes(b"checked artifact")
        self.state = self.directory / "state.json"
        # Patch the existing HTTP helper inside child Python processes, never use the network.
        self.pythonpath = self.directory / "pythonpath"
        self.pythonpath.mkdir()
        (self.pythonpath / "sitecustomize.py").write_text(
            f"import sys, os, json\nfrom pathlib import Path\nsys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
            "import check_release\n"
            "def fake_release(path):\n"
            "    pin = json.loads(Path('upstream.json').read_text())\n"
            "    if path == '/releases/tags/' + pin['tag']:\n"
            "        return {'tag_name': pin['tag'], 'draft': False, 'prerelease': bool(os.environ.get('FAKE_PRERELEASE'))}\n"
            "    if path == '/git/ref/tags/' + pin['tag']:\n"
            "        return {'object': {'type': 'tag', 'sha': 'a' * 40}}\n"
            "    assert path == '/git/tags/' + 'a' * 40\n"
            "    return {'object': {'type': 'commit', 'sha': '0' * 40 if os.environ.get('FAKE_MOVED_TAG') else pin['commit']}}\n"
            "check_release.github_json = fake_release\n"
        )

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True).strip()

    def publish(self, **overrides):
        self.state.unlink(missing_ok=True)
        environment = {
            **os.environ,
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "GITHUB_SHA": self.git("rev-parse", "HEAD"),
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REPOSITORY": "example/teslamate",
            "GITHUB_ACTOR": "isolated-test",
            "GHCR_TOKEN": "fake-test-only",
            "GITHUB_STEP_SUMMARY": str(self.directory / "summary.md"),
            "FAKE_STATE": str(self.state),
            "PYTHONPATH": str(self.pythonpath),
            **overrides,
        }
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/publish_images.sh"), str(self.artifacts)],
            cwd=self.repo, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotIn("fake-test-only", result.stdout + result.stderr)
        commands = json.loads(self.state.read_text())["commands"] if self.state.exists() else []
        return result, commands

    def test_checked_architectures_are_pushed_before_next_load(self):
        result, commands = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        loads = [i for i, command in enumerate(commands) if command[0] == "load"]
        pushes = [i for i, command in enumerate(commands) if command[0] == "push"]
        indexes = [i for i, command in enumerate(commands) if command[:3] == ["buildx", "imagetools", "create"]]
        self.assertEqual(len(loads), 2)
        self.assertEqual(len(pushes), 4)
        self.assertEqual(len(indexes), 2)
        self.assertTrue(loads[0] < pushes[0] < pushes[1] < loads[1] < pushes[2] < pushes[3] < indexes[0])
        self.assertTrue(all("latest" not in str(command) and "stable" not in str(command) for command in commands))

    def test_publication_failure_stops_before_indexes(self):
        for overrides in ({"FAKE_FAIL_PUSH": "arm64"}, {"FAKE_BAD_LABEL": "1"}):
            with self.subTest(overrides=overrides):
                result, commands = self.publish(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(any(command[:3] == ["buildx", "imagetools", "create"] for command in commands))
        result, _ = self.publish(FAKE_BAD_INDEX="1")
        self.assertNotEqual(result.returncode, 0)
        (self.artifacts / "checked-images-arm64.tar").unlink()
        result, commands = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])

    def test_reject_unrequested_or_untrusted_publication(self):
        for overrides in (
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_EVENT_NAME": "workflow_dispatch", "PUBLISH_REQUESTED": "false"},
            {"GITHUB_EVENT_NAME": "workflow_dispatch", "PUBLISH_REQUESTED": "true", "GITHUB_REF": "refs/heads/feature"},
            {"GITHUB_SHA": "0" * 40},
            {"FAKE_PRERELEASE": "1"},
        ):
            with self.subTest(overrides=overrides):
                result, commands = self.publish(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(commands, [])

    def test_tag_moved_during_build_is_rejected_before_login(self):
        result, commands = self.publish(FAKE_MOVED_TAG="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])

    def test_actual_ci_nonroot_check_rejects_failed_empty_or_invalid_uid(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        loop = re.search(
            r"(?ms)^          for image in amap-adapter teslamate-amap; do\n.*?^          done$", workflow
        ).group(0)
        for overrides, expected in (
            ({"FAKE_UID_OUTPUT": "10001"}, 0),
            ({"FAKE_UID_OUTPUT": "0"}, 1),
            ({"FAKE_UID_OUTPUT": ""}, 1),
            ({"FAKE_UID_OUTPUT": "root"}, 1),
            ({"FAKE_UID_FAIL": "1"}, 1),
        ):
            with self.subTest(overrides=overrides):
                environment = {
                    **os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "FAKE_STATE": str(self.state), "IMAGE_ARCHITECTURE": "amd64", **overrides,
                }
                result = subprocess.run(
                    ["bash", "-c", "set -euo pipefail\n" + textwrap.dedent(loop)],
                    cwd=self.repo, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_automatic_branch_is_pin_only_and_matches_tag(self):
        pin = json.loads((self.repo / "upstream.json").read_text())
        pin["tag"] = "v999.0.0"
        (self.repo / "upstream.json").write_text(json.dumps(pin))
        self.git("add", "upstream.json")
        self.git("commit", "--quiet", "-m", "new stable pin")
        dispatch = {"GITHUB_EVENT_NAME": "workflow_dispatch", "PUBLISH_REQUESTED": "true", "GITHUB_REF": "refs/heads/upstream/v999.0.0"}
        result, _ = self.publish(**dispatch)
        self.assertEqual(result.returncode, 0, result.stderr)
        result, commands = self.publish(**{**dispatch, "GITHUB_REF": "refs/heads/upstream/v999.0.1"})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])
        (self.repo / "changed-patch").write_text("unreviewed change")
        self.git("add", "changed-patch")
        self.git("commit", "--amend", "--quiet", "-m", "forbidden patch change")
        result, commands = self.publish(**dispatch)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])


if __name__ == "__main__":
    unittest.main()
