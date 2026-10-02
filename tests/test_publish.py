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
import hashlib, json, os, subprocess
from pathlib import Path
import sys
args = sys.argv[1:]
state_path = Path(os.environ["FAKE_STATE"])
state = json.loads(state_path.read_text()) if state_path.exists() else {"commands": [], "tags": {}, "indexes": {}}
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
elif args[:3] == ["buildx", "imagetools", "create"]:
    target = args[args.index("--tag") + 1]
    package = target.split(":")[0].rsplit("/", 1)[-1]
    if target.endswith(":latest"):
        if os.environ.get("FAKE_FAIL_LATEST") == package:
            sys.exit(1)
        assert "--prefer-index=false" in args and "@sha256:" in args[-1], "latest must copy the verified index digest"
        raw = state["indexes"][args[-1]]
        if os.environ.get("FAKE_BAD_LATEST") == package:
            index = json.loads(raw)
            index["manifests"][0]["digest"] = "sha256:" + "f" * 64
            raw = json.dumps(index)
    else:
        if os.environ.get("FAKE_FAIL_VERSION_INDEX") == package:
            sys.exit(1)
        architectures = ["amd64"] if (os.environ.get("FAKE_BAD_INDEX") or os.environ.get("FAKE_BAD_VERSION_INDEX") == package) else ["amd64", "arm64"]
        raw = json.dumps({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json", "manifests": [
            {"platform": {"os": "linux", "architecture": arch}, "digest": "sha256:" + hashlib.sha256((package + arch).encode()).hexdigest()}
            for arch in architectures]})
        digest = "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
        metadata = Path(args[args.index("--metadata-file") + 1])
        metadata.write_text(json.dumps({"containerimage.descriptor": {"digest": digest}}))
        state["indexes"][target.split(":")[0] + "@" + digest] = raw
    state["indexes"][target] = raw
    state_path.write_text(json.dumps(state))
