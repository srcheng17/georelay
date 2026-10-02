"""No external requests or real keys: public-landmark coordinates are fixtures."""

import concurrent.futures
import contextlib
import copy
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request

from adapter import server


LAT, LON = "39.908823", "116.397470"
OSM_LAT, OSM_LON = "48.85837", "2.294481"
USER_AGENT = "Adapter-test/1.0 (test@example.invalid)"
AMAP = {
    "status": "1", "regeocode": {
        "formatted_address": "北京市东城区测试路1号",
        "addressComponent": {
            "province": "北京市", "city": [], "district": "东城区", "township": [],
            "streetNumber": {"street": "测试路", "number": "1号"},
            "building": {"name": []}, "neighborhood": {"name": ""},
        },
    },
}
OSM = {
    "osm_id": 123, "osm_type": "way", "lat": "0", "lon": "0",
    "display_name": "Tour Eiffel, Paris, France", "name": "Tour Eiffel",
    "address": {"road": "Avenue Gustave Eiffel", "city": "Paris", "country": "France", "country_code": "fr"},
}


class MockHTTP(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requests.append((self.path, dict(self.headers)))
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", self.server.url + "/stolen")
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        try:
            if self.path.startswith("/slow"):
                for _ in range(30):
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.05)
            elif self.path.startswith("/large"):
                self.wfile.write(b"x" * (server.MAX_BODY + 1))
            elif self.path.startswith("/osm-lookup"):
                self.wfile.write(json.dumps([OSM]).encode())
            else:
                self.wfile.write(json.dumps(OSM if self.path.startswith("/osm") else AMAP).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass


@contextlib.contextmanager
def serving(http):
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}"
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


class AdapterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "adapter.sqlite3"
        self.adapter = server.Adapter(self.db_path, "fake-test-key", user_agent=USER_AGENT)

    def error(self, status, function, *args):
        with self.assertRaises(server.AdapterError) as raised:
            function(*args)
        self.assertEqual(raised.exception.status, status)
        self.assertNotIn("Unable to geocode", str(raised.exception))

    def expire(self):
        with self.adapter.connect() as db:
            db.execute("UPDATE cache SET expires=0")

    def test_coordinate_canonicalization_preserves_arbitrary_input_precision(self):
        for value in ["116.397470", "+116.39747", "1.1639747e2", "00116.39747000"]:
            self.assertEqual(server.coordinate(value, 180), "116.39747")
        self.assertEqual(server.coordinate("-0.000", 90), "0")
        precise = "39.123456789012345678901234567890123456789"
        self.assertEqual(server.coordinate(precise, 90), precise)
        for value in [None, "nan", "NaN", "Infinity", " 3", "3 ", "--1", "90.0000000000000000000000000000000000001", "1e-999"]:
            self.error(400, server.coordinate, value, 90)

    def test_gcj02_known_vector_and_outside_guard(self):
        lon, lat = server.gcj02(LAT, LON)
        self.assertAlmostEqual(lon, 116.4037135824, places=8)
        self.assertAlmostEqual(lat, 39.9102264981, places=8)
        self.assertEqual(server.gcj02(OSM_LAT, OSM_LON), (float(OSM_LON), float(OSM_LAT)))

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_reverse_lookup_restart_language_ttl_and_original_wgs84(self, upstream):
        first = self.adapter.reverse(LAT, LON, "zh-cn")
        self.assertEqual((first["lat"], first["lon"]), (LAT, "116.39747"))
        self.assertEqual((first["osm_type"], first["osm_id"]), ("node", -1))
        self.assertEqual(first["address"]["city"], "北京市")
        self.assertEqual(first["address"]["road"], "测试路")
        self.assertNotIn("neighbourhood", first["address"])
        self.assertEqual(self.adapter.reverse(LAT, "1.1639747e2", "zh-cn"), first)
        self.assertEqual(upstream.call_count, 1)
        restarted = server.Adapter(self.db_path, "fake-test-key", user_agent=USER_AGENT)
        self.assertEqual(restarted.lookup("N-1", "zh-cn"), [first])
        self.assertEqual(upstream.call_count, 1)
        self.assertEqual(restarted.lookup("N-1", "en")[0]["osm_id"], -1)
        self.assertEqual(upstream.call_count, 2)
        self.expire()
        self.assertEqual(restarted.lookup("N-1", "zh-cn")[0]["osm_id"], -1)
        self.assertEqual(upstream.call_count, 3)
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT id,lat,lon FROM identities").fetchall(), [(1, LAT, "116.39747")])

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_concurrent_reverse_assigns_one_identity(self, upstream):
        adapters = [server.Adapter(self.db_path, "fake-test-key") for _ in range(4)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda index: adapters[index % 4].reverse(LAT, LON), range(24)))
        self.assertEqual({row["osm_id"] for row in results}, {-1})
        second = self.adapter.reverse("39.90", LON)
        self.assertEqual(second["osm_id"], -2)
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM identities").fetchone()[0], 2)

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_lookup_validates_entire_batch_and_never_returns_foreign_identity(self, upstream):
        first = self.adapter.reverse(LAT, LON)
        calls = upstream.call_count
        for value, status in [("N-1,N-999", 404), ("N12", 422), ("W-1", 422), ("R20", 422),
                              ("N-0", 400), ("N-01", 400), ("N-9223372036854775808", 400),
                              ("N-1,", 400), ("n-1", 400), ("N-1," * 50 + "N-1", 400)]:
            self.error(status, self.adapter.lookup, value)
        self.assertEqual(upstream.call_count, calls)
        self.assertEqual(self.adapter.lookup("N-1,N-1"), [first])
        self.assertEqual(self.adapter.lookup(""), [])

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_cache_missing_key_and_upstream_failures_never_become_unknown(self, upstream):
        first = self.adapter.reverse(LAT, LON)
        self.adapter.key = ""
        self.assertEqual(self.adapter.lookup("N-1"), [first])
        self.expire()
        self.error(503, self.adapter.lookup, "N-1")
        self.adapter.key = "fake-test-key"
        upstream.side_effect = server.AdapterError(504, "Upstream request timed out")
        self.error(504, self.adapter.lookup, "N-1")
        upstream.side_effect = None
        for payload in [{"status": "0", "info": "private text"}, {"error": "Unable to geocode"}, {"status": "1", "regeocode": []}, []]:
            upstream.return_value = payload
            self.error(502, self.adapter.lookup, "N-1")
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT id FROM identities").fetchall(), [(1,)])

    @patch("adapter.server.upstream", return_value=OSM)
    def test_overseas_needs_no_amap_key_and_retains_local_identity_and_wgs84(self, upstream):
        self.adapter.key = ""
        result = self.adapter.reverse(OSM_LAT, OSM_LON, "fr")
        self.assertEqual(result["osm_id"], -1)
        self.assertEqual(result["osm_type"], "node")
        self.assertEqual((result["lat"], result["lon"]), (OSM_LAT, OSM_LON))
        self.assertEqual(result["upstream"]["osm_id"], 123)
        self.assertEqual(upstream.call_args.args[:6], ("osm", "", OSM_LAT, OSM_LON, "fr", USER_AGENT))
        self.adapter.user_agent = ""
        self.assertEqual(self.adapter.lookup("N-1", "fr"), [result])
        self.expire()
        self.error(503, self.adapter.lookup, "N-1", "fr")

    @patch("adapter.server.upstream")
    def test_amap_border_result_falls_back_osm_without_changing_identity(self, upstream):
        upstream.return_value = AMAP
        first = self.adapter.reverse(LAT, LON)
        self.expire()
        upstream.reset_mock()
        first = copy.deepcopy(AMAP)
        first["regeocode"]["addressComponent"]["province"] = "香港特别行政区"
        upstream.side_effect = [first, OSM]
        result = self.adapter.reverse(LAT, LON)
        self.assertEqual(result["osm_id"], -1)
        self.assertEqual([call.args[0] for call in upstream.call_args_list], ["amap", "osm"])
        self.expire()
        upstream.side_effect = [[OSM]]
        self.assertEqual(self.adapter.lookup("N-1")[0]["osm_id"], -1)
        self.assertEqual(upstream.call_args.args[-1], "W123")
        wrong_country = copy.deepcopy(AMAP)
        wrong_country["regeocode"]["addressComponent"]["country"] = "Japan"
        self.assertFalse(server.mainland_response(wrong_country))

    def test_inside_bbox_foreign_confirmation_and_mainland_errors(self):
        # These overseas cities are inside the conventional GCJ mathematical box.
        for index, (lat, lon, country) in enumerate([
            ("37.5665", "126.978", "kr"), ("34.6937", "135.5023", "jp"),
            ("1.3521", "103.8198", "sg"), ("13.7563", "100.5018", "th"),
        ]):
            foreign = copy.deepcopy(OSM)
            foreign["address"]["country_code"] = country
            with patch.object(self.adapter, "osm", return_value=foreign), patch("adapter.server.upstream", side_effect=server.AdapterError(504, "Upstream request timed out")) as upstream:
                result = self.adapter.reverse(lat, lon)
                self.assertEqual(result["osm_id"], -(index + 1))
                self.assertEqual(result["address"]["country_code"], country)
                self.assertEqual(upstream.call_count, 1)
                self.expire()
                self.assertEqual(self.adapter.reverse(lat, lon)["osm_id"], result["osm_id"])
                self.assertEqual(upstream.call_count, 1)  # Trusted provenance bypasses AMap.
        self.adapter.key = ""
        mainland = copy.deepcopy(OSM)
        mainland["address"]["country_code"] = "cn"
        with patch.object(self.adapter, "osm", return_value=mainland):
            self.error(503, self.adapter.reverse, LAT, LON)
        self.adapter.key = "fake-test-key"
        with patch.object(self.adapter, "osm", return_value=mainland), patch("adapter.server.upstream", side_effect=server.AdapterError(504, "Upstream request timed out")):
            self.error(504, self.adapter.reverse, LAT, LON)
        self.adapter.key = ""
        for code in ["", "?", "china"]:
            mainland["address"]["country_code"] = code
            with patch.object(self.adapter, "osm", return_value=mainland):
                self.error(503, self.adapter.reverse, LAT, LON)
        for lat, lon, country, region in [("37.5", "126.98", "kr", ""),
                                           ("25.033", "121.5654", "tw", ""),
                                           ("22.3193", "114.1694", "cn", "CN-HK"),
                                           ("22.1987", "113.5439", "cn", "CN-MO")]:
            foreign = copy.deepcopy(OSM)
            foreign["address"].update({"country_code": country, "ISO3166-2-lvl3": region})
            started = time.monotonic()
            with patch.object(self.adapter, "osm", return_value=foreign) as osm, patch("adapter.server.upstream") as upstream:
                result = self.adapter.reverse(lat, lon)
                self.assertEqual(result["address"]["country_code"], country)
                self.assertEqual((result["lat"], result["lon"]), (lat, lon))
                upstream.assert_not_called()
            self.assertGreater(osm.call_args.args[-1] - started, 16.9)
            self.assertLess(osm.call_args.args[-1] - started, 17.1)

    def test_hong_kong_macao_country_cn_require_iso_subdivision(self):
        for region in ["CN-HK", "CN-MO"]:
            payload = copy.deepcopy(OSM)
            payload["address"] = {"country_code": "cn", "ISO3166-2-lvl3": region}
            server.require_outside_mainland(payload, server.AdapterError(502, "Not confirmed"))
        payload["address"]["ISO3166-2-lvl3"] = "CN-GD"
        self.error(502, server.require_outside_mainland, payload, server.AdapterError(502, "Not confirmed"))

    def test_fifty_cold_osm_lookup_uses_one_verified_batch_and_preserves_all_ids(self):
        originals = []
        for index in range(50):
            payload = copy.deepcopy(OSM)
            payload["osm_id"] = index if index else 1  # First two locals share one OSM object.
            with patch.object(self.adapter, "osm", return_value=payload):
                originals.append(self.adapter.reverse(f"48.{index:06d}", OSM_LON, "fr"))
        self.expire()
        restarted = server.Adapter(self.db_path, user_agent=USER_AGENT)
        responses = [{**OSM, "osm_id": index} for index in range(1, 50)]
        ids = ",".join("N" + str(item["osm_id"]) for item in originals)
        with patch("adapter.server.upstream", return_value=list(reversed(responses))) as upstream:
            refreshed = restarted.lookup(ids, "en")
        self.assertEqual(upstream.call_count, 1)
        self.assertEqual(set(upstream.call_args.args[-1].split(",")), {f"W{index}" for index in range(1, 50)})
        self.assertEqual([(item["osm_id"], item["lat"], item["lon"]) for item in refreshed],
                         [(item["osm_id"], item["lat"], item["lon"]) for item in originals])

    def test_osm_batch_rejects_missing_duplicate_and_unrequested_identity(self):
        with patch.object(self.adapter, "osm", return_value=OSM):
            self.adapter.reverse(OSM_LAT, OSM_LON, "fr")
            self.adapter.reverse("48.85", OSM_LON, "fr")
        for payload in [[], [OSM, OSM], [{**OSM, "osm_id": 999}], {"error": "Unable to geocode"}]:
            with patch.object(self.adapter, "osm", return_value=payload):
                self.error(502, self.adapter.lookup, "N-1,N-2", "en")
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM cache WHERE language='en'").fetchone()[0], 0)

    def test_legacy_schema_migration_preserves_ids(self):
        legacy = Path(self.temp.name) / "legacy.sqlite3"
        with sqlite3.connect(legacy) as db:
            db.execute("CREATE TABLE identities (id INTEGER PRIMARY KEY AUTOINCREMENT, lat TEXT NOT NULL, lon TEXT NOT NULL, UNIQUE(lat,lon))")
            db.execute("INSERT INTO identities VALUES(10001,?,?)", (LAT, LON))
        adapter = server.Adapter(legacy, "fake-test-key")
        with patch("adapter.server.upstream", return_value=AMAP):
            self.assertEqual(adapter.lookup("N-10001")[0]["osm_id"], -10001)
            self.assertEqual(adapter.reverse("39.9", LON)["osm_id"], -10002)

    @patch("adapter.server.upstream")
    def test_osm_serialization_and_budget_include_rate_wait(self, upstream):
        starts = []
        def request(*args):
            starts.append(time.monotonic())
            return OSM
        upstream.side_effect = request
        other = server.Adapter(self.db_path, user_agent=USER_AGENT)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda adapter: adapter.reverse(OSM_LAT, OSM_LON), [self.adapter, other]))
        # Concurrent identical cache fills may coalesce naturally; force a miss.
        if len(starts) == 1:
            self.adapter.reverse(OSM_LAT, OSM_LON, "fr")
        self.assertGreaterEqual(starts[1] - starts[0], 0.99)
        self.adapter.lookup_timeout = 0.1
        started = time.monotonic()
        self.error(504, self.adapter.lookup, "N-1", "de")
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertEqual(len(starts), 2)

    def test_osm_malformed_or_unknown_response_is_failure(self):
        for payload in [{"error": "Unable to geocode"}, [], {}, {**OSM, "display_name": []},
                        {**OSM, "address": []}, {**OSM, "address": {}},
                        {**OSM, "address": {"city": []}}, {**OSM, "osm_type": "unknown"},
                        {**OSM, "osm_id": -99}, {**OSM, "osm_id": True}]:
            self.error(502, server.osm_address, payload, 1, OSM_LAT, OSM_LON)

    def test_osm_lock_wait_has_a_deadline_across_processes(self):
        code = ("import fcntl,sys,time; "
                "f=open(sys.argv[1], 'w'); fcntl.flock(f, fcntl.LOCK_EX); "
                "print('locked', flush=True); time.sleep(10)")
        holder = subprocess.Popen([sys.executable, "-c", code, str(self.db_path) + ".osm.lock"],
                                  stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            started = time.monotonic()
            self.error(504, self.adapter.osm, OSM_LAT, OSM_LON, "en", started + 0.1)
            self.assertLess(time.monotonic() - started, 0.3)
        finally:
            holder.terminate()
            holder.communicate(timeout=2)

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_entire_lookup_has_one_budget_and_returns_no_partial_list(self, upstream):
        self.adapter.reverse(LAT, LON)
        self.adapter.reverse("39.9", LON)
        self.expire()
        self.adapter.lookup_timeout = 0.12
        budgets = []
        def slow(*args):
            budgets.append(args[-1])
            time.sleep(0.075)
            return AMAP
        upstream.side_effect = slow
        self.error(504, self.adapter.lookup, "N-1,N-2")
        self.assertLess(budgets[1], budgets[0])

    def test_real_http_upstream_conversion_osm_coordinates_redirect_and_size(self):
        mock = ThreadingHTTPServer(("127.0.0.1", 0), MockHTTP)
        mock.requests = []
        with serving(mock) as url:
            mock.url = url
            real_run = subprocess.run
            code = ("import json,sys; from adapter import server; "
                    f"server.AMAP_URL={url + '/amap'!r}; "
                    "print(json.dumps(server.fetch(*json.load(sys.stdin))))")
            def local_child(command, **kwargs):
                self.assertNotIn("fake-test-key", " ".join(command))
                return real_run([sys.executable, "-c", code], **kwargs)
            with patch("adapter.server.subprocess.run", side_effect=local_child):
                result = self.adapter.reverse(LAT, LON, "zh")
                self.assertEqual((result["lat"], result["lon"]), (LAT, "116.39747"))
                self.assertEqual(self.adapter.lookup("N-1", "zh"), [result])
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(mock.requests[-1][0]).query)
            self.assertEqual(query["location"], ["116.40371358,39.91022650"])
            self.assertNotEqual(query["location"][0], f"{LON},{LAT}")
            with patch.object(server, "OSM_URL", url + "/osm"):
                self.assertEqual(server.fetch("osm", "", OSM_LAT, OSM_LON, "fr", USER_AGENT, 1), OSM)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(mock.requests[-1][0]).query)
            self.assertEqual((query["lat"], query["lon"]), ([OSM_LAT], [OSM_LON]))
            self.assertEqual(mock.requests[-1][1]["User-Agent"], USER_AGENT)
            self.assertNotIn("key", query)
            with patch.object(server, "OSM_LOOKUP_URL", url + "/osm-lookup"):
                self.assertEqual(server.fetch("osm", "", "", "", "de", USER_AGENT, 1, "W123"), [OSM])
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(mock.requests[-1][0]).query)
            self.assertEqual(query["osm_ids"], ["W123"])
            self.assertNotIn("lat", query)
            self.assertNotIn("lon", query)
            self.assertNotIn("key", query)
            with patch.object(server, "AMAP_URL", url + "/redirect"):
                with self.assertRaises(urllib.error.HTTPError):
                    server.fetch("amap", "fake-test-key", LAT, LON, "", "", 1)
            self.assertFalse(any(path.startswith("/stolen") for path, _ in mock.requests))
            with patch.object(server, "AMAP_URL", url + "/large"):
                self.error(502, server.fetch, "amap", "fake-test-key", LAT, LON, "", "", 1)

    def test_actual_network_child_killed_on_slow_drip(self):
        mock = ThreadingHTTPServer(("127.0.0.1", 0), MockHTTP)
        mock.requests = []
        real_run = subprocess.run
        with serving(mock) as url:
            code = ("import json,sys; from adapter import server; "
                    f"server.AMAP_URL={url + '/slow'!r}; "
                    "print(json.dumps(server.fetch(*json.load(sys.stdin))))")
            def local_child(command, **kwargs):
                return real_run([sys.executable, "-c", code], **kwargs)
            started = time.monotonic()
            with patch("adapter.server.subprocess.run", side_effect=local_child):
                self.error(504, server.upstream, "amap", "fake-test-key", LAT, LON, "", "", 0.3)
            self.assertLess(time.monotonic() - started, 0.8)
            self.assertTrue(mock.requests)

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_http_contract_and_private_logs(self, upstream):
        output = io.StringIO()
        with contextlib.redirect_stderr(output), serving(server.Server(("127.0.0.1", 0), self.adapter)) as url:
            def get(path, status=200, **headers):
                request = urllib.request.Request(url + path, headers=headers)
                try:
                    response = urllib.request.urlopen(request, timeout=3)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    self.assertEqual(response.status, status)
                    self.assertEqual(response.headers.get_content_type(), "application/json")
                    return json.load(response)
            self.assertEqual(get("/health"), {"status": "ok"})
            self.assertEqual(upstream.call_count, 0)
            result = get(f"/reverse?lat={LAT}&lon={LON}&format=jsonv2", **{"Accept-Language": "ZH-CN"})
            self.assertEqual(get("/lookup?osm_ids=N-1", **{"Accept-Language": "zh-cn"}), [result])
            for path, status in [("/reverse?lat=nan&lon=2", 400), ("/reverse?lat=1&lat=2&lon=3", 400),
                                 ("/lookup", 400), ("/lookup?osm_ids=N123", 422),
                                 ("/lookup?osm_ids=N-999", 404), ("/missing", 404),
                                 ("/reverse?" + "x" * 4100, 414), ("/health?format=xml", 400)]:
                self.assertIn("error", get(path, status))
            self.expire()
            upstream.side_effect = server.AdapterError(504, "Upstream request timed out")
            body = get("/lookup?osm_ids=N-1", 504)
            self.assertNotIn("Unable to geocode", json.dumps(body))
            request = urllib.request.Request(url + "/" + LAT, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(request, timeout=3)
            self.assertNotIn(LAT, raised.exception.read().decode())
        self.assertNotIn(LAT, output.getvalue())
        self.assertNotIn("fake-test-key", output.getvalue())

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_sqlite_online_backup_preserves_identity_and_refuses_overwrite(self, upstream):
        self.adapter.reverse(LAT, LON)
        backup = Path(self.temp.name) / "backup.sqlite3"
        env = {**os.environ, "ADAPTER_DB": str(self.db_path)}
        command = [sys.executable, "-m", "adapter.server", "--backup", str(backup)]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        restored = server.Adapter(backup)
        self.assertEqual(restored.lookup("N-1")[0]["osm_id"], -1)
        self.assertEqual(subprocess.run(command, env=env, capture_output=True).returncode, 1)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        missing_env = {**env, "ADAPTER_DB": str(self.db_path) + ".missing"}
        missing_backup = Path(self.temp.name) / "missing.sqlite3"
        result = subprocess.run(command[:-1] + [str(missing_backup)], env=missing_env, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(missing_backup.exists())

    def test_configuration_bounds(self):
        for value in ["0", "-1", "nan", "inf", "oops", "26"]:
            with patch.dict(os.environ, {"LOOKUP_TIMEOUT_SECONDS": value}):
                with self.assertRaises(ValueError):
                    server.number_env("LOOKUP_TIMEOUT_SECONDS", "20", 25)


if __name__ == "__main__":
    unittest.main()
