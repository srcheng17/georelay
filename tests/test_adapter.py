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
BAIDU = {
    "status": 0, "result": {
        "location": {"lat": 39.915, "lng": 116.410},  # BD09: never persisted.
        "formatted_address": "北京市东城区测试路1号",
        "addressComponent": {
            "country": "中国", "country_code_iso2": "CN", "country_code": 0,
            "province": "北京市", "city": "北京市", "district": "东城区",
            "town": [], "street": "测试路", "street_number": "1号",
        },
        "poiRegions": [{"name": "虚构园区"}], "pois": [{"name": "虚构设施"}],
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
                for _ in range(100):  # Five seconds: exceeds the child's total deadline.
                    self.wfile.write(b" ")
                    self.wfile.flush()
                    time.sleep(0.05)
            elif self.path.startswith("/large"):
                self.wfile.write(b"x" * (server.MAX_BODY + 1))
            elif self.path.startswith("/osm-lookup"):
                self.wfile.write(json.dumps([OSM]).encode())
            elif self.path.startswith("/baidu"):
                self.wfile.write(json.dumps(BAIDU).encode())
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


def address(identity=-1, lat=LAT, lon=LON, context=None):
    return {"osm_id": identity, "osm_type": "node", "lat": server.coordinate(lat, 90),
            "lon": server.coordinate(lon, 180), "context": context or {"outside_mainland": False}}


def from_response(body):
    context = {key: value for key, value in body["georelay"].items() if key != "version"}
    return address(body["osm_id"], body["lat"], body["lon"], context)


class AdapterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / "cache.sqlite3"
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
        tiny = "0." + "0" * 1023 + "1"
        self.assertEqual(server.coordinate("1e-1024", 90), tiny)
        self.assertEqual(server.coordinate(tiny, 90), tiny)
        self.error(400, server.coordinate, "1." + "1" * 1024, 90)
        for value in [None, "nan", "NaN", "Infinity", " 3", "3 ", "--1", "90.0000000000000000000000000000000000001", "1e-1025"]:
            self.error(400, server.coordinate, value, 90)

    def test_gcj02_known_vector_and_outside_guard(self):
        lon, lat = server.gcj02(LAT, LON)
        self.assertAlmostEqual(lon, 116.4037135824, places=8)
        self.assertAlmostEqual(lat, 39.9102264981, places=8)
        self.assertEqual(server.gcj02(OSM_LAT, OSM_LON), (float(OSM_LON), float(OSM_LAT)))

    def test_baidu_official_public_sn_vector_and_normalized_mapping(self):
        query = urllib.parse.urlencode([("address", "百度大厦"), ("output", "json"), ("ak", "yourak")])
        self.assertEqual(server.baidu_sn("/geocoder/v2/", query, "yoursk"), "7de5a22212ffaa9e326444c75a58f9a0")
        cases = [
            ([{"name": " 虚构园区 "}], [{"name": "虚构设施"}], "测试路", "虚构园区"),
            ([None, {"name": "不取第二项"}], [{"name": " 虚构设施 "}], "测试路", "虚构设施"),
            ("invalid", [None, {"name": "不取第二项"}], "测试路", "测试路"),
            ([], {}, [], BAIDU["result"]["formatted_address"]),
        ]
        for regions, pois, road, expected in cases:
            payload = copy.deepcopy(BAIDU)
            payload["result"].update({"poiRegions": regions, "pois": pois})
            payload["result"]["addressComponent"].update({"street": road, "city": [], "town": []})
            result = server.baidu_address(payload, 10001, LAT, LON)
            self.assertEqual(result["name"], expected)
            self.assertEqual(result["namedetails"]["name"], expected)
            self.assertEqual((result["osm_id"], result["lat"], result["lon"]), (-10001, LAT, LON))
            self.assertEqual(result["address"]["city"], "北京市")
            self.assertEqual(result["address"]["country_code"], "cn")
            self.assertNotIn("neighbourhood", result["address"])
        for status in [False, "0", None, 1]:
            self.error(502, server.baidu_address, {**BAIDU, "status": status}, 1, LAT, LON)
        payload["result"]["formatted_address"] = []
        self.error(502, server.baidu_address, payload, 1, LAT, LON)

    def test_amap_name_uses_first_aoi_then_first_poi_then_existing_fallbacks(self):
        cases = [
            ([{"name": " 虚构园区甲 "}], [{"name": "虚构设施乙"}], "虚构楼宇", "虚构小区", "测试路", "虚构园区甲"),
            ([{"name": []}, {"name": "不取第二个AOI"}], [{"name": " 虚构设施乙 "}], "虚构楼宇", "虚构小区", "测试路", "虚构设施乙"),
            ("invalid", [None, {"name": "不取第二个POI"}], "虚构楼宇", "虚构小区", "测试路", "虚构楼宇"),
            ({}, 42, [], "虚构小区", "测试路", "虚构小区"),
            (None, [{"name": " "}], {}, None, "测试路", "测试路"),
            ([5], [], None, "", [], AMAP["regeocode"]["formatted_address"]),
            ([], {"name": "非列表POI"}, "虚构楼宇", "", "测试路", "虚构楼宇"),
        ]
        for aois, pois, building, neighbourhood, road, expected in cases:
            with self.subTest(expected=expected, aois=aois, pois=pois):
                payload = copy.deepcopy(AMAP)
                payload["regeocode"].update({"aois": aois, "pois": pois})
                parts = payload["regeocode"]["addressComponent"]
                parts.update({"building": {"name": building}, "neighborhood": {"name": neighbourhood}})
                parts["streetNumber"]["street"] = road
                result = server.nominatim(payload, 1, LAT, LON)
                self.assertEqual(result["name"], expected)
                self.assertEqual(result["namedetails"]["name"], expected)

    def test_hong_kong_macao_country_cn_require_iso_subdivision(self):
        for region in ["CN-HK", "CN-MO"]:
            payload = copy.deepcopy(OSM)
            payload["address"] = {"country_code": "cn", "ISO3166-2-lvl3": region}
            server.require_outside_mainland(payload, server.AdapterError(502, "Not confirmed"))
        payload["address"]["ISO3166-2-lvl3"] = "CN-GD"
        self.error(502, server.require_outside_mainland, payload, server.AdapterError(502, "Not confirmed"))

    def test_osm_malformed_or_unknown_response_is_failure(self):
        for payload in [{"error": "Unable to geocode"}, [], {}, {**OSM, "display_name": []}, {**OSM, "display_name": "Unable to geocode"},
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
                # Includes interpreter/import startup on a loaded CI runner.
                self.error(504, server.upstream, "amap", "fake-test-key", LAT, LON, "", "", 2)
            self.assertLess(time.monotonic() - started, 3)
            self.assertTrue(mock.requests)

    def test_configuration_bounds(self):
        for value in ["0", "-1", "nan", "inf", "oops", "26"]:
            with patch.dict(os.environ, {"LOOKUP_TIMEOUT_SECONDS": value}):
                with self.assertRaises(ValueError):
                    server.number_env("LOOKUP_TIMEOUT_SECONDS", "20", 25)

    def test_real_http_upstream_conversion_osm_coordinates_redirect_and_size(self):
        mock = ThreadingHTTPServer(("127.0.0.1", 0), MockHTTP)
        mock.requests = []
        with serving(mock) as url:
            mock.url = url
            real_run = subprocess.run
            code = ("import json,sys; from adapter import server; "
                    f"server.AMAP_URL={url + '/amap'!r}; "
                    f"server.AMAP_GLOBAL_URL={url + '/amap-global'!r}; "
                    f"server.BAIDU_URL={url + '/baidu/'!r}; "
                    "print(json.dumps(server.fetch(*json.load(sys.stdin))))")
            def local_child(command, **kwargs):
                self.assertNotIn("fake-test-key", " ".join(command))
                self.assertNotIn("yourak", " ".join(command))
                self.assertNotIn("yoursk", " ".join(command))
                return real_run([sys.executable, "-c", code], **kwargs)
            with patch("adapter.server.subprocess.run", side_effect=local_child):
                result = self.adapter.reverse(address(), "zh")
                self.assertEqual((result["lat"], result["lon"]), (LAT, "116.39747"))
                self.assertEqual(self.adapter.lookup([address()], "zh"), [result])
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(mock.requests[-1][0]).query)
            self.assertEqual(query["location"], ["116.40371358,39.91022650"])
            self.assertEqual(query["extensions"], ["all"])
            self.assertNotEqual(query["location"][0], f"{LON},{LAT}")
            baidu = server.Adapter(self.db_path, provider="baidu", baidu_ak="yourak", baidu_sk="yoursk")
            with patch("adapter.server.subprocess.run", side_effect=local_child):
                result = baidu.reverse(address(), "zh-cn")
                self.assertEqual(result["upstream"]["provider"], "baidu")
                self.assertEqual((result["lat"], result["lon"]), (LAT, "116.39747"))
                self.assertEqual(baidu.lookup([address()], "zh-cn"), [result])
            path = urllib.parse.urlsplit(mock.requests[-1][0])
            query = urllib.parse.parse_qs(path.query)
            self.assertEqual((path.path, query["location"], query["coordtype"]), ("/baidu/", [LAT + ",116.39747"], ["wgs84ll"]))
            self.assertEqual(query["extensions_poi"], ["1"])
            self.assertEqual(query["ak"], ["yourak"])
            unsigned, actual_sn = path.query.rsplit("&sn=", 1)
            self.assertEqual(actual_sn, server.baidu_sn(path.path, unsigned, "yoursk"))
            self.assertNotIn("yoursk", mock.requests[-1][0])
            with patch("adapter.server.subprocess.run", side_effect=local_child):
                server.upstream("amap", "fake-test-key", LAT, LON, "", "", 1, None, "", "global")
            path = urllib.parse.urlsplit(mock.requests[-1][0])
            self.assertEqual(path.path, "/amap-global")
            self.assertEqual(urllib.parse.parse_qs(path.query)["location"], [LON + "," + LAT])
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

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_cache_deletion_restart_language_and_precise_coordinates(self, upstream):
        precise = "39.12345678901234567890123456789"
        row = address(-10001, precise, LON)
        first = self.adapter.reverse(row, "ZH-CN")
        self.assertEqual((first["osm_id"], first["lat"], first["lon"]), (-10001, precise, "116.39747"))
        self.assertEqual(first["georelay"], {"version": 1, "outside_mainland": False})
        restarted = server.Adapter(self.db_path, "fake-test-key")
        self.assertEqual(restarted.lookup([row], "zh-cn"), [first])
        self.assertEqual(upstream.call_count, 1)
        self.assertEqual(restarted.lookup([row], "en")[0]["osm_id"], -10001)
        self.expire()
        self.assertEqual(restarted.lookup([row], "zh-cn")[0]["lat"], precise)
        self.assertEqual(upstream.call_count, 3)
        self.db_path.unlink()
        empty = server.Adapter(self.db_path, "fake-test-key")
        self.assertEqual(empty.lookup([row], "zh-cn"), [first])
        self.assertEqual(upstream.call_count, 4)
        with empty.connect() as db:
            self.assertEqual({r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}, {"cache"})
            self.assertFalse(db.execute("PRAGMA foreign_key_list(cache)").fetchall())

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_concurrent_candidates_share_template_without_sharing_identity(self, upstream):
        adapters = [server.Adapter(self.db_path, "fake-test-key") for _ in range(4)]
        rows = [address(-index - 1) for index in range(24)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda item: adapters[item[0] % 4].reverse(item[1]), enumerate(rows)))
        self.assertEqual([body["osm_id"] for body in results], [row["osm_id"] for row in rows])
        calls = upstream.call_count
        self.assertEqual(self.adapter.reverse(address(-10001))["osm_id"], -10001)
        self.assertEqual(upstream.call_count, calls)
        with self.adapter.connect() as db:
            cached = db.execute("SELECT body FROM cache").fetchall()
            self.assertEqual(len(cached), 1)
            template = json.loads(cached[0][0])
            self.assertFalse({"osm_id", "osm_type", "lat", "lon"} & set(template))

    def test_expired_cache_cleanup_is_bounded_low_frequency_and_preserves_live_entries(self):
        with self.adapter.connect() as db:
            db.executemany("INSERT INTO cache VALUES(?,?,?,?,?)", [(str(i), "", "amap", 0, "{}") for i in range(1200)])
            db.execute("INSERT INTO cache VALUES('live','','amap',?, '{}')", (time.time() + 1000,))
        self.adapter.cleanup(time.monotonic() + 2)
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM cache WHERE expires=0").fetchone()[0], 700)
        self.adapter.cleanup(time.monotonic() + 2)
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM cache").fetchone()[0], 701)
        self.adapter._next_cleanup = 0
        self.adapter.cleanup(time.monotonic() + 2)
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM cache WHERE expires=0").fetchone()[0], 200)
            self.assertEqual(db.execute("SELECT cache_key FROM cache WHERE expires>0").fetchall(), [("live",)])

    def test_legacy_identity_database_is_rejected_without_modification(self):
        legacy = Path(self.temp.name) / "legacy.sqlite3"
        with contextlib.closing(sqlite3.connect(legacy)) as db, db:
            db.execute("CREATE TABLE identities (id INTEGER PRIMARY KEY AUTOINCREMENT, lat TEXT, lon TEXT)")
            db.execute("INSERT INTO identities VALUES(10001,?,?)", (LAT, LON))
        original = legacy.read_bytes()
        with self.assertRaisesRegex(ValueError, "Legacy identity"):
            server.Adapter(legacy)
        self.assertEqual(legacy.read_bytes(), original)
        self.assertFalse(Path(str(legacy) + ".osm.lock").exists())
        with patch.dict(os.environ, {"ADAPTER_DB": str(legacy)}, clear=True), patch.object(sys, "argv", ["adapter.server"]):
            with self.assertRaisesRegex(ValueError, "Legacy ADAPTER_DB"):
                server.main()
        with contextlib.closing(sqlite3.connect(legacy)) as db, db:
            self.assertEqual(db.execute("SELECT id FROM identities").fetchall(), [(10001,)])

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_lookup_validates_whole_batch_and_skips_positive_history(self, upstream):
        rows = [address(-2, "39.9"), address()]
        response = self.adapter.lookup([{"osm_id": 123, "osm_type": "way"}, *rows, {"osm_id": 12, "osm_type": "node"}], "en")
        self.assertEqual([body["osm_id"] for body in response], [-2, -1])
        self.assertEqual(upstream.call_count, 2)
        upstream.reset_mock()
        self.assertEqual(self.adapter.lookup([{"osm_id": 123, "osm_type": "way"}]), [])
        self.assertEqual(self.adapter.lookup([]), [])
        invalid = [None, "N-1", [address(), address()], [address()] * 51,
                   [address(), {**address(-2), "osm_type": "way"}],
                   [address(), {**address(-2), "lat": "nan"}],
                   [address(), {**address(-2), "lat": "39.900"}],
                   [{**address(), "osm_id": 0}], [{**address(), "osm_id": True}],
                   [{**address(), "osm_id": -server.MAX_ID - 1}],
                   [address(context={"outside_mainland": 1})],
                   [address(context={"outside_mainland": False, "source_osm_id": 123})],
                   [address(context={"outside_mainland": False, "source_osm_type": "way", "source_osm_id": -1})]]
        for rows in invalid:
            status = 422 if isinstance(rows, list) and len(rows) == 2 and rows[1].get("osm_type") == "way" else 400
            self.error(status, self.adapter.lookup, rows)
        upstream.assert_not_called()

    def test_provider_changes_keep_application_provenance_and_isolate_caches(self):
        self.adapter.baidu_ak, self.adapter.baidu_sk = "yourak", "yoursk"
        mainland = copy.deepcopy(OSM)
        mainland["address"]["country_code"] = "cn"
        with patch.object(self.adapter, "osm", return_value=mainland):
            osm = self.adapter.reverse(address(), provider="osm")
        row = from_response(osm)
        self.assertFalse(row["context"]["outside_mainland"])
        with patch("adapter.server.upstream", return_value=AMAP) as upstream:
            amap = self.adapter.reverse(row)
            self.assertEqual(upstream.call_args.args[0], "amap")
        with patch("adapter.server.upstream", return_value=BAIDU):
            baidu = self.adapter.reverse(row, provider="baidu")
        self.assertEqual(amap["georelay"], baidu["georelay"])
        self.assertEqual(baidu["georelay"]["source_osm_id"], 123)
        self.assertFalse(baidu["georelay"]["outside_mainland"])
        # Same coordinate, different evidence cannot reuse the mainland template.
        outside = address(context={"outside_mainland": True, "source_osm_type": "way", "source_osm_id": 123})
        with patch.object(self.adapter, "osm", return_value=OSM) as provider, patch("adapter.server.upstream") as keyed:
            result = self.adapter.reverse(outside)
            self.assertTrue(result["georelay"]["outside_mainland"])
            provider.assert_called_once()
            keyed.assert_not_called()
        with self.adapter.connect() as db:
            self.assertEqual({row[0] for row in db.execute("SELECT policy FROM cache")}, {"auto:amap", "baidu", "osm"})

    def test_fixed_baidu_and_global_amap_configuration_and_coverage(self):
        fixed = server.Adapter(self.db_path, provider="baidu", baidu_ak="yourak", baidu_sk="yoursk")
        foreign = copy.deepcopy(BAIDU)
        foreign["result"]["addressComponent"].update(country="France", country_code_iso2="FR", province=[])
        row = address(lat=OSM_LAT, lon=OSM_LON)
        with patch("adapter.server.upstream", return_value=foreign):
            self.assertEqual(fixed.reverse(row)["address"]["country_code"], "fr")
        self.expire()
        fixed.baidu_sk = ""
        self.error(503, fixed.lookup, [row])
        fixed.baidu_sk = "yoursk"
        with patch("adapter.server.upstream", return_value={"status": 302, "message": "private text"}):
            self.error(502, fixed.lookup, [row])
        fixed_amap = server.Adapter(self.db_path, "fake-test-key", provider="amap")
        foreign = copy.deepcopy(AMAP)
        foreign["regeocode"]["addressComponent"].update(country="Japan", province=[])
        row = address(lat="35.65858", lon="139.74543")
        with patch("adapter.server.upstream", return_value=foreign):
            self.error(502, fixed_amap.reverse, row)
        global_amap = server.Adapter(self.db_path, "fake-test-key", provider="amap", amap_region="global")
        with patch("adapter.server.upstream", return_value=foreign) as upstream:
            self.assertEqual(global_amap.reverse(row)["address"]["country"], "Japan")
            self.assertEqual(upstream.call_args.args[-1], "global")
        with patch("adapter.server.upstream", return_value=AMAP) as upstream:
            self.assertEqual(fixed_amap.reverse(row)["osm_id"], -1)
            self.assertEqual(upstream.call_count, 1)

    def test_auto_region_confirmation_and_errors_preserve_independent_evidence(self):
        for lat, lon, country, subdivision in [("37.5665", "126.978", "kr", ""), ("1.3521", "103.8198", "sg", ""),
                                               ("22.3193", "114.1694", "cn", "CN-HK"), ("22.1987", "113.5439", "cn", "CN-MO")]:
            foreign = copy.deepcopy(OSM)
            foreign["address"].update(country_code=country, **{"ISO3166-2-lvl3": subdivision})
            with patch.object(self.adapter, "osm", return_value=foreign), patch("adapter.server.upstream", side_effect=server.AdapterError(504, "Upstream request timed out")) as keyed:
                result = self.adapter.reverse(address(lat=lat, lon=lon))
                self.assertTrue(result["georelay"]["outside_mainland"])
                self.assertEqual(keyed.call_count, 1)
                self.expire()
                self.adapter.reverse(from_response(result))
                self.assertEqual(keyed.call_count, 1)
        self.adapter.key = ""
        mainland = copy.deepcopy(OSM)
        for code in ["cn", "", "?", "china"]:
            mainland["address"]["country_code"] = code
            with patch.object(self.adapter, "osm", return_value=mainland):
                self.error(503, self.adapter.reverse, address())
        self.adapter.key = "fake-test-key"
        with patch.object(self.adapter, "osm", return_value=mainland), patch("adapter.server.upstream", side_effect=server.AdapterError(504, "Upstream request timed out")):
            self.error(504, self.adapter.reverse, address())

    def test_overseas_without_mainland_key_still_requires_public_osm_operator_identity(self):
        self.adapter.key = ""
        row = address(-10001, OSM_LAT, OSM_LON)
        with patch.object(self.adapter, "osm", return_value=OSM) as osm, patch("adapter.server.upstream") as keyed:
            first = self.adapter.reverse(row, "fr")
            self.assertEqual((first["osm_id"], first["lat"], first["lon"]), (-10001, OSM_LAT, OSM_LON))
            self.assertTrue(first["georelay"]["outside_mainland"])
            osm.assert_called_once()
            keyed.assert_not_called()
        self.adapter.user_agent = ""
        self.assertEqual(self.adapter.lookup([row], "fr"), [first])
        self.expire()
        self.error(503, self.adapter.lookup, [from_response(first)], "fr")

    def test_fifty_osm_contexts_expand_verified_sources_and_preserve_request_order(self):
        rows = [address(-i - 1, f"48.{i:06d}", OSM_LON,
                        {"outside_mainland": True, "source_osm_type": "way", "source_osm_id": max(1, i)}) for i in range(50)]
        responses = [{**OSM, "osm_id": i} for i in range(1, 50)]
        with patch.object(self.adapter, "osm", return_value=list(reversed(responses))) as osm:
            result = self.adapter.lookup(list(reversed(rows)), "EN")
            self.assertEqual(osm.call_count, 1)
            self.assertEqual(set(osm.call_args.args[-1].split(",")), {f"W{i}" for i in range(1, 50)})
        self.assertEqual([(body["osm_id"], body["lat"], body["lon"]) for body in result],
                         [(row["osm_id"], row["lat"], row["lon"]) for row in reversed(rows)])
        self.assertTrue(all(body["georelay"]["outside_mainland"] for body in result))

    def test_osm_batch_rejects_missing_duplicate_foreign_and_malformed_items_atomically(self):
        rows = [address(-1, OSM_LAT, OSM_LON, {"outside_mainland": True, "source_osm_type": "way", "source_osm_id": 123}),
                address(-2, "48.85", OSM_LON, {"outside_mainland": True, "source_osm_type": "node", "source_osm_id": 456})]
        second = {**OSM, "osm_id": 456, "osm_type": "node"}
        for payload in [[], [OSM, OSM], [OSM], [OSM, {**second, "osm_id": 999}],
                        [OSM, {**second, "display_name": []}], {"error": "Unable to geocode"}]:
            with patch.object(self.adapter, "osm", return_value=payload):
                self.error(502, self.adapter.lookup, rows, "en")
            with self.adapter.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)

    def test_fixed_osm_batch_mainland_is_source_without_overseas_evidence(self):
        mainland = copy.deepcopy(OSM)
        mainland["address"]["country_code"] = "cn"
        rows = [address(-1, context={"outside_mainland": False, "source_osm_type": "way", "source_osm_id": 123}),
                address(-2, "39.9", context={"outside_mainland": False, "source_osm_type": "way", "source_osm_id": 123})]
        with patch.object(self.adapter, "osm", return_value=[mainland]) as osm:
            result = self.adapter.lookup(rows, "fr", "osm")
            osm.assert_called_once()
        self.assertEqual([body["osm_id"] for body in result], [-1, -2])
        self.assertTrue(all(not body["georelay"]["outside_mainland"] for body in result))
        with patch("adapter.server.upstream", return_value=AMAP) as keyed:
            self.adapter.lookup([from_response(body) for body in result])
            self.assertEqual(keyed.call_count, 2)

    def test_fifty_mainland_refreshes_have_four_workers_and_complete_ordered_results(self):
        rows = [address(-i - 1, f"39.{i:06d}") for i in range(50)]
        self.adapter.lookup_timeout = 5
        self.adapter.baidu_ak, self.adapter.baidu_sk = "yourak", "yoursk"
        for provider, payload in [("amap", AMAP), ("baidu", BAIDU)]:
            active = peak = 0
            lock = threading.Lock()
            def delayed(*args):
                nonlocal active, peak
                with lock:
                    active += 1
                    peak = max(peak, active)
                try:
                    time.sleep(0.035)
                    return payload
                finally:
                    with lock:
                        active -= 1
            with patch("adapter.server.upstream", side_effect=delayed) as upstream:
                result = self.adapter.lookup(list(reversed(rows)), "en", provider)
            self.assertEqual(upstream.call_count, 50)
            self.assertTrue(1 < peak <= 4)
            self.assertEqual([body["osm_id"] for body in result], [row["osm_id"] for row in reversed(rows)])

    def test_lookup_deadline_cancels_queue_and_late_responses_do_not_enter_cache(self):
        rows = [address(-i - 1, f"39.{i:06d}") for i in range(50)]
        self.adapter.lookup_timeout = 0.12
        workers, budgets = [], []
        release = threading.Event()
        def slow(*args):
            workers.append(threading.current_thread())
            budgets.append(args[6])
            release.wait(timeout=2)
            return AMAP
        try:
            with patch("adapter.server.upstream", side_effect=slow), patch.object(self.adapter, "address", wraps=self.adapter.address) as calls:
                started = time.monotonic()
                self.error(504, self.adapter.lookup, rows)
                self.assertLess(time.monotonic() - started, 0.4)
                self.assertEqual(calls.call_count, 4)
        finally:
            release.set()
            for worker in workers:
                worker.join(timeout=1)
                self.assertFalse(worker.is_alive())
        self.assertTrue(all(0 < budget <= self.adapter.lookup_timeout for budget in budgets))
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)

    def test_nonfirst_failure_is_observed_before_slow_first_item(self):
        rows = [address(-i - 1, f"39.{i:06d}") for i in range(50)]
        ready, release = threading.Barrier(4), threading.Event()
        workers = []
        def request(*args):
            workers.append(threading.current_thread())
            if args[2] in {row["lat"] for row in rows[:4]}:
                ready.wait(timeout=1)
            if args[2] == rows[0]["lat"]:
                release.wait(timeout=0.3)
            elif args[2] == rows[1]["lat"]:
                raise server.AdapterError(502, "Upstream request failed")
            else:
                time.sleep(0.005)
            return AMAP
        try:
            with patch("adapter.server.upstream", side_effect=request) as upstream:
                started = time.monotonic()
                self.error(502, self.adapter.lookup, rows, "en", "amap")
                self.assertLess(time.monotonic() - started, 0.25)
                self.assertLessEqual(upstream.call_count, 8)
        finally:
            release.set()
            for worker in set(workers):
                worker.join(timeout=1)
                self.assertFalse(worker.is_alive())

    @patch("adapter.server.upstream", return_value=OSM)
    def test_osm_rate_limit_survives_restart_and_wait_counts_toward_budget(self, upstream):
        starts = []
        def request(*args):
            starts.append(time.monotonic())
            return OSM
        upstream.side_effect = request
        row = address(lat=OSM_LAT, lon=OSM_LON)
        self.adapter.reverse(row)
        restarted = server.Adapter(self.db_path, user_agent=USER_AGENT)
        restarted.reverse(row, "fr")
        self.assertGreaterEqual(starts[1] - starts[0], 0.99)
        restarted.lookup_timeout = 0.1
        started = time.monotonic()
        self.error(504, restarted.lookup, [row], "de")
        self.assertLess(time.monotonic() - started, 0.3)
        self.assertEqual(len(starts), 2)

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_missing_keys_and_upstream_failures_never_become_unknown(self, upstream):
        row = address()
        first = self.adapter.reverse(row)
        self.adapter.key = ""
        self.assertEqual(self.adapter.lookup([row]), [first])
        self.expire()
        mainland = {**OSM, "address": {"country_code": "cn"}}
        with patch.object(self.adapter, "osm", return_value=mainland):
            self.error(503, self.adapter.lookup, [row])
        self.adapter.key = "fake-test-key"
        upstream.side_effect = server.AdapterError(504, "Upstream request timed out")
        with patch.object(self.adapter, "osm", return_value=mainland):
            self.error(504, self.adapter.lookup, [row])
        upstream.side_effect = None
        for payload in [{"status": "0", "info": "private text"}, {"error": "Unable to geocode"}, {"status": "1", "regeocode": []}, []]:
            upstream.return_value = payload
            with patch.object(self.adapter, "osm", return_value=mainland):
                self.error(502, self.adapter.lookup, [row])

    def http(self, url, document=None, endpoint="/v1/reverse", status=200, raw=None, headers=None, method=None):
        data = json.dumps(document).encode() if document is not None else raw
        request = urllib.request.Request(url + endpoint, data=data, method=method,
                                         headers=headers or ({"Content-Type": "application/json"} if data is not None else {}))
        try:
            response = urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            self.assertEqual(response.status, status)
            self.assertEqual(response.headers.get_content_type(), "application/json")
            body = json.load(response)
            if status != 200:
                self.assertNotIn(LAT, json.dumps(body))
                self.assertNotIn("Unable to geocode", json.dumps(body))
            return body

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_http_versioned_protocol_body_validation_and_private_errors(self, upstream):
        document = {"version": 1, "address": address(), "language": "ZH-CN"}
        output = io.StringIO()
        with contextlib.redirect_stderr(output), serving(server.Server(("127.0.0.1", 0), self.adapter)) as url:
            self.assertEqual(self.http(url, endpoint="/health")["storage"], "disposable-cache")
            first = self.http(url, document)
            self.assertEqual(self.http(url, {"version": 1, "addresses": [address()], "language": "zh-cn"}, "/v1/lookup"), [first])
            self.assertEqual(upstream.call_count, 1)
            for invalid in [{**document, "version": True}, {**document, "version": 2}, {**document, "language": LAT + "\n"},
                            {**document, "provider": "auto"}, {**document, "provider": None}, {**document, "unexpected": LAT},
                            {**document, "address": {**address(), "context": {"outside_mainland": False, "source_osm_id": 123}}}]:
                self.http(url, invalid, status=400)
            for raw in [b'{"version":1,"version":1}', b'{"version":NaN}', b'\xff',
                        json.dumps(document).replace('"outside_mainland": false', '"outside_mainland": false, "outside_mainland": false').encode()]:
                self.http(url, raw=raw, status=400)
            self.http(url, raw=b'x' * (server.MAX_REQUEST_BODY + 1), status=413)
            self.http(url, raw=b'{}', headers={"Content-Type": "text/plain"}, status=415)
            self.http(url, raw=b'{}', headers={"Content-Type": "application/json", "Transfer-Encoding": "chunked"}, status=400)
            self.http(url, endpoint="/reverse", status=409)
            self.http(url, endpoint="/reverse?lat=" + LAT + "&lon=" + LON, status=409)
            self.http(url, endpoint="/v1/lookup", status=409)
            self.http(url, document, "/missing", status=404)
            self.http(url, document, "/" + LAT, status=404)
            self.http(url, endpoint="/health?private=" + LAT, status=400)
            self.expire()
            upstream.side_effect = server.AdapterError(504, "Upstream request timed out")
            mainland = {**OSM, "address": {"country_code": "cn"}}
            with patch.object(self.adapter, "osm", return_value=mainland):
                self.http(url, document, status=504)
        self.assertNotIn(LAT, output.getvalue())
        self.assertNotIn("fake-test-key", output.getvalue())
        self.assertNotIn(AMAP["regeocode"]["formatted_address"], output.getvalue())

    def test_http_provider_override_and_health_storage_failures(self):
        self.adapter.baidu_ak, self.adapter.baidu_sk = "yourak", "yoursk"
        with serving(server.Server(("127.0.0.1", 0), self.adapter)) as url:
            with patch("adapter.server.upstream", return_value=BAIDU):
                first = self.http(url, {"version": 1, "address": address(), "language": "", "provider": "baidu"})
                self.assertEqual(first["upstream"]["provider"], "baidu")
            with patch("adapter.server.upstream", return_value=AMAP):
                result = self.http(url, {"version": 1, "addresses": [address()], "language": "", "provider": "amap"}, "/v1/lookup")
                self.assertEqual(result[0]["upstream"]["provider"], "amap")
            with patch.object(self.adapter, "health", side_effect=sqlite3.DatabaseError(LAT)):
                self.assertEqual(self.http(url, endpoint="/health", status=503), {"error": "Local storage unavailable"})

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_online_cache_backup_refuses_legacy_source_and_overwrite(self, upstream):
        self.adapter.reverse(address())
        backup = Path(self.temp.name) / "backup.sqlite3"
        env = {key: value for key, value in os.environ.items() if key != "ADAPTER_DB"}
        env["ADAPTER_CACHE_DB"] = str(self.db_path)
        command = [sys.executable, "-m", "adapter.server", "--backup", str(backup)]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        restored = server.Adapter(backup)
        self.assertEqual(restored.lookup([address(-123)])[0]["osm_id"], -123)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(subprocess.run(command, env=env, capture_output=True).returncode, 1)
        missing = Path(self.temp.name) / "missing.sqlite3"
        env["ADAPTER_CACHE_DB"] = str(self.db_path) + ".missing"
        self.assertEqual(subprocess.run(command[:-1] + [str(missing)], env=env, capture_output=True).returncode, 1)
        self.assertFalse(missing.exists())
        legacy = Path(self.temp.name) / "legacy.sqlite3"
        with contextlib.closing(sqlite3.connect(legacy)) as db, db:
            db.execute("CREATE TABLE identities (id INTEGER)")
        env["ADAPTER_CACHE_DB"] = str(legacy)
        self.assertEqual(subprocess.run(command[:-1] + [str(missing)], env=env, capture_output=True).returncode, 1)
        self.assertFalse(missing.exists())

    @patch("adapter.server.upstream", return_value=AMAP)
    def test_corrupt_cache_is_failure_and_never_supplies_a_candidate_identity(self, upstream):
        row = address()
        original = self.adapter.reverse(row)
        cases = ["{", json.dumps({}), json.dumps({**original, "osm_id": -999}),
                 json.dumps({"display_name": "Unable to geocode", "georelay": {"version": 1, "outside_mainland": False}}),
                 json.dumps({"display_name": "Private text", "georelay": {"version": 1, "outside_mainland": False, "source_osm_id": -1}})]
        for corrupt in cases:
            with self.adapter.connect() as db:
                db.execute("UPDATE cache SET body=?", (corrupt,))
            self.error(503, self.adapter.reverse, address(-2))
        self.assertEqual(upstream.call_count, 1)

    def test_protocol_rejects_unhashable_fields_without_side_effects(self):
        for field, value in [("osm_type", []), ("osm_type", {}), ("osm_id", "-1")]:
            self.error(400, self.adapter.reverse, {**address(), field: value})
        self.error(400, self.adapter.reverse, address(context={"outside_mainland": False, "source_osm_type": [], "source_osm_id": 123}))
        self.error(400, self.adapter.reverse, address(), "", [])
        with self.adapter.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM cache").fetchone()[0], 0)

    def test_http_duplicate_framing_headers_are_rejected_without_logging_body(self):
        output = io.StringIO()
        document = json.dumps({"version": 1, "address": address(), "language": ""}).encode()
        with contextlib.redirect_stderr(output), serving(server.Server(("127.0.0.1", 0), self.adapter)) as url:
            port = urllib.parse.urlsplit(url).port
            for headers, status in [(f"Content-Length: {len(document)}\r\nContent-Length: {len(document)}\r\n", 400),
                                    (f"Content-Length: {len(document)}\r\nContent-Type: application/json\r\n", 415),
                                    ("Content-Length: 0\r\n", 400)]:
                request = ("POST /v1/reverse HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\n" + headers + "\r\n").encode() + document
                with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
                    connection.sendall(request)
                    response = bytearray()
                    while part := connection.recv(65536):
                        response.extend(part)
                self.assertIn(f" {status} ".encode(), bytes(response).split(b"\r\n", 1)[0])
                self.assertNotIn(LAT.encode(), response)
        self.assertEqual(output.getvalue(), "")

    def test_provider_and_secret_configuration_validation(self):
        for config in [{"provider": "unknown"}, {"provider": ""}, {"mainland_provider": "osm"}, {"amap_region": "https://elsewhere.invalid"}]:
            with self.assertRaises(ValueError):
                server.Adapter(self.db_path, **config)
        for provider in ["auto", "", "AMAP", " baidu", "unknown"]:
            self.error(400, self.adapter.reverse, address(), "", provider)
            self.error(400, self.adapter.lookup, [], "", provider)
        secret_file = Path(self.temp.name) / "test-secret"
        secret_file.write_text("example-test-value\n")
        secret_file.chmod(0o600)
        for name in ["AMAP_KEY", "BAIDU_AK", "BAIDU_SK"]:
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(server.secret_env(name), "")
            with patch.dict(os.environ, {name + "_FILE": str(secret_file)}, clear=True):
                self.assertEqual(server.secret_env(name), "example-test-value")
            for values in [{name: "example-test-value", name + "_FILE": str(secret_file)}, {name: "contains whitespace"}, {name: "x" * 513}]:
                with patch.dict(os.environ, values, clear=True):
                    with self.assertRaises(ValueError):
                        server.secret_env(name)
        with patch.dict(os.environ, {"ADAPTER_CACHE_DB": str(self.db_path), "GEOCODER_PROVIDER": "baidu", "MAINLAND_PROVIDER": "baidu",
                                    "BAIDU_AK_FILE": str(secret_file), "BAIDU_SK_FILE": str(secret_file), "AMAP_API_REGION": "global"}, clear=True), \
                patch.object(sys, "argv", ["adapter.server"]), patch("adapter.server.Server") as http:
            server.main()
            configured = http.call_args.args[1]
            self.assertEqual((configured.provider, configured.mainland_provider, configured.amap_region), ("baidu", "baidu", "global"))
            self.assertEqual((configured.baidu_ak, configured.baidu_sk), ("example-test-value", "example-test-value"))


if __name__ == "__main__":
    unittest.main()
