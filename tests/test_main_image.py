"""Run the real smoke shell with offline Docker and HTTP fixtures."""

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
from http.server import HTTPServer
import importlib.util
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOGIN_HTML = ('<html><title>TeslaMate</title><form id="tokens" phx-submit="sign_in">'
              '<input name="tokens[access]"><input name="tokens[refresh]"></form></html>')
FAKE_DOCKER = '''#!/usr/bin/env python3
import json, os, subprocess, sys, time
from pathlib import Path
args = sys.argv[1:]
path = Path(os.environ["FAKE_STATE"])
state = json.loads(path.read_text()) if path.exists() else {"commands": [], "containers": [], "networks": []}
state["commands"].append(args)
mode = os.environ["FAKE_MODE"]
if args[:2] == ["network", "create"]:
    state["networks"].append(args[-1])
elif args[:2] == ["network", "rm"]:
    if mode == "cleanup-error":
        print("fake-private-error", file=sys.stderr)
        path.write_text(json.dumps(state))
        sys.exit(1)
    state["networks"].remove(args[-1])
elif args[0] == "rm":
    if mode == "container-cleanup-error":
        path.write_text(json.dumps(state))
        sys.exit(1)
    state["containers"] = [name for name in state["containers"] if name not in args[2:]]
elif args[0] == "run":
    state["containers"].append(args[args.index("--name") + 1])
path.write_text(json.dumps(state))
if (mode == "block-inspect" and args[0] == "inspect"
    or mode == "block-sql" and args[0] == "exec"
    or mode == "block-probe" and "-c" in args
    or mode == "block-rpc" and "rpc" in args):
    Path(os.environ["FAKE_READY"]).write_text(str(os.getpid()) + " " + str(os.getppid()))
    time.sleep(30)
if args[:2] == ["container", "ls"]:
    print("\\n".join(state["containers"]))
elif args[0] == "inspect":
    component = args[-1].rsplit("-", 1)[-1]
    print("exited 17" if mode == component + "-exit" else "running 0")
elif args[0] == "run":
    if mode == "start-error" and args[-1] == "app:checked":
        print("fake-private-error", file=sys.stderr)
        sys.exit(1)
    if "-c" in args:
        # Execute the actual embedded probe: fixed offline response, no Docker/network.
        setup = ''' + repr('''
import io, os
from pathlib import Path
from email.message import Message
from urllib.error import HTTPError, URLError
import urllib.request
def fake_open(request, timeout):
    url = request if isinstance(request, str) else request.full_url
    assert url in ("http://app:4000/sign_in", "http://stub:8080/health") and timeout == 2
    if url == "http://app:4000/sign_in":
        assert request.get_header("Accept") == "text/html"
    if os.environ["FAKE_MODE"] == "timeout":
        raise URLError("fake-private-error")
    if os.environ["FAKE_MODE"] == "http-error":
        raise HTTPError(url, 500, "fake-private-error", None, None)
    body = {
        "http://app:4000/sign_in": Path(os.environ["FAKE_BODY_FILE"]).read_bytes(),
        "http://stub:8080/health": b'{"ok": true}',
    }[url]
    response = io.BytesIO(body)
    response.status = 503 if os.environ["FAKE_MODE"] == "http-status" else 200
    response.headers = Message()
    response.headers["Content-Type"] = os.environ.get("FAKE_CONTENT_TYPE", "text/html; charset=utf-8" if url.endswith("sign_in") else "application/json")
    response.geturl = lambda: os.environ.get("FAKE_REDIRECT", url)
    return response
urllib.request.urlopen = fake_open
''') + '''
        result = subprocess.run([sys.executable, "-c", setup + args[-1]]).returncode
        state["containers"].remove(args[args.index("--name") + 1])
        path.write_text(json.dumps(state))
        sys.exit(result)
    print("fixture-container")
elif args[0] == "exec":
    if "rpc" in args:
        if mode == "rpc-error":
            print("fake-private-error", file=sys.stderr)
            sys.exit(1)
        print({"rpc-marker-missing": "unrelated", "rpc-marker-spoof": '\"GEORELAY_RUNTIME_LOCATIONS_OK\"'}.get(mode, "GEORELAY_RUNTIME_LOCATIONS_OK"))
        if mode == "rpc-return":
            print(":ok")
        sys.exit(0)
    if mode == "sql-error":
        print("fake-private-error", file=sys.stderr)
        sys.exit(1)
    print({"sql-empty": "0|t", "sql-missing-table": "91|f"}.get(mode, "91|t"))
'''


class MainImageSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        docker = self.directory / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        self.state = self.directory / "state.json"
        self.body = self.directory / "body.html"
        self.body.write_text(LOGIN_HTML, encoding="utf-8")

    def smoke(self, mode="success", **overrides):
        self.state.unlink(missing_ok=True)
        self.body.write_text(overrides.pop("FAKE_BODY", LOGIN_HTML), encoding="utf-8")
        started = time.monotonic()
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/test_main_image.sh"), "app:checked", "probe:checked"],
            env={**os.environ, "PATH": str(self.directory) + os.pathsep + os.environ["PATH"],
                 "TMPDIR": str(self.directory), "FAKE_STATE": str(self.state), "FAKE_MODE": mode, "FAKE_BODY_FILE": str(self.body),
                 "MAIN_IMAGE_TIMEOUT_SECONDS": "3", **overrides},
            capture_output=True, text=True, timeout=10,
        )
        state = json.loads(self.state.read_text()) if self.state.exists() else None
        self.assertEqual(list(self.directory.glob("tmp.*")), [], "temporary stdout file was not cleaned")
        self.assertNotIn("fake-private-error", result.stdout + result.stderr)
        self.assertNotIn("isolated-test-only", result.stdout + result.stderr)
        self.assertNotIn("isolated-smoke-test-only", result.stdout + result.stderr)
        if state is not None:
            if mode != "container-cleanup-error":
                self.assertEqual(state["containers"], [], "containers were not cleaned")
            if mode != "cleanup-error":
                self.assertEqual(state["networks"], [], "network was not cleaned")
            self.assertTrue(any(command[:2] == ["rm", "-fv"] for command in state["commands"]))
            self.assertFalse(any(command[0] == "logs" for command in state["commands"]))
        return result, state, time.monotonic() - started

    def test_default_release_start_and_real_http_probe_then_migration_readback(self):
        result, state, _ = self.smoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/sign_in HTTP 200", result.stdout)
        self.assertIn("migrations=91; core tables present", result.stdout)
        commands = state["commands"]
        app = next(command for command in commands if command[-1] == "app:checked")
        self.assertNotIn("--entrypoint", app)
        self.assertIn("--pull=never", app)
        database = next(command for command in commands if command[-1] == "postgres:18-trixie")
        self.assertIn("--tmpfs", database)
        self.assertIn("/var/lib/postgresql", database)
        self.assertIn("POSTGRES_DB=georelay_smoke", database)
        self.assertTrue(any(command[:3] == ["network", "create", "--internal"] for command in commands))
        for command in (app, database):
            self.assertFalse(set(command) & {"-p", "--publish", "-P", "--publish-all", "-v", "--volume"})
        self.assertNotIn("--mount", database)
        self.assertIn("NOMINATIM_BASE_URL=http://stub:8080", app)
        self.assertIn("NOMINATIM_LOCAL_IDENTITIES_ONLY=true", app)
        self.assertTrue(app[app.index("--mount") + 1].endswith("runtime_locations.exs,readonly"))
        stub = next(command for command in commands if command[-1] == "/checks/runtime_geocoder_stub.py")
        self.assertIn("--pull=never", stub)
        self.assertTrue(stub[stub.index("--mount") + 1].endswith("runtime_geocoder_stub.py,readonly"))
        probe_index = next(i for i, command in enumerate(commands) if "-c" in command)
        sql_index = next(i for i, command in enumerate(commands) if "psql" in command)
        self.assertLess(probe_index, sql_index)
        self.assertIn("ON_ERROR_STOP=1", commands[sql_index])
        self.assertIn("PGOPTIONS=-c statement_timeout=5000 -c lock_timeout=5000", commands[sql_index])
        for table in ("schema_migrations", "cars", "addresses", "positions", "drives", "charging_processes", "settings"):
            self.assertIn(table, commands[sql_index][-1])

    def test_early_exit_and_start_failure_fail_and_clean(self):
        for mode in ("app-exit", "db-exit", "stub-exit", "start-error"):
            with self.subTest(mode=mode):
                result, state, _ = self.smoke(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Main image smoke failed", result.stderr)
                if mode.endswith("-exit"):
                    self.assertIn("state=exited exit=17", result.stderr)
                self.assertFalse(any("psql" in command for command in state["commands"]))

    def test_http_requires_token_form_status_type_and_no_redirect(self):
        cases = [
            {"mode": "http-status"}, {"mode": "http-error"},
            {"FAKE_CONTENT_TYPE": "application/json"}, {"FAKE_REDIRECT": "http://app:4000/"},
            {"FAKE_BODY": "TeslaMate"},
            {"FAKE_BODY": LOGIN_HTML.replace('name="tokens[access]"', 'name="unrelated"')},
            {"FAKE_BODY": LOGIN_HTML.replace('name="tokens[refresh]"', 'name="unrelated"')},
            {"FAKE_BODY": LOGIN_HTML.replace('phx-submit="sign_in"', 'phx-submit="other"')},
            {"FAKE_BODY": LOGIN_HTML.replace('id="tokens"', 'id="other"')},
            {"FAKE_BODY": LOGIN_HTML + "x" * 262145},
            {"FAKE_BODY": LOGIN_HTML + "é" * 131072},
        ]
        for case in cases:
            with self.subTest(case=list(case)):
                result, state, _ = self.smoke(**case)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("HTTP login response or fixture probe execution invalid", result.stderr)
                self.assertFalse(any("psql" in command for command in state["commands"]))

    def test_token_form_probe_accepts_ui_brand_changes(self):
        body = LOGIN_HTML.replace("TeslaMate", "Fixture UI")
        result, state, _ = self.smoke(FAKE_BODY=body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any("rpc" in command for command in state["commands"]))
        self.assertNotIn("/notice", result.stdout)
        self.assertNotIn("/license", result.stdout)

    def test_missing_migrations_tables_and_query_errors_fail_and_clean(self):
        for mode in ("sql-empty", "sql-missing-table", "sql-error"):
            with self.subTest(mode=mode):
                result, _, _ = self.smoke(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("migration", result.stderr)
                self.assertNotIn("smoke passed", result.stdout)

    def test_readiness_timeout_is_bounded_and_cleans(self):
        result, _, elapsed = self.smoke("timeout", MAIN_IMAGE_TIMEOUT_SECONDS="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP readiness timeout", result.stderr)
        self.assertLess(elapsed, 6)

    def test_signals_cancel_blocked_docker_calls_and_reap_before_cleanup(self):
        for mode, signum in (("block-inspect", signal.SIGTERM), ("block-probe", signal.SIGTERM),
                             ("block-sql", signal.SIGTERM), ("block-rpc", signal.SIGTERM), ("block-inspect", signal.SIGINT)):
            with self.subTest(mode=mode, signal=signum):
                self.state.unlink(missing_ok=True)
                ready = self.directory / "ready"
                ready.unlink(missing_ok=True)
                process = subprocess.Popen(
                    ["bash", str(ROOT / "scripts/test_main_image.sh"), "app:checked", "probe:checked"],
                    env={**os.environ, "PATH": str(self.directory) + os.pathsep + os.environ["PATH"],
                         "TMPDIR": str(self.directory), "FAKE_STATE": str(self.state), "FAKE_MODE": mode, "FAKE_BODY_FILE": str(self.body),
                         "FAKE_READY": str(ready), "MAIN_IMAGE_TIMEOUT_SECONDS": "120"},
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
                )
                try:
                    deadline = time.monotonic() + 5
                    while not ready.exists() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertTrue(ready.exists(), "fixture never reached blocked Docker call")
                    docker_pid, wrapper_pid = map(int, ready.read_text().split())
                    process.send_signal(signum)  # Only the Bash entry PID, not its group.
                    try:
                        stdout, stderr = process.communicate(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.fail("signal did not promptly interrupt the blocked Docker command")
                    self.assertEqual(process.returncode, 128 + signum, stderr)
                    self.assertNotIn("smoke passed", stdout)
                    self.assertNotIn("Traceback", stderr)
                    for pid in (docker_pid, wrapper_pid):
                        with self.assertRaises(ProcessLookupError):
                            os.kill(pid, 0)
                    self.assertEqual(list(self.directory.glob("tmp.*")), [])
                    state = json.loads(self.state.read_text())
                    self.assertEqual(state["containers"], [])
                    self.assertEqual(state["networks"], [])
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)  # Bound cleanup of a failing fixture.
                    process.communicate()

    def test_cleanup_failure_prevents_successful_exit(self):
        for mode in ("cleanup-error", "container-cleanup-error"):
            with self.subTest(mode=mode):
                result, state, _ = self.smoke(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("isolated resource cleanup", result.stderr)
                self.assertNotIn("smoke passed", result.stdout)
                self.assertTrue(state["networks"] if mode == "cleanup-error" else state["containers"])

    def test_compiled_rpc_must_pass_before_success(self):
        result, _, _ = self.smoke("rpc-return")
        self.assertEqual(result.returncode, 0, result.stderr)
        for mode in ("rpc-error", "rpc-marker-missing", "rpc-marker-spoof"):
            with self.subTest(mode=mode):
                result, _, _ = self.smoke(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("compiled address RPC", result.stderr)
                self.assertNotIn("smoke passed", result.stdout)

    def test_public_fixture_http_contract_and_fallback_detection(self):
        spec = importlib.util.spec_from_file_location("runtime_geocoder_stub", ROOT / "scripts/runtime_geocoder_stub.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        server = HTTPServer(("127.0.0.1", 0), module.Handler)
        server.events = []
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            origin = "http://127.0.0.1:" + str(server.server_port)
            def fetch(path, language="en"):
                request = Request(origin + path, headers={"Accept-Language": language})
                try:
                    response = urlopen(request, timeout=2)
                except HTTPError as error:
                    response = error
                with response:
                    return response.status, json.load(response)
            reverse = "/reverse?format=jsonv2&lat=48.8584&lon=2.2945"
            for _ in range(2):
                status, body = fetch(reverse)
                self.assertEqual((status, body["osm_id"], body["lat"]), (200, -10001, "48.8584"))
            lookup = "/lookup?format=jsonv2&osm_ids=W42,N-10001"
            status, body = fetch(lookup, "zh-CN")
            self.assertEqual((status, body[0]["name"], body[0]["lat"]), (200, "Fixture Updated", "49.0"))
            self.assertEqual(fetch(lookup, "missing"), (200, []))
            self.assertEqual(fetch(lookup, "provider-fail"), (502, {"error": "fixture_provider_failure"}))
            self.assertEqual(fetch(reverse.replace("48.8584", "48.8585")), (502, {"error": "fixture_provider_failure"}))
            self.assertEqual(fetch("/assertions"), (200, {"ok": True}))
            fetch(reverse)  # An unexpected reverse fallback invalidates the RPC gate.
            self.assertEqual(fetch("/assertions"), (200, {"ok": False}))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_invalid_deadline_does_not_create_resources(self):
        for value in ("0", "601", "oops", "18446744073709551617"):
            with self.subTest(value=value):
                result, state, _ = self.smoke(MAIN_IMAGE_TIMEOUT_SECONDS=value)
                self.assertEqual(result.returncode, 2)
                self.assertIsNone(state)

    def test_ci_gates_both_native_architectures_before_artifact_save(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        call = workflow.index("run: exec bash scripts/test_main_image.sh georelay:checked georelay-adapter:checked")
        self.assertLess(workflow.index("docker build --platform"), call)
        self.assertLess(call, workflow.index("docker save"))
        for runner in ("ubuntu-latest", "ubuntu-24.04-arm"):
            self.assertIn("runner: " + runner, workflow)


if __name__ == "__main__":
    unittest.main()
