"""Run with python -m adapter.server; only expose port 8080 on a trusted network.

AMAP_KEY or AMAP_KEY_FILE supplies the Web Service key (never both).
NOMINATIM_USER_AGENT must identify the operator for public OSM requests.
ADAPTER_DB defaults to /data/adapter.sqlite3. CACHE_TTL_SECONDS defaults to 86400,
UPSTREAM_TIMEOUT_SECONDS to 8, and LOOKUP_TIMEOUT_SECONDS to 20. No retries.
--backup DEST uses SQLite's online backup API; DEST must not already exist.
"""

import argparse
import contextlib
from decimal import Decimal, InvalidOperation
import fcntl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


AMAP_URL = "https://restapi.amap.com/v3/geocode/regeo"
OSM_URL = "https://nominatim.openstreetmap.org/reverse"
OSM_LOOKUP_URL = "https://nominatim.openstreetmap.org/lookup"
MAINLAND_PROVINCES = frozenset("北京市 天津市 河北省 山西省 内蒙古自治区 辽宁省 吉林省 黑龙江省 上海市 江苏省 浙江省 安徽省 福建省 江西省 山东省 河南省 湖北省 湖南省 广东省 广西壮族自治区 海南省 重庆市 四川省 贵州省 云南省 西藏自治区 陕西省 甘肃省 青海省 宁夏回族自治区 新疆维吾尔自治区".split())
MAX_BODY = 1024 * 1024
MAX_IDS = 50  # TeslaMate Locations.update_addresses/1 batches 50 identities.
MAX_ID = 2**63 - 1