elif args[:3] == ["buildx", "imagetools", "inspect"]:
    if os.environ.get("FAKE_FAIL_LATEST_READ") and args[-1].endswith(":latest"):
        sys.exit(1)
    print(state["indexes"][args[-1]])
    if "teslamate-amap-adapter:" in args[-1] and not args[-1].endswith(":latest"):
        for ref, sha in json.loads(os.environ.get("FAKE_REMOTE_UPDATE", "{}" )).items():
            subprocess.run(["git", "--git-dir", os.environ["FAKE_ORIGIN"], "update-ref", ref, sha], check=True)
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
        self.origin = self.directory / "origin.git"
        self.git("clone", "--quiet", "--bare", str(self.repo), str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
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
            "    latest = os.environ.get('FAKE_LATEST_TAG', pin['tag'])\n"
            "    if path == '/releases/latest':\n"
            "        if os.environ.get('FAKE_LATEST_FAIL'): raise OSError('fake-private-error')\n"
            "        return {'tag_name': latest, 'draft': False, 'prerelease': bool(os.environ.get('FAKE_LATEST_PRERELEASE'))}\n"
            "    if path == '/releases/tags/' + pin['tag']:\n"
            "        return {'tag_name': pin['tag'], 'draft': False, 'prerelease': bool(os.environ.get('FAKE_PRERELEASE'))}\n"
            "    if path == '/git/ref/tags/' + pin['tag']:\n"
            "        return {'object': {'type': 'tag', 'sha': 'a' * 40}}\n"
            "    if path == '/git/tags/' + 'a' * 40:\n"
            "        return {'object': {'type': 'commit', 'sha': '0' * 40 if os.environ.get('FAKE_MOVED_TAG') else pin['commit']}}\n"
            "    assert path == '/git/ref/tags/' + latest\n"
            "    return {'object': {'type': 'commit', 'sha': 'b' * 40}}\n"
            "check_release.github_json = fake_release\n"
        )

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True).strip()

    def newer_remote_commit(self):
        previous = self.git("rev-parse", "HEAD")
        (self.repo / "new-source").write_text("source changed during publication")
        self.git("add", "new-source")
        self.git("commit", "--quiet", "-m", "new source")
        sha = self.git("rev-parse", "HEAD")
        self.git("push", "--quiet", "origin", "HEAD:refs/heads/test-candidate")
        self.git("reset", "--hard", "--quiet", previous)
        return sha

    @staticmethod
    def latest_commands(commands):
        return [command for command in commands if command[:3] == ["buildx", "imagetools", "create"] and any(arg.endswith(":latest") for arg in command)]

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
            "FAKE_ORIGIN": str(self.origin),
            "PYTHONPATH": str(self.pythonpath),
            **overrides,
        }
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/publish_images.sh"), str(self.artifacts)],
            cwd=self.repo, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotIn("fake-test-only", result.stdout + result.stderr)
        self.assertNotIn("fake-private-error", result.stdout + result.stderr)
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
        self.assertEqual(len(indexes), 4)
        self.assertTrue(loads[0] < pushes[0] < pushes[1] < loads[1] < pushes[2] < pushes[3] < indexes[0])
        version_reads = [i for i, command in enumerate(commands) if command[:3] == ["buildx", "imagetools", "inspect"] and not command[-1].endswith(":latest")]
        self.assertTrue(indexes[0] < version_reads[0] < indexes[1] < version_reads[1] < indexes[2] < indexes[3])
        self.assertTrue(all("stable" not in str(command) for command in commands))
        state = json.loads(self.state.read_text())
        version = json.loads((self.repo / "upstream.json").read_text())["tag"] + "-amap-" + self.git("rev-parse", "HEAD")
        for package in ("ghcr.io/example/teslamate-amap", "ghcr.io/example/teslamate-amap-adapter"):
            self.assertEqual(state["indexes"][package + ":latest"], state["indexes"][package + ":" + version])

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

    def test_either_version_index_failure_prevents_any_latest_promotion(self):
        for package in ("teslamate-amap", "teslamate-amap-adapter"):
            for failure in ("FAKE_FAIL_VERSION_INDEX", "FAKE_BAD_VERSION_INDEX"):
                with self.subTest(package=package, failure=failure):
                    result, commands = self.publish(**{failure: package})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.latest_commands(commands), [])

    def test_latest_copy_or_content_failure_is_not_reported_as_success(self):
        for package in ("teslamate-amap", "teslamate-amap-adapter"):
            for failure in ("FAKE_FAIL_LATEST", "FAKE_BAD_LATEST"):
                with self.subTest(package=package, failure=failure):
                    result, commands = self.publish(**{failure: package})
                    self.assertNotEqual(result.returncode, 0)
                    latest = self.latest_commands(commands)
                    self.assertEqual(len(latest), 1 if package == "teslamate-amap" else 2)
        result, commands = self.publish(FAKE_FAIL_LATEST_READ="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.latest_commands(commands)), 1)

    def test_newer_official_release_skips_latest_but_preserves_version_publication(self):
        result, commands = self.publish(FAKE_LATEST_TAG="v999.0.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("newer official stable release", result.stdout)
        self.assertEqual(self.latest_commands(commands), [])
        self.assertEqual(len([command for command in commands if command[:3] == ["buildx", "imagetools", "create"]]), 2)

    def test_release_api_failure_or_invalid_report_prevents_latest(self):
        for failure in ("FAKE_LATEST_FAIL", "FAKE_LATEST_PRERELEASE"):
            with self.subTest(failure=failure):
                result, commands = self.publish(**{failure: "1"})
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.latest_commands(commands), [])

    def test_obsolete_main_source_cannot_overwrite_latest(self):
        newer = self.newer_remote_commit()
        self.git("push", "--quiet", "origin", newer + ":refs/heads/main")
        result, commands = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("source branch has changed", result.stdout)
        self.assertEqual(self.latest_commands(commands), [])

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
        self.git("push", "--quiet", "origin", "HEAD:refs/heads/upstream/v999.0.0")
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

    def test_upstream_source_or_parent_changed_during_publication_skips_latest(self):
        pin = json.loads((self.repo / "upstream.json").read_text())
        pin["tag"] = "v999.0.0"
        (self.repo / "upstream.json").write_text(json.dumps(pin))
        self.git("add", "upstream.json")
        self.git("commit", "--quiet", "-m", "new stable pin")
        self.git("push", "--quiet", "origin", "HEAD:refs/heads/upstream/v999.0.0")
        newer = self.newer_remote_commit()
        dispatch = {"GITHUB_EVENT_NAME": "workflow_dispatch", "PUBLISH_REQUESTED": "true", "GITHUB_REF": "refs/heads/upstream/v999.0.0"}
        for ref, reason in (
            ("refs/heads/upstream/v999.0.0", "source branch has changed"),
            ("refs/heads/main", "no longer has current main as its parent"),
        ):
            with self.subTest(ref=ref):
                result, commands = self.publish(**dispatch, FAKE_REMOTE_UPDATE=json.dumps({ref: newer}))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(reason, result.stdout)
                self.assertEqual(self.latest_commands(commands), [])
                # Restore both remote refs for the next case's strict version preflight.
                self.git("push", "--quiet", "origin", "+HEAD:refs/heads/upstream/v999.0.0", "+HEAD^:refs/heads/main")

    def test_upstream_already_obsolete_at_start_keeps_strict_preflight(self):
        pin = json.loads((self.repo / "upstream.json").read_text())
        pin["tag"] = "v999.0.0"
        (self.repo / "upstream.json").write_text(json.dumps(pin))
        self.git("add", "upstream.json")
        self.git("commit", "--quiet", "-m", "new stable pin")
        self.git("push", "--quiet", "origin", "HEAD:refs/heads/upstream/v999.0.0")
        newer = self.newer_remote_commit()
        self.git("push", "--quiet", "origin", newer + ":refs/heads/main")
        result, commands = self.publish(GITHUB_EVENT_NAME="workflow_dispatch", PUBLISH_REQUESTED="true", GITHUB_REF="refs/heads/upstream/v999.0.0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, [])


if __name__ == "__main__":
    unittest.main()
