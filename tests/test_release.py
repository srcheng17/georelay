import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_release as release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.pin = {
            "repository": "https://github.com/teslamate-org/teslamate.git",
            "tag": "v4.3.0",
            "commit": "a" * 40,
        }

    def responses(self, tag="v4.3.0", sha="a" * 40, annotated=True):
        return {
            "/releases/latest": {"tag_name": tag, "draft": False, "prerelease": False},
            "/git/ref/tags/" + tag: {
                "object": {"type": "tag" if annotated else "commit", "sha": "b" * 40 if annotated else sha}
            },
            "/git/tags/" + "b" * 40: {"object": {"type": "commit", "sha": sha}},
        }

    def test_current_and_new_release_preserve_reviewed_pin(self):
        original = copy.deepcopy(self.pin)
        for tag, sha, annotated, status in (
            ("v4.3.0", "a" * 40, True, "current"),
            ("v4.10.0", "c" * 40, False, "update_available"),
        ):
            with self.subTest(tag=tag):
                data = self.responses(tag, sha, annotated)
                result = release.check_release(self.pin, data.__getitem__)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["proposed"]["commit"], sha)
                self.assertEqual(self.pin, original)

    def test_unstable_downgrade_moved_and_malformed_tags_fail(self):
        for tag in ("v4.3.0-rc.1", "main", "v4.2.0", "v04.3.0"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.check_release(self.pin, self.responses(tag).__getitem__)
        for field in ("draft", "prerelease"):
            data = self.responses()
            data["/releases/latest"][field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                release.check_release(self.pin, data.__getitem__)
        with self.assertRaises(ValueError):
            release.check_release(self.pin, self.responses(sha="c" * 40).__getitem__)
        for obj in (
            {"type": "blob", "sha": "b" * 40},
            {"type": "tag", "sha": "b" * 40},
            {"type": "commit", "sha": "not-a-sha"},
        ):
            data = self.responses()
            data["/git/tags/" + "b" * 40]["object"] = obj
            with self.subTest(obj=obj), self.assertRaises(ValueError):
                release.check_release(self.pin, data.__getitem__)

    def test_api_timeout_is_bounded_and_response_size_is_limited(self):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"{}"
        with patch.object(release, "urlopen", return_value=response) as fetch:
            self.assertEqual(release.github_json("/releases/latest"), {})
        self.assertEqual(fetch.call_args.kwargs["timeout"], 20)
        response.__enter__.return_value.read.return_value = b"x" * 1_048_577
        with patch.object(release, "urlopen", return_value=response), self.assertRaises(ValueError):
            release.github_json("/releases/latest")

    def test_failure_cannot_write_proposal_or_leak_error(self):
        with tempfile.TemporaryDirectory() as directory:
            pin = Path(directory) / "upstream.json"
            output = Path(directory) / "proposal.json"
            pin.write_text(json.dumps(self.pin))
            with (
                patch.object(sys, "argv", ["check_release", "--pin", str(pin), "--output", str(output)]),
                patch.object(release, "check_release", side_effect=OSError("private-token-body")),
                patch.object(sys, "stderr", new_callable=io.StringIO) as error,
            ):
                self.assertEqual(release.main(), 1)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(pin.read_text()), self.pin)
            self.assertNotIn("private-token-body", error.getvalue())

            with (
                patch.object(sys, "argv", ["check_release", "--pin", str(pin), "--output", str(pin)]),
                patch.object(release, "check_release") as check,
                patch.object(sys, "stderr", new_callable=io.StringIO),
            ):
                self.assertEqual(release.main(), 1)
                check.assert_not_called()
            self.assertEqual(json.loads(pin.read_text()), self.pin)


if __name__ == "__main__":
    unittest.main()