class AdapterError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def coordinate(value, limit):
    """Canonical decimal text without float conversion or Decimal rounding."""
    if not isinstance(value, str) or len(value) > 80 or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,3})?", value
    ):
        raise AdapterError(400, "Invalid coordinates")
    try:
        number = Decimal(value)
        if not number.is_finite() or number.copy_abs() > limit or abs(number.as_tuple().exponent) > 80:
            raise InvalidOperation
    except InvalidOperation:
        raise AdapterError(400, "Invalid coordinates") from None
    if not number:
        return "0"
    value = format(number, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def in_amap_bounds(lat, lon):
    return 72.004 <= float(lon) <= 137.8347 and 0.8293 <= float(lat) <= 55.8271


def gcj02(lat, lon):
    """Return AMap longitude/latitude; keep the stored WGS84 text unchanged."""
    lat, lon = float(lat), float(lon)
    # ponytail: conventional GCJ02 bounding box, not a political border polygon.
    # Add a vetted coverage polygon if border-region support is required.
    if not in_amap_bounds(lat, lon):
        return lon, lat
    x, y = lon - 105, lat - 35
    dlat = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    dlon = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    common = (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    dlat += common + (20 * math.sin(y * math.pi) + 40 * math.sin(y / 3 * math.pi)) * 2 / 3
    dlat += (160 * math.sin(y / 12 * math.pi) + 320 * math.sin(y * math.pi / 30)) * 2 / 3
    dlon += common + (20 * math.sin(x * math.pi) + 40 * math.sin(x / 3 * math.pi)) * 2 / 3
    dlon += (150 * math.sin(x / 12 * math.pi) + 300 * math.sin(x / 30 * math.pi)) * 2 / 3
    rad = math.radians(lat)
    magic = 1 - 0.00669342162296594323 * math.sin(rad) ** 2
    dlat *= 180 / ((6378245 * (1 - 0.00669342162296594323) / magic**1.5) * math.pi)
    dlon *= 180 / ((6378245 / math.sqrt(magic)) * math.cos(rad) * math.pi)
    return lon + dlon, lat + dlat


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def fetch(provider, key, lat, lon, language, user_agent, timeout, osm_ids=None):
    """Called in a disposable process: parent kills DNS/slow-drip overruns."""
    if provider == "amap":
        longitude, latitude = gcj02(lat, lon)
        query = {"key": key, "location": f"{longitude:.8f},{latitude:.8f}",
                 "output": "JSON", "extensions": "all", "radius": "1000"}
        url, headers = AMAP_URL, {}
    elif provider == "osm":
        query = {"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1, "namedetails": 1, "zoom": 19}
        url, headers = OSM_URL, {"User-Agent": user_agent, "Accept-Language": language}
        if osm_ids:
            query.pop("lat")
            query.pop("lon")
            query["osm_ids"] = osm_ids
            url = OSM_LOOKUP_URL
    else:
        raise AdapterError(502, "Invalid upstream provider")
    # No environment proxies or redirects: neither may forward a key elsewhere.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(url + "?" + urllib.parse.urlencode(query), headers=headers)
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise AdapterError(502, "Upstream request failed")
        body = response.read(MAX_BODY + 1)
    if len(body) > MAX_BODY:
        raise AdapterError(502, "Invalid upstream response")
    return json.loads(body)


def upstream(provider, key, lat, lon, language, user_agent, timeout, osm_ids=None):
    """Wall-clock limit includes DNS, headers and complete response body."""
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--fetch"],
            input=json.dumps([provider, key, lat, lon, language, user_agent, timeout, osm_ids]), capture_output=True,
            text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        raise AdapterError(504, "Upstream request timed out") from None
    except OSError:
        raise AdapterError(502, "Upstream request failed") from None
    if result.returncode == 2:
        raise AdapterError(504, "Upstream request timed out")
    if result.returncode != 0:
        raise AdapterError(502, "Upstream request failed")
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        raise AdapterError(502, "Invalid upstream response") from None


def text(value):
    return value.strip() if isinstance(value, str) else ""


def mapping(value):
    return value if isinstance(value, dict) else {}


def mainland_response(payload):
    payload = mapping(payload)
    parts = mapping(mapping(payload.get("regeocode")).get("addressComponent"))
    province, country = text(parts.get("province")), text(parts.get("country"))
    if payload.get("status") != "1" or not province:
        raise AdapterError(502, "Invalid upstream response")
    return province in MAINLAND_PROVINCES and (not country or country.casefold() in {"中国", "中华人民共和国", "china"})


def osm_identity(payload):
    payload = mapping(payload)
    if (type(payload.get("osm_id")) is not int or not 0 < payload["osm_id"] <= MAX_ID
            or payload.get("osm_type") not in {"node", "way", "relation"}):
        raise AdapterError(502, "Invalid upstream response")
    return payload["osm_type"], payload["osm_id"]


def osm_address(payload, identity, lat, lon):
    payload = mapping(payload)
    address = {key: text(value) for key, value in mapping(payload.get("address")).items() if text(value)}
    if "error" in payload or not text(payload.get("display_name")) or not address:
        raise AdapterError(502, "Invalid upstream response")
    osm_identity(payload)
    # Upstream identities are provenance only; the adapter owns stable identity.
    return {
        "osm_id": -identity, "osm_type": "node", "lat": lat, "lon": lon,
        "display_name": payload["display_name"],
        "name": text(payload.get("name")) or text(mapping(payload.get("namedetails")).get("name")),
        "address": address,
        "namedetails": {key: text(value) for key, value in mapping(payload.get("namedetails")).items() if text(value)},
        "licence": "Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright",
        "upstream": {"provider": "osm", "osm_id": payload.get("osm_id"), "osm_type": payload.get("osm_type")},
    }


def require_outside_mainland(payload, error):
    address = mapping(mapping(payload).get("address"))
    country = text(address.get("country_code")).lower()
    special_region = any(key.startswith("ISO3166-2-") and text(value).upper() in {"CN-HK", "CN-MO"}
                         for key, value in address.items())
    if not re.fullmatch("[a-z]{2}", country) or (country == "cn" and not special_region):
        raise error


def remaining(deadline):
    budget = deadline - time.monotonic()
    if budget <= 0:
        raise AdapterError(504, "Lookup request timed out")
    return budget


def nominatim(payload, identity, lat, lon):
    payload = mapping(payload)
    regeo = mapping(payload.get("regeocode"))
    display_name = text(regeo.get("formatted_address"))
    if payload.get("status") != "1" or not display_name:
        raise AdapterError(502, "Invalid upstream response")
    parts = mapping(regeo.get("addressComponent"))
    street = mapping(parts.get("streetNumber"))
    province = text(parts.get("province"))
    neighbourhood = text(mapping(parts.get("neighborhood")).get("name"))
    aois, pois = regeo.get("aois"), regeo.get("pois")
    aoi_name = text(mapping(aois[0]).get("name")) if isinstance(aois, list) and aois else ""
    poi_name = text(mapping(pois[0]).get("name")) if isinstance(pois, list) and pois else ""
    name = (aoi_name or poi_name or text(mapping(parts.get("building")).get("name"))
            or neighbourhood or text(street.get("street")))
    city = text(parts.get("city"))
    if not city and province in {"北京市", "上海市", "天津市", "重庆市"}:
        city = province
    address = {
        "road": text(street.get("street")), "house_number": text(street.get("number")),
        "city": city, "county": text(parts.get("district")), "state": province,
        "neighbourhood": neighbourhood or text(parts.get("township")),
        "country": "中国", "country_code": "cn",
    }
    return {
        "osm_type": "node", "osm_id": -identity, "lat": lat, "lon": lon,
        "display_name": display_name, "name": name or display_name,
        "address": {key: value for key, value in address.items() if value},
        "namedetails": {"name": name or display_name},
    }


class Adapter:
    def __init__(self, path, key="", ttl=86400, timeout=8, lookup_timeout=20, user_agent=""):
        self.path, self.key = str(path), key
        self.ttl, self.timeout, self.lookup_timeout = ttl, timeout, lookup_timeout
        self.user_agent = user_agent
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lat TEXT NOT NULL, lon TEXT NOT NULL,
                    source_osm_id INTEGER, source_osm_type TEXT, UNIQUE(lat, lon)
                );
                CREATE TABLE IF NOT EXISTS cache (
                    identity INTEGER NOT NULL REFERENCES identities(id),
                    language TEXT NOT NULL, expires REAL NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(identity, language)
                );
            """)
            # Preserve IDs from an earlier schema; the map must never be rebuilt.
            db.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in db.execute("PRAGMA table_info(identities)")}
            for name, kind in [("source_osm_id", "INTEGER"), ("source_osm_type", "TEXT")]:
                if name not in columns:
                    db.execute(f"ALTER TABLE identities ADD COLUMN {name} {kind}")

    @contextlib.contextmanager
    def connect(self, deadline=None):
        timeout = min(1, remaining(deadline)) if deadline else 1
        with contextlib.closing(sqlite3.connect(self.path, timeout=timeout)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db

    def health(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("SELECT id FROM identities LIMIT 1").fetchone()
        return {"status": "ok"}

    def reverse(self, lat, lon, language=""):
        deadline = time.monotonic() + min(25, 2 * self.timeout + 1)
        lat, lon = coordinate(lat, 90), coordinate(lon, 180)
        with self.connect(deadline) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM identities WHERE lat=? AND lon=?", (lat, lon)).fetchone()
            if row is None:
                identity = db.execute("INSERT INTO identities(lat,lon) VALUES(?,?)", (lat, lon)).lastrowid
            else:
                identity = row[0]
        return self.address(identity, lat, lon, language, deadline)

    def lookup(self, osm_ids, language=""):
        deadline = time.monotonic() + self.lookup_timeout
        if osm_ids == "":
            return []  # Official details([]) can send an empty list.
        ids = osm_ids.split(",")
        if len(ids) > MAX_IDS:
            raise AdapterError(400, "Too many identities")
        identities = []
        for value in ids:
            if re.fullmatch(r"[NWR][0-9]+", value) or re.fullmatch(r"[WR]-[0-9]+", value):
                raise AdapterError(422, "Unsupported identity")
            if not re.fullmatch(r"N-[1-9][0-9]{0,18}", value) or int(value[2:]) > MAX_ID:
                raise AdapterError(400, "Invalid identity")
            identities.append(int(value[2:]))
        rows = []
        with self.connect(deadline) as db:
            for identity in dict.fromkeys(identities):
                row = db.execute("SELECT lat,lon,source_osm_type,source_osm_id FROM identities WHERE id=?", (identity,)).fetchone()
                if row is None:
                    raise AdapterError(404, "Identity not found")
                rows.append((identity, *row))
        self.refresh_osm_batch(rows, language, deadline)
        return [self.address(*row[:3], language, deadline) for row in rows]

    def refresh_osm_batch(self, rows, language, deadline):
        stale = {}
        with self.connect(deadline) as db:
            for identity, lat, lon, source_type, source_id in rows:
                if source_id is None:
                    continue
                cached = db.execute("SELECT expires FROM cache WHERE identity=? AND language=?", (identity, language)).fetchone()
                if cached and cached[0] > time.time():
                    continue
                stale.setdefault((source_type, source_id), []).append((identity, lat, lon))
        if not stale:
            return
        ids = ",".join(kind[0].upper() + str(identity) for kind, identity in stale)
        payload = self.osm("", "", language, deadline, ids)
        if not isinstance(payload, list) or len(payload) != len(stale):
            raise AdapterError(502, "Invalid upstream response")
        found = {}
        for item in payload:
            source = osm_identity(item)
            if source not in stale or source in found:
                raise AdapterError(502, "Unexpected upstream identity")
            require_outside_mainland(item, AdapterError(502, "Unexpected upstream coverage"))
            found[source] = item
        bodies = [osm_address(found[source], *row) for source, local_rows in stale.items() for row in local_rows]
        with self.connect(deadline) as db:
            for body in bodies:
                self.cache_result(db, body, language)

    def address(self, identity, lat, lon, language, deadline):
        with self.connect(deadline) as db:
            cached = db.execute("SELECT expires,body FROM cache WHERE identity=? AND language=?", (identity, language)).fetchone()
            source = db.execute("SELECT source_osm_id FROM identities WHERE id=?", (identity,)).fetchone()[0]
        remaining(deadline)
        if cached and cached[0] > time.time():
            return json.loads(cached[1])
        body = None
        error = AdapterError(502, "Unexpected upstream coverage")
        if in_amap_bounds(lat, lon) and source is None:
            try:
                if not self.key:
                    raise AdapterError(503, "AMap key is not configured")
                payload = upstream("amap", self.key, lat, lon, language, "", min(self.timeout, remaining(deadline)))
                if mainland_response(payload):
                    body = nominatim(payload, identity, lat, lon)
            except AdapterError as exc:
                error = exc
        if body is None:
            payload = self.osm(lat, lon, language, deadline)
            require_outside_mainland(payload, error)
            body = osm_address(payload, identity, lat, lon)
        remaining(deadline)
        with self.connect(deadline) as db:
            self.cache_result(db, body, language)
        return body

    def cache_result(self, db, body, language):
        db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?)", (
            -body["osm_id"], language, time.time() + self.ttl, json.dumps(body, ensure_ascii=False),
        ))
        source = body.get("upstream", {})
        db.execute("UPDATE identities SET source_osm_type=?, source_osm_id=? WHERE id=?", (
            source.get("osm_type"), source.get("osm_id"), -body["osm_id"],
        ))

    def osm(self, lat, lon, language, deadline, osm_ids=None):
        if not self.user_agent:
            raise AdapterError(503, "Nominatim user agent is not configured")
        # A local-volume flock serializes processes as well as HTTP worker threads.
        # Wait one second AFTER completion, stricter than OSM's 1 request/sec.
        with os.fdopen(os.open(self.path + ".osm.lock", os.O_RDWR | os.O_CREAT, 0o600), "r+") as lock:
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(min(0.05, remaining(deadline)))
            try:
                completed = float(lock.read() or "0")
                wait = max(0, completed + 1 - time.time())
                if wait >= remaining(deadline):
                    raise AdapterError(504, "Lookup request timed out")
                time.sleep(wait)
                try:
                    return upstream("osm", "", lat, lon, language, self.user_agent,
                                    min(self.timeout, remaining(deadline)), osm_ids)
                finally:
                    lock.seek(0)
                    lock.truncate()
                    lock.write(str(time.time()))
                    lock.flush()
                    os.fsync(lock.fileno())
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)


class Handler(BaseHTTPRequestHandler):
    server_version = "AMapAdapter"
    sys_version = ""

    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self, *args):
        pass  # Access/error URLs contain precise coordinates; never log them.

    def send_error(self, code, message=None, explain=None):
        self.respond(code, {"error": "Invalid HTTP request"})

    def respond(self, status, body):
        encoded = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def do_GET(self):
        try:
            if len(self.path) > 4096:
                raise AdapterError(414, "Request is too long")
            url = urllib.parse.urlsplit(self.path)
            if url.scheme or url.netloc or url.fragment:
                raise AdapterError(400, "Invalid request target")
            params = urllib.parse.parse_qs(url.query, keep_blank_values=True, max_num_fields=20)
            if any(len(values) != 1 for values in params.values()):
                raise AdapterError(400, "Duplicate query parameter")
            params = {key: values[0] for key, values in params.items()}
            language = self.headers.get("Accept-Language", "").strip().lower()
            if len(language) > 128 or any(ord(char) < 32 or ord(char) > 126 for char in language):
                raise AdapterError(400, "Invalid language header")
            if params.get("format", "jsonv2") not in {"json", "jsonv2"}:
                raise AdapterError(400, "Unsupported response format")
            if url.path == "/health":
                body = self.server.adapter.health()
            elif url.path == "/reverse":
                body = self.server.adapter.reverse(params.get("lat"), params.get("lon"), language)
            elif url.path == "/lookup":
                if "osm_ids" not in params:
                    raise AdapterError(400, "Missing identities")
                body = self.server.adapter.lookup(params["osm_ids"], language)
            else:
                raise AdapterError(404, "Endpoint not found")
            self.respond(200, body)
        except AdapterError as exc:
            self.respond(exc.status, {"error": str(exc)})
        except ValueError:
            self.respond(400, {"error": "Invalid request"})
        except sqlite3.Error:
            self.respond(503, {"error": "Local storage unavailable"})


class Server(ThreadingHTTPServer):
    def __init__(self, address, adapter):
        self.adapter = adapter
        super().__init__(address, Handler)

    def handle_error(self, request, client_address):
        # Do not let socket/SQLite/urllib exception tracebacks expose locations.
        print("Request failed", file=sys.stderr)


def number_env(name, default, maximum):
    try:
        number = float(os.environ.get(name, default))
        if not 0 < number <= maximum:
            raise ValueError
        return number
    except ValueError:
        raise ValueError("Invalid " + name) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", metavar="DEST")
    args = parser.parse_args()
    os.umask(0o077)
    path = os.environ.get("ADAPTER_DB", "/data/adapter.sqlite3")
    if args.backup:
        # Refuse overwrite and source creation: a typo must not create a fake backup.
        with contextlib.closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as source:
            source.execute("SELECT id FROM identities LIMIT 1").fetchone()
            with open(args.backup, "xb"):
                pass
            with contextlib.closing(sqlite3.connect(args.backup)) as destination:
                source.backup(destination)
        return
    key, key_file = os.environ.get("AMAP_KEY", ""), os.environ.get("AMAP_KEY_FILE", "")
    if key and key_file:
        raise ValueError("Set only one AMap key source")
    if key_file:
        key = Path(key_file).read_text().strip()
    if len(key) > 512 or any(char.isspace() for char in key):
        raise ValueError("Invalid AMap key configuration")
    user_agent = os.environ.get("NOMINATIM_USER_AGENT", "").strip()
    if len(user_agent) > 256 or any(ord(char) < 32 or ord(char) > 126 for char in user_agent):
        raise ValueError("Invalid Nominatim user agent")
    adapter = Adapter(path, key, number_env("CACHE_TTL_SECONDS", "86400", 31536000),
                      number_env("UPSTREAM_TIMEOUT_SECONDS", "8", 20),
                      number_env("LOOKUP_TIMEOUT_SECONDS", "20", 25), user_agent)
    with Server(("0.0.0.0", 8080), adapter) as server:
        server.serve_forever()


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["--fetch"]:
            print(json.dumps(fetch(*json.load(sys.stdin)), ensure_ascii=False))
        else:
            main()
    except (TimeoutError, urllib.error.URLError) as exc:
        # Nothing from the URL or the underlying exception reaches stderr.
        sys.exit(2 if isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError) else 1)
    except Exception:
        print("Adapter operation failed", file=sys.stderr)
        sys.exit(1)
