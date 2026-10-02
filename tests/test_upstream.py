"""Real git fixtures exercise the same fail-closed preparation as CI, offline."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "prepare_upstream", Path(__file__).resolve().parents[1] / "scripts/prepare_upstream.py"
)
upstream = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upstream)


class PrepareUpstreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        upstream.git(self.source, "init", "--quiet")
        upstream.git(self.source, "config", "user.name", "Fixture")
        upstream.git(self.source, "config", "user.email", "fixture@example.invalid")
        (self.source / "value").write_text("before\n")
        (self.source / "Dockerfile").write_text("FROM scratch\n")
        upstream.git(self.source, "add", ".")
        upstream.git(self.source, "commit", "--quiet", "-m", "fixture")
        upstream.git(self.source, "tag", "v4.3.0")
        self.pin = {
            "repository": upstream.REPOSITORY,
            "tag": "v4.3.0",
            "commit": upstream.git(self.source, "rev-parse", "HEAD"),
        }
        self.pin_path = self.root / "pin.json"
        self.pin_path.write_text(json.dumps(self.pin))
        self.patches = self.root / "patches"
        self.patches.mkdir()
        (self.source / "value").write_text("after\n")
        self.patch_file = self.patches / "001.patch"
        self.patch_file.write_text(upstream.git(self.source, "diff") + "\n")
        upstream.git(self.source, "checkout", "--", "value")
        self.destination = self.root / "destination"
        # Git redirects the official URL to the disposable fixture; no network.
        env = patch.dict(os.environ, {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "url." + self.source.as_uri() + ".insteadOf",
            "GIT_CONFIG_VALUE_0": upstream.REPOSITORY,
        })
        env.start()
        self.addCleanup(env.stop)

    def prepare(self):
        upstream.prepare(self.destination, self.pin_path, self.patches)

    def repin_source(self):
        upstream.git(self.source, "add", ".")
        upstream.git(self.source, "commit", "--quiet", "-m", "fixture change")
        upstream.git(self.source, "tag", "--force", "v4.3.0")
        self.pin["commit"] = upstream.git(self.source, "rev-parse", "HEAD")
        self.pin_path.write_text(json.dumps(self.pin))

    def test_exact_pin_is_patched(self):
        self.prepare()
        self.assertEqual((self.destination / "value").read_text(), "after\n")
        self.assertEqual(upstream.git(self.destination, "rev-parse", "HEAD"), self.pin["commit"])

    def test_unrelated_upstream_changes_and_missing_files_pass_through(self):
        files = {
            "LICENSE": b"Updated upstream license\r\n",
            "NOTICE": b"Updated TeslaMate notice\r\n",
            "TRADEMARK.md": b"Updated upstream trademark policy\r\n",
            "Dockerfile": b"FROM scratch\nLABEL fixture=teslamate\n",
            "elixir/lib/teslamate_web/templates/layout/root.html.heex":
                b"<title>TeslaMate</title>\r\n",
            "elixir/priv/gettext/new_locale/LC_MESSAGES/default.po":
                b'msgid "TeslaMate"\r\nmsgstr "TeslaMate"\r\n',
            "elixir/priv/gettext/default.pot":
                b'msgid "TeslaMate"\r\nmsgstr ""\r\n',
            "elixir/priv/static/images/logo.svg": b"<svg>TeslaMate</svg>\r\n",
            "elixir/priv/static/new-logo.png": b"\x89PNG\r\nfixture\n",
            "elixir/priv/static/favicon.ico": b"\x00\x00\x01\x00fixture",
        }
        for missing in (False, True):
            with self.subTest(missing=missing):
                for relative, content in files.items():
                    path = self.source / relative
                    if missing:
                        path.unlink()
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(content)
                self.repin_source()
                destination = self.root / ("missing" if missing else "changed")
                upstream.prepare(destination, self.pin_path, self.patches)
                for relative, content in files.items():
                    path = destination / relative
                    if missing:
                        self.assertFalse(path.exists())
                    else:
                        self.assertEqual(path.read_bytes(), content)
                self.assertEqual((destination / "value").read_text(), "after\n")
                self.assertEqual(upstream.git(destination, "diff", "--name-only"), "value")
                self.assertEqual(upstream.git(destination, "ls-files", "--others", "--exclude-standard"), "")

    def test_moved_tag_stops_before_checkout_and_patch(self):
        self.pin["commit"] = "0" * 40
        self.pin_path.write_text(json.dumps(self.pin))
        with self.assertRaisesRegex(ValueError, "pinned commit"):
            self.prepare()
        self.assertFalse((self.destination / "value").exists())

    def test_patch_conflict_does_not_mutate_source(self):
        self.patch_file.write_text(self.patch_file.read_text().replace("-before", "-absent"))
        with self.assertRaises(subprocess.CalledProcessError):
            self.prepare()
        self.assertEqual((self.destination / "value").read_text(), "before\n")

    def test_existing_work_is_never_overwritten(self):
        self.destination.mkdir()
        sentinel = self.destination / "keep"
        sentinel.write_text("untouched")
        with self.assertRaisesRegex(ValueError, "empty directory"):
            self.prepare()
        self.assertEqual(sentinel.read_text(), "untouched")

    def test_absent_patch_and_invalid_pin_stop_before_fetch(self):
        self.patch_file.unlink()
        with self.assertRaisesRegex(ValueError, "no upstream patch"):
            self.prepare()
        self.assertFalse(self.destination.exists())
        for key, value in [
            ("tag", "v4.3.0-rc1"),
            ("commit", "main"),
            ("commit", 10**39),
            ("repository", "file:///tmp"),
        ]:
            invalid = dict(self.pin, **{key: value})
            self.pin_path.write_text(json.dumps(invalid))
            with self.assertRaises(ValueError):
                upstream.load_pin(self.pin_path)


if __name__ == "__main__":
    unittest.main()
