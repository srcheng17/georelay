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
        for name in upstream.LEGAL_FILES:
            (self.source / name).write_bytes((upstream.ROOT / name).read_bytes())
        for name in (*upstream.BRANDED_ASSETS, "robots.txt"):
            asset = self.source / "elixir/priv/static" / name
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_text("fixture asset\n")
        layout = self.source / "elixir/lib/teslamate_web/templates/layout/root.html.heex"
        layout.parent.mkdir(parents=True)
        layout.write_text(
            '<.live_title suffix=" · GeoRelay" /><strong>GeoRelay</strong>\n'
            'https://github.com/srcheng17/georelay\n' + upstream.DISCLAIMER + '\n'
        )
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
        for name in upstream.LEGAL_FILES:
            self.assertEqual(
                (self.destination / name).read_bytes(), (upstream.ROOT / name).read_bytes()
            )
        self.assertEqual(
            (self.destination / "MODIFICATIONS.md").read_bytes(),
            (upstream.ROOT / "MODIFICATIONS.md").read_bytes(),
        )
        self.assertIn(
            "COPY --chmod=444 MODIFICATIONS.md TRADEMARK.md /usr/share/doc/teslamate/",
            (self.destination / "Dockerfile").read_text(),
        )
        static = self.destination / "elixir/priv/static"
        self.assertEqual((static / "favicon.svg").read_bytes(), (upstream.ROOT / "branding/favicon.svg").read_bytes())
        self.assertEqual(
            {p.relative_to(static).as_posix() for p in static.rglob("*") if p.is_file()},
            {"favicon.svg", "robots.txt"},
        )

    def test_changed_or_missing_legal_text_stops_before_patch(self):
        for name in upstream.LEGAL_FILES:
            for missing in (False, True):
                with self.subTest(name=name, missing=missing):
                    upstream.git(self.source, "reset", "--hard", self.pin["commit"])
                    legal = self.source / name
                    if missing:
                        legal.unlink()
                    else:
                        # A newline-only change must not be normalized away.
                        legal.write_bytes(legal.read_bytes().replace(b"\n", b"\r\n"))
                    upstream.git(self.source, "add", ".")
                    upstream.git(self.source, "commit", "--quiet", "-m", "legal change")
                    upstream.git(self.source, "tag", "--force", "v4.3.0")
                    pin = dict(self.pin, commit=upstream.git(self.source, "rev-parse", "HEAD"))
                    self.pin_path.write_text(json.dumps(pin))
                    destination = self.root / (name + ("-missing" if missing else "-changed"))
                    with self.assertRaisesRegex(ValueError, name + ".*manual review"):
                        upstream.prepare(destination, self.pin_path, self.patches)
                    self.assertEqual((destination / "value").read_text(), "before\n")
                    self.assertEqual((destination / "Dockerfile").read_text(), "FROM scratch\n")
                    self.assertFalse((destination / "MODIFICATIONS.md").exists())
                    self.assertEqual(upstream.git(destination, "status", "--porcelain"), "")

    def test_unreviewed_static_asset_stops_before_patch(self):
        (self.source / "elixir/priv/static/new-logo.svg").write_text("unreviewed")
        self.repin_source()
        with self.assertRaisesRegex(ValueError, "manual branding review"):
            self.prepare()
        self.assertEqual((self.destination / "value").read_text(), "before\n")
        self.assertEqual(upstream.git(self.destination, "status", "--porcelain"), "")

    def test_unrelated_files_names_and_missing_old_assets_are_preserved(self):
        unchanged = {
            "elixir/priv/static/diagnostics.js": b"const module = 'TeslaMate.HTTP';\r\n",
            "elixir/lib/teslamate_web/templates/internal.html.heex":
                b"<%= TeslaMate.HTTP.get(:teslamate) %>\n",
            "elixir/lib/teslamate_web/templates/layout/root.html.heex":
                b'<.live_title suffix={" \xc2\xb7 GeoRelay"} /><strong class="app">GeoRelay</strong>\n',
            "elixir/priv/gettext/new_locale/LC_MESSAGES/default.po":
                b'# TeslaMate copyright and path references remain\r\n'
                b'msgid "Welcome to TeslaMate"\r\nmsgstr "TeslaMate"\r\n',
        }
        for relative, content in unchanged.items():
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        for name in ("images/logo_icon.svg", "favicon-16x16.png"):
            (self.source / "elixir/priv/static" / name).unlink()
        # New catalogs need not contain unrelated or every known message.
        message = sorted(upstream.BRAND_MESSAGES)[0]
        for relative in ("default.pot", "new_locale/LC_MESSAGES/extra.po"):
            path = self.source / "elixir/priv/gettext" / relative
            path.write_text('msgid ' + json.dumps(message) + '\nmsgstr ""\n')
        self.repin_source()
        self.prepare()
        for relative, content in unchanged.items():
            self.assertEqual((self.destination / relative).read_bytes(), content)
        for relative in ("default.pot", "new_locale/LC_MESSAGES/extra.po"):
            catalog = self.destination / "elixir/priv/gettext" / relative
            self.assertIn(message.replace("TeslaMate", "GeoRelay"), catalog.read_text())
        static = self.destination / "elixir/priv/static"
        self.assertEqual((static / "favicon.svg").read_bytes(), (upstream.ROOT / "branding/favicon.svg").read_bytes())
        self.assertTrue(all(not (static / name).exists() for name in upstream.BRANDED_ASSETS))

    def test_catalog_changes_only_known_decoded_singular_messages(self):
        catalog = self.root / "wrapped.po"
        quote = lambda value: json.dumps(value, ensure_ascii=False)
        untouched = (
            '# TeslaMate.HTTP and lib/teslamate references stay intact\r\n'
            'msgid "TeslaMate.HTTP"\r\nmsgstr "TeslaMate.HTTP"\r\n\r\n'
            'msgid "© the TeslaMate contributors"\r\n'
            'msgstr "© the TeslaMate contributors"\r\n\r\n'
            'msgid ' + quote(upstream.DISCLAIMER) + '\r\nmsgstr ""\r\n\r\n'
            'msgid "Welcome to TeslaMate"\r\nmsgstr "TeslaMate"\r\n\r\n'
            '#~ msgid ' + quote(sorted(upstream.BRAND_MESSAGES)[0]) + '\r\n'
            '#~ msgstr "Old TeslaMate translation"\r\n\r\n'
        )
        original = expected = untouched
        for number, (message, translation) in enumerate(zip(
            sorted(upstream.BRAND_MESSAGES),
            ['TeslaMate-Daten "Tesla API"\n%{token} %{url}', 'TeslaMate로', 'TeslaMate会使用\\路径\u2028继续\u0085结束', ''],
        )):
            prefix = (
                '#: lib/teslamate_web/template.html.heex:1\r\n'
                '#, fuzzy, elixir-autogen, elixir-format\r\n'
                'msgctxt ' + quote('context-' + str(number)) + '\r\n'
            )
            before, after = message.split("TeslaMate")
            msgid = 'msgid\t""\r\n  ' + quote(before + "Tesla") + '\r\n' + quote("Mate" + after)
            if translation:
                before, after = translation.split("TeslaMate")
                msgstr = '  msgstr\t""\r\n  ' + quote(before + "Tesla") + '\r\n' + quote("Mate" + after)
            else:
                msgstr = 'msgstr ""'
            original += prefix + msgid + '\r\n' + msgstr + '\r\n\r\n'
            expected += (
                prefix + 'msgid ' + quote(message.replace("TeslaMate", "GeoRelay")) + '\r\n'
                + 'msgstr ' + quote(translation.replace("TeslaMate", "GeoRelay")) + '\r\n\r\n'
            )
        catalog.write_bytes(original.encode())
        upstream.brand_catalog(catalog)
        self.assertEqual(catalog.read_bytes(), expected.encode())
        upstream.brand_catalog(catalog)
        self.assertEqual(catalog.read_bytes(), expected.encode())

    def test_known_branding_message_with_plural_shape_requires_review(self):
        catalog = self.root / "plural.po"
        message = sorted(upstream.BRAND_MESSAGES)[0]
        original = (
            'msgid ' + json.dumps(message) + '\nmsgid_plural "TeslaMate plural"\n'
            'msgstr[0] "TeslaMate"\nmsgstr[1] "TeslaMate"\n'
        ).encode()
        catalog.write_bytes(original)
        with self.assertRaisesRegex(ValueError, "not singular.*manual branding review"):
            upstream.brand_catalog(catalog)
        self.assertEqual(catalog.read_bytes(), original)

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
