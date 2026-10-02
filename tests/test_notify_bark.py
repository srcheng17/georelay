"""Bark dry-run and loopback receiver checks; no real endpoint or credentials."""

import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import notify_bark as bark


REPORT = {"status": "failed", "notify": True, "notification": {
    "repository": "fixture/georelay", "run_id": 10, "attempt": 1, "source_pr": 7,
    "sha": "a" * 40, "run_url": "https://github.com/fixture/georelay/actions/runs/10",
    "stage": "beta_validation", "failed_jobs": ["build-arm64"], "conclusion": "failure",
}}


@contextlib.contextmanager
def receiver(responses):
    captured = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            captured.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            code, body, headers = responses[min(len(captured) - 1, len(responses) - 1)]
            self.send_response(code)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port) + "/fixture-device-key", captured
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class BarkTests(unittest.TestCase):
    def test_dry_run_zero_network_and_success_actual_local_receiver(self):
        with receiver([(200, b'{"code":200}', {})]) as (url, captured):
            result = bark.send(REPORT, url, dry_run=True, allow_local_http=True)
            self.assertEqual(result, {"status": "dry_run", "attempts": 0})
            self.assertEqual(captured, [])
            result = bark.send(REPORT, url, allow_local_http=True)
            self.assertEqual(result, {"status": "sent", "attempts": 1, "http_status": 200})
            self.assertEqual(len(captured), 1)
            self.assertIn("PR: #7", captured[0]["body"])
            self.assertIn("https://github.com/fixture/georelay/pull/7", captured[0]["body"])
            self.assertIn("build-arm64", captured[0]["body"])
            self.assertEqual(captured[0]["idempotency_key"], "georelay/fixture/georelay/10/1/beta_validation")
            self.assertNotIn("fixture-device-key", json.dumps(result))

    def test_missing_secret_and_structural_url_rejection(self):
        self.assertEqual(bark.send(REPORT, "")["status"], "not_configured")
        for url in ("http://example.invalid/key", "https://user:pass@example.invalid/key", "https://example.invalid/#key",
                    "https://example.invalid:99999/key", "https://example.invalid/key\n", "http://192.0.2.1/key"):
            with self.subTest(url=url):
                self.assertEqual(bark.send(REPORT, url, dry_run=True, allow_local_http=True)["status"], "configuration_error")
        for attempts in (0, 6):
            self.assertEqual(bark.send(REPORT, "https://fixture.invalid/key", attempts=attempts)["status"], "configuration_error")

    def test_bounded_explicit_http_retries_keep_same_key_and_validate_bark_code(self):
        with receiver([(429, b'private-response', {}), (500, b'private-response', {}), (200, b'{"code":200}', {})]) as (url, captured):
            waits = []
            result = bark.send(REPORT, url, allow_local_http=True, sleep=waits.append)
            self.assertEqual(result["status"], "sent")
            self.assertEqual(result["attempts"], 3)
            self.assertEqual(waits, [1, 2])
            self.assertEqual(len({item["idempotency_key"] for item in captured}), 1)
        with receiver([(503, b'private-response', {})]) as (url, captured):
            result = bark.send(REPORT, url, allow_local_http=True, sleep=lambda _: None)
            self.assertEqual(result["status"], "retry_exhausted")
            self.assertEqual(len(captured), 3)
        for body in (b'{"code":400,"message":"private-response"}', b'invalid private-response'):
            with receiver([(200, body, {})]) as (url, captured):
                result = bark.send(REPORT, url, allow_local_http=True)
                self.assertEqual(result["status"], "verification_failed")
                self.assertEqual(len(captured), 1)
                self.assertNotIn("private-response", json.dumps(result))

    def test_rejected_or_ambiguous_transport_not_blindly_retried_or_redirected(self):
        with receiver([(401, b'private-response', {})]) as (url, captured):
            self.assertEqual(bark.send(REPORT, url, allow_local_http=True)["status"], "rejected")
            self.assertEqual(len(captured), 1)
        with receiver([(302, b'', {"Location": "https://untrusted.invalid/device-key"})]) as (url, captured):
            self.assertEqual(bark.send(REPORT, url, allow_local_http=True)["status"], "rejected")
            self.assertEqual(len(captured), 1)
        for error in (TimeoutError("private-response"), URLError("private-response")):
            with patch.object(bark, "build_opener") as opener:
                opener.return_value.open.side_effect = error
                waits = []
                result = bark.send(REPORT, "https://fixture.invalid/device-key", sleep=waits.append)
                self.assertEqual(result["status"], "uncertain")
                self.assertEqual(opener.return_value.open.call_count, 3)
                self.assertEqual(waits, [1, 2])
                self.assertNotIn("private-response", json.dumps(result))

    def test_payload_rejects_success_external_link_or_untrusted_job_text(self):
        for malformed in ([], None, "private-response", {"status": "failed", "notify": True, "notification": []}):
            self.assertEqual(bark.send(malformed, "https://fixture.invalid/key", dry_run=True)["status"], "configuration_error")
        for change in (lambda r: r.update(status="success"), lambda r: r.update(notify=False),
                       lambda r: r["notification"].update(run_url="https://private.invalid/raw-log"),
                       lambda r: r["notification"].update(failed_jobs=["private-response"]),
                       lambda r: r["notification"].update(stage="private-response")):
            report = json.loads(json.dumps(REPORT))
            change(report)
            self.assertEqual(bark.send(report, "https://fixture.invalid/key", dry_run=True)["status"], "configuration_error")
        report = json.loads(json.dumps(REPORT))
        report["notification"]["stage"] = "main_dispatch"
        report["merged_sha"] = "b" * 40
        self.assertIn("正式发布触发未确认", bark.payload(report)["body"])

    def test_cli_result_exposes_no_endpoint_secret_payload_or_raw_error(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            report.write_text(json.dumps(REPORT))
            command = [sys.executable, str(Path(bark.__file__)), "--report", str(report), "--dry-run"]
            result = subprocess.run(command, capture_output=True, text=True,
                                    env=dict(os.environ, BARK_URL="https://fixture.invalid/private-device-key"), check=False)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "dry_run")
            self.assertNotIn("private-device-key", result.stdout + result.stderr)
            self.assertNotIn(REPORT["notification"]["sha"], result.stdout + result.stderr)
            for malformed in ('invalid private-response', '[]', '{"status":"failed","notify":true,"notification":[]}'):
                report.write_text(malformed)
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("private-response", result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
