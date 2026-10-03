"""Run with python -m adapter.server; only expose port 8080 on a trusted network.

AMAP_KEY or AMAP_KEY_FILE supplies the Web Service key (never both).
BAIDU_AK and BAIDU_SK each support a mutually exclusive _FILE source.
GEOCODER_PROVIDER defaults to auto; MAINLAND_PROVIDER defaults to amap.
AMAP_API_REGION=mainland (default) or global selects the AMap API and datum.
NOMINATIM_USER_AGENT must identify the operator for public OSM requests.
ADAPTER_CACHE_DB defaults to /data/cache.sqlite3; legacy ADAPTER_DB is rejected. CACHE_TTL_SECONDS defaults to 86400,
UPSTREAM_TIMEOUT_SECONDS to 8, and LOOKUP_TIMEOUT_SECONDS to 20. No retries.
--backup DEST uses SQLite's online backup API; DEST must not already exist.
"""

import argparse
import concurrent.futures
import contextlib
from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


AMAP_URL = "https://restapi.amap.com/v3/geocode/regeo"
AMAP_GLOBAL_URL = "https://sg-restapi.opnavi.com/v3/geocode/regeo"
BAIDU_URL = "https://api.map.baidu.com/reverse_geocoding/v3/"
OSM_URL = "https://nominatim.openstreetmap.org/reverse"
OSM_LOOKUP_URL = "https://nominatim.openstreetmap.org/lookup"
MAINLAND_PROVINCES = frozenset("北京市 天津市 河北省 山西省 内蒙古自治区 辽宁省 吉林省 黑龙江省 上海市 江苏省 浙江省 安徽省 福建省 江西省 山东省 河南省 湖北省 湖南省 广东省 广西壮族自治区 海南省 重庆市 四川省 贵州省 云南省 西藏自治区 陕西省 甘肃省 青海省 宁夏回族自治区 新疆维吾尔自治区".split())
SPECIAL_REGIONS = frozenset({"香港特别行政区", "澳门特别行政区", "台湾省", "香港", "澳门", "台湾"})
CHINA_NAMES = frozenset({"中国", "中华人民共和国", "china"})
MAX_BODY = 1024 * 1024
MAX_IDS = 50  # TeslaMate Locations.update_addresses/1 batches 50 identities.
MAX_ID = 2**63 - 1
MAX_REQUEST_BODY = 65536
CACHE_CLEANUP_INTERVAL = 60
CACHE_CLEANUP_LIMIT = 500


class AdapterError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def coordinate(value, limit):
    """Canonical decimal text without float conversion or Decimal rounding."""
    if not isinstance(value, str) or len(value) > 2050 or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,4})?", value
    ):
        raise AdapterError(400, "Invalid coordinates")
    try:
        number = Decimal(value)
        if not number.is_finite() or number.copy_abs() > limit or abs(number.as_tuple().exponent) > 1024 or len(number.as_tuple().digits) > 1024:
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


def baidu_sn(path, query, sk):
    encoded = urllib.parse.quote_plus(path + "?" + query + sk, safe="")
    return hashlib.md5(encoded.encode("utf-8")).hexdigest()


def fetch(provider, key, lat, lon, language, user_agent, timeout, osm_ids=None,
          baidu_sk="", amap_region="mainland"):
    """Called in a disposable process: parent kills DNS/slow-drip overruns."""
    if provider == "amap":
        if amap_region not in {"mainland", "global"}:
            raise AdapterError(502, "Invalid AMap API region")
        longitude, latitude = gcj02(lat, lon) if amap_region == "mainland" else (lon, lat)
        location = f"{longitude:.8f},{latitude:.8f}" if amap_region == "mainland" else f"{longitude},{latitude}"
        query = {"key": key, "location": location,
                 "output": "JSON", "extensions": "all", "radius": "1000"}
        url, headers = (AMAP_URL if amap_region == "mainland" else AMAP_GLOBAL_URL), {}
    elif provider == "baidu":
        query = {"ak": key, "location": f"{lat},{lon}", "coordtype": "wgs84ll",
                 "output": "json", "extensions_poi": "1"}
        url, headers = BAIDU_URL, {}
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
    query = urllib.parse.urlencode(query)
    if provider == "baidu":
        query += "&sn=" + baidu_sn(urllib.parse.urlsplit(url).path, query, baidu_sk)
    request = urllib.request.Request(url + "?" + query, headers=headers)
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise AdapterError(502, "Upstream request failed")
        body = response.read(MAX_BODY + 1)
    if len(body) > MAX_BODY:
        raise AdapterError(502, "Invalid upstream response")
    return json.loads(body)


def upstream(provider, key, lat, lon, language, user_agent, timeout, osm_ids=None,
             baidu_sk="", amap_region="mainland"):
    """Wall-clock limit includes DNS, headers and complete response body."""
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--fetch"],
            input=json.dumps([provider, key, lat, lon, language, user_agent, timeout, osm_ids,
                              baidu_sk, amap_region]), capture_output=True,
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


def mainland_response(payload, provider="amap"):
    payload = mapping(payload)
    if provider == "baidu":
        result = mapping(payload.get("result"))
        valid = type(payload.get("status")) is int and payload["status"] == 0
    else:
        result = mapping(payload.get("regeocode"))
        valid = payload.get("status") == "1"
    parts = mapping(result.get("addressComponent"))
    province, country = text(parts.get("province")), text(parts.get("country"))
    code = text(parts.get("country_code_iso2")).lower() if provider == "baidu" else ""
    if not valid or not text(result.get("formatted_address")):
        raise AdapterError(502, "Invalid upstream response")
    if (code and re.fullmatch("[a-z]{2}", code) and code != "cn") or (country and country.casefold() not in CHINA_NAMES):
        return False
    if province in MAINLAND_PROVINCES and (not country or country.casefold() in CHINA_NAMES) and code in {"", "cn"}:
        return True
    if province in SPECIAL_REGIONS:
        return False
    raise AdapterError(502, "Unexpected upstream coverage")


def osm_identity(payload):
    payload = mapping(payload)
    if (type(payload.get("osm_id")) is not int or not 0 < payload["osm_id"] <= MAX_ID
            or payload.get("osm_type") not in {"node", "way", "relation"}):
        raise AdapterError(502, "Invalid upstream response")
    return payload["osm_type"], payload["osm_id"]


def osm_address(payload, identity, lat, lon):
    payload = mapping(payload)
    address = {key: text(value) for key, value in mapping(payload.get("address")).items() if text(value)}
    if "error" in payload or text(payload.get("display_name")) in {"", "Unable to geocode"} or not address:
        raise AdapterError(502, "Invalid upstream response")
    osm_identity(payload)
    # Upstream identities are provenance only; PostgreSQL owns stable identity.
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
    if payload.get("status") != "1" or display_name in {"", "Unable to geocode"}:
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
        "country": text(parts.get("country")),
    }
    if address["country"].casefold() in CHINA_NAMES and province in MAINLAND_PROVINCES:
        address["country_code"] = "cn"
    return {
        "osm_type": "node", "osm_id": -identity, "lat": lat, "lon": lon,
        "display_name": display_name, "name": name or display_name,
        "address": {key: value for key, value in address.items() if value},
        "namedetails": {"name": name or display_name},
        "upstream": {"provider": "amap"},
    }


def baidu_address(payload, identity, lat, lon):
    payload = mapping(payload)
    result = mapping(payload.get("result"))
    display_name = text(result.get("formatted_address"))
    if type(payload.get("status")) is not int or payload["status"] != 0 or display_name in {"", "Unable to geocode"}:
        raise AdapterError(502, "Invalid upstream response")
    parts = mapping(result.get("addressComponent"))
    regions, pois = result.get("poiRegions"), result.get("pois")
    region_name = text(mapping(regions[0]).get("name")) if isinstance(regions, list) and regions else ""
    poi_name = text(mapping(pois[0]).get("name")) if isinstance(pois, list) and pois else ""
    name = region_name or poi_name or text(parts.get("street")) or display_name
    province, city = text(parts.get("province")), text(parts.get("city"))
    if not city and province in {"北京市", "上海市", "天津市", "重庆市"}:
        city = province
    address = {
        "road": text(parts.get("street")), "house_number": text(parts.get("street_number")),
        "city": city, "county": text(parts.get("district")), "state": province,
        "neighbourhood": text(parts.get("town")), "country": text(parts.get("country")),
    }
    code = text(parts.get("country_code_iso2")).lower()
    if re.fullmatch("[a-z]{2}", code):
        address["country_code"] = code
    return {
        "osm_type": "node", "osm_id": -identity, "lat": lat, "lon": lon,
        "display_name": display_name, "name": name, "namedetails": {"name": name},
        "address": {key: value for key, value in address.items() if value},
        "upstream": {"provider": "baidu"},
    }


def language_value(value):
    if not isinstance(value, str) or len(value) > 128 or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise AdapterError(400, "Invalid language")
    return value.strip().lower()


def request_address(value, allow_positive=False):
    if not isinstance(value, dict) or set(value) - {"osm_id", "osm_type", "lat", "lon", "context"}:
        raise AdapterError(400, "Invalid address")
    identity, kind = value.get("osm_id"), value.get("osm_type")
    if type(identity) is not int or not 0 < abs(identity) <= MAX_ID or kind not in ("node", "way", "relation"):
        raise AdapterError(400, "Invalid identity")
    if identity > 0:
        if not allow_positive:
            raise AdapterError(422, "Unsupported identity")
        # Historical positive identities cannot be treated as trusted OSM sources.
        return None
    if kind != "node":
        raise AdapterError(422, "Unsupported identity")
    if set(value) != {"osm_id", "osm_type", "lat", "lon", "context"}:
        raise AdapterError(400, "Missing address context")
    lat, lon = coordinate(value["lat"], 90), coordinate(value["lon"], 180)
    if lat != value["lat"] or lon != value["lon"]:
        raise AdapterError(400, "Coordinates must be canonical")
    context = value["context"]
    if (not isinstance(context, dict) or set(context) - {"source_osm_type", "source_osm_id", "outside_mainland"}
            or type(context.get("outside_mainland")) is not bool):
        raise AdapterError(400, "Invalid address context")
    source_type, source_id = context.get("source_osm_type"), context.get("source_osm_id")
    if "source_osm_type" in context or "source_osm_id" in context:
        if (source_type not in ("node", "way", "relation") or type(source_id) is not int
                or not 0 < source_id <= MAX_ID):
            raise AdapterError(400, "Invalid source identity")
    return {"osm_id": identity, "osm_type": "node", "lat": lat, "lon": lon, "context": dict(context)}


def request_document(value, endpoint):
    field = "address" if endpoint == "/v1/reverse" else "addresses"
    if (not isinstance(value, dict) or set(value) - {"version", field, "language", "provider"}
            or not {"version", field, "language"} <= set(value)):
        raise AdapterError(400, "Invalid protocol request")
    if type(value["version"]) is not int or value["version"] != 1:
        raise AdapterError(400, "Unsupported protocol version")
    if "provider" in value and value["provider"] not in ("amap", "baidu", "osm"):
        raise AdapterError(400, "Invalid provider")
    language = language_value(value["language"])
    return value[field], language, value.get("provider")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AdapterError(400, "Duplicate JSON field")
        result[key] = value
    return result


def require_cache_schema(db):
    # Inspect table names only: never read or migrate permanent legacy records.
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "identities" in tables:
        raise ValueError("Legacy identity database must be archived separately")
    if tables - {"cache"}:
        raise ValueError("Invalid cache database schema")
    if "cache" in tables:
        columns = {row[1] for row in db.execute("PRAGMA table_info(cache)")}
        if columns != {"cache_key", "language", "policy", "expires", "body"}:
            raise ValueError("Invalid cache database schema")
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("Unsupported cache database version")
    return "cache" in tables


class Adapter:
    def __init__(self, path, key="", ttl=86400, timeout=8, lookup_timeout=20, user_agent="",
                 provider="auto", mainland_provider="amap", baidu_ak="", baidu_sk="", amap_region="mainland"):
        if provider not in {"auto", "amap", "baidu", "osm"} or mainland_provider not in {"amap", "baidu"}:
            raise ValueError("Invalid geocoder provider configuration")
        if amap_region not in {"mainland", "global"}:
            raise ValueError("Invalid AMap API region configuration")
        self.path, self.key = str(path), key
        self.ttl, self.timeout, self.lookup_timeout = ttl, timeout, lookup_timeout
        self.user_agent = user_agent
        self.provider, self.mainland_provider = provider, mainland_provider
        self.baidu_ak, self.baidu_sk = baidu_ak, baidu_sk
        self.amap_region = amap_region
        self._cleanup_lock, self._next_cleanup = threading.Lock(), 0
        self._osm_started = time.time()
        if Path(path).exists():
            with contextlib.closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
                require_cache_schema(db)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            require_cache_schema(db)
            db.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY, language TEXT NOT NULL, policy TEXT NOT NULL,
                    expires REAL NOT NULL, body TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS cache_expires_index ON cache(expires)")
            db.execute("PRAGMA user_version=1")

    @contextlib.contextmanager
    def connect(self, deadline=None):
        timeout = min(1, remaining(deadline)) if deadline else 1
        with contextlib.closing(sqlite3.connect(self.path, timeout=timeout)) as db:
            with db:
                yield db

    def health(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                valid = require_cache_schema(db)
            except ValueError:
                raise AdapterError(503, "Invalid cache database schema") from None
            if not valid:
                raise sqlite3.DatabaseError("Cache is unavailable")
            db.execute("SELECT cache_key FROM cache LIMIT 1").fetchone()
        return {"status": "ok", "protocol": 1, "storage": "disposable-cache"}

    def cleanup(self, deadline):
        if time.monotonic() < self._next_cleanup or not self._cleanup_lock.acquire(blocking=False):
            return
        try:
            if time.monotonic() < self._next_cleanup:
                return
            with self.connect(deadline) as db:
                db.execute("DELETE FROM cache WHERE cache_key IN (SELECT cache_key FROM cache WHERE expires<=? LIMIT ?)",
                           (time.time(), CACHE_CLEANUP_LIMIT))
            self._next_cleanup = time.monotonic() + CACHE_CLEANUP_INTERVAL
        finally:
            self._cleanup_lock.release()

    def policy(self, provider):
        if provider is None:
            provider = self.provider
        elif provider not in ("amap", "baidu", "osm"):
            raise AdapterError(400, "Invalid provider")
        policy = "auto:" + self.mainland_provider if provider == "auto" else provider
        return policy + ":global" if policy.endswith("amap") and self.amap_region == "global" else policy

    def cache_key(self, address, language, policy):
        # Candidate identity deliberately excluded; all routing evidence included.
        return json.dumps([address["lat"], address["lon"], language, policy, address["context"]], sort_keys=True, separators=(",", ":"))

    def reverse(self, address, language="", provider=None):
        policy, language = self.policy(provider), language_value(language)
        address = request_address(address)
        deadline = time.monotonic() + min(25, 2 * self.timeout + 1)
        self.cleanup(deadline)
        return self.address(address, language, deadline, policy)

    def lookup(self, addresses, language="", provider=None):
        policy, language = self.policy(provider), language_value(language)
        deadline = time.monotonic() + self.lookup_timeout
        if not isinstance(addresses, list) or len(addresses) > MAX_IDS:
            raise AdapterError(400, "Invalid address batch")
        rows = []
        identities = set()
        for value in addresses:
            address = request_address(value, allow_positive=True)
            if address is None:
                continue
            if address["osm_id"] in identities:
                raise AdapterError(400, "Duplicate identity")
            identities.add(address["osm_id"])
            rows.append(address)
        if not rows:
            return []
        self.cleanup(deadline)
        self.refresh_osm_batch(rows, language, deadline, policy)
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        try:
            futures = [pool.submit(self.address, row, language, deadline, policy) for row in rows]
            done, pending = concurrent.futures.wait(
                futures, timeout=remaining(deadline), return_when=concurrent.futures.FIRST_EXCEPTION,
            )
            for future in done:
                future.result()
            if pending:
                raise concurrent.futures.TimeoutError
            remaining(deadline)
            return [future.result() for future in futures]
        except concurrent.futures.TimeoutError:
            raise AdapterError(504, "Lookup request timed out") from None
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def refresh_osm_batch(self, rows, language, deadline, policy):
        if policy != "osm" and not policy.startswith("auto:"):
            return
        stale = {}
        with self.connect(deadline) as db:
            for row in rows:
                context = row["context"]
                if "source_osm_id" not in context or (policy != "osm" and not context["outside_mainland"]):
                    continue
                cached = db.execute("SELECT expires FROM cache WHERE cache_key=?", (self.cache_key(row, language, policy),)).fetchone()
                if cached and cached[0] > time.time():
                    continue
                source = context["source_osm_type"], context["source_osm_id"]
                stale.setdefault(source, []).append(row)
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
            if policy != "osm":
                require_outside_mainland(item, AdapterError(502, "Unexpected upstream coverage"))
            found[source] = item
        # Validate the entire upstream set before storing any batch result.
        bodies = [(row, self.template(osm_address(found[source], 0, row["lat"], row["lon"]), row, policy))
                  for source, local_rows in stale.items() for row in local_rows]
        remaining(deadline)
        with self.connect(deadline) as db:
            for row, body in bodies:
                self.cache_result(db, row, body, language, policy)
            remaining(deadline)

    def keyed_payload(self, provider, lat, lon, language, deadline):
        timeout = min(self.timeout, remaining(deadline))
        if provider == "amap":
            if not self.key:
                raise AdapterError(503, "AMap key is not configured")
            if self.amap_region == "global":
                return upstream("amap", self.key, lat, lon, language, "", timeout, None, "", "global")
            return upstream("amap", self.key, lat, lon, language, "", timeout)
        if not self.baidu_ak or not self.baidu_sk:
            raise AdapterError(503, "Baidu credentials are not configured")
        return upstream("baidu", self.baidu_ak, lat, lon, language, "", timeout, None, self.baidu_sk)

    def response(self, template, address):
        return {**template, "osm_id": address["osm_id"], "osm_type": "node", "lat": address["lat"], "lon": address["lon"]}

    def template(self, body, address, policy):
        body = {key: value for key, value in body.items() if key not in {"osm_id", "osm_type", "lat", "lon"}}
        context = {"version": 1, **address["context"]}
        source = body.get("upstream", {})
        if source.get("provider") == "osm":
            context.update(source_osm_type=source["osm_type"], source_osm_id=source["osm_id"])
            if policy.startswith("auto:"):
                context["outside_mainland"] = True
        body["georelay"] = context
        return body

    def address(self, row, language, deadline, policy):
        lat, lon, outside = row["lat"], row["lon"], row["context"]["outside_mainland"]
        cache_key = self.cache_key(row, language, policy)
        with self.connect(deadline) as db:
            cached = db.execute("SELECT expires,body FROM cache WHERE cache_key=?", (cache_key,)).fetchone()
        remaining(deadline)
        if cached and cached[0] > time.time():
            try:
                template = json.loads(cached[1])
                if (not isinstance(template, dict) or any(key in template for key in ("osm_id", "osm_type", "lat", "lon"))
                        or text(template.get("display_name")) in {"", "Unable to geocode"}
                        or not isinstance(template.get("georelay"), dict)
                        or type(template["georelay"].get("version")) is not int
                        or template["georelay"]["version"] != 1
                        or type(template["georelay"].get("outside_mainland")) is not bool):
                    raise ValueError
                cached_context = {key: value for key, value in template["georelay"].items() if key != "version"}
                request_address({**row, "context": cached_context})
                if row["context"]["outside_mainland"] and not cached_context["outside_mainland"]:
                    raise ValueError
            except (AdapterError, ValueError, TypeError):
                raise AdapterError(503, "Invalid cache data") from None
            return self.response(template, row)
        if policy == "osm":
            payload = self.osm(lat, lon, language, deadline)
            body = osm_address(payload, 0, lat, lon)
        elif not policy.startswith("auto:"):
            provider = policy.split(":")[0]
            payload = self.keyed_payload(provider, lat, lon, language, deadline)
            if provider == "amap" and self.amap_region == "mainland" and not mainland_response(payload):
                raise AdapterError(502, "Unexpected upstream coverage")
            body = (nominatim if provider == "amap" else baidu_address)(payload, 0, lat, lon)
        else:
            body = None
            provider = policy.split(":")[1]
            error = AdapterError(502, "Unexpected upstream coverage")
            if in_amap_bounds(lat, lon) and not outside:
                try:
                    payload = self.keyed_payload(provider, lat, lon, language, deadline)
                    if mainland_response(payload, provider):
                        body = (nominatim if provider == "amap" else baidu_address)(payload, 0, lat, lon)
                except AdapterError as exc:
                    error = exc
            if body is None:
                payload = self.osm(lat, lon, language, deadline)
                require_outside_mainland(payload, error)
                body = osm_address(payload, 0, lat, lon)
        remaining(deadline)
        body = self.template(body, row, policy)
        with self.connect(deadline) as db:
            self.cache_result(db, row, body, language, policy)
            remaining(deadline)
        remaining(deadline)
        return self.response(body, row)

    def cache_result(self, db, row, body, language, policy):
        db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?)", (
            self.cache_key(row, language, policy), language, policy, time.time() + self.ttl, json.dumps(body, ensure_ascii=False),
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
                try:
                    completed = float(lock.read() or "0")
                except ValueError:
                    raise AdapterError(503, "Invalid rate limit state") from None
                if not math.isfinite(completed):
                    raise AdapterError(503, "Invalid rate limit state")
                completed = max(completed, self._osm_started)
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
    server_version = "GeoRelayAdapter"
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

    def target(self):
        if len(self.path) > 4096:
            raise AdapterError(414, "Request is too long")
        url = urllib.parse.urlsplit(self.path)
        if url.path in {"/reverse", "/lookup"}:
            raise AdapterError(409, "Application-owned protocol required")
        if url.scheme or url.netloc or url.fragment or url.query:
            raise AdapterError(400, "Invalid request target")
        return url.path

    def handle_request(self, post=False):
        try:
            endpoint = self.target()
            if not post:
                if endpoint in {"/reverse", "/lookup", "/v1/reverse", "/v1/lookup"}:
                    raise AdapterError(409, "Application-owned protocol required")
                if endpoint != "/health":
                    raise AdapterError(404, "Endpoint not found")
                body = self.server.adapter.health()
            else:
                if endpoint in {"/reverse", "/lookup"}:
                    raise AdapterError(409, "Application-owned protocol required")
                if endpoint not in {"/v1/reverse", "/v1/lookup"}:
                    raise AdapterError(404, "Endpoint not found")
                if self.headers.get("Transfer-Encoding") is not None:
                    raise AdapterError(400, "Unsupported request encoding")
                lengths = self.headers.get_all("Content-Length", [])
                if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,9}", lengths[0]):
                    raise AdapterError(400, "Invalid content length")
                length = int(lengths[0])
                if length == 0:
                    raise AdapterError(400, "Empty request body")
                if length > MAX_REQUEST_BODY:
                    raise AdapterError(413, "Request body is too large")
                content_types = self.headers.get_all("Content-Type", [])
                if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
                    raise AdapterError(415, "JSON content type required")
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise AdapterError(400, "Incomplete request body")
                try:
                    document = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                except (UnicodeError, ValueError, RecursionError):
                    raise AdapterError(400, "Invalid JSON request") from None
                value, language, provider = request_document(document, endpoint)
                function = self.server.adapter.reverse if endpoint == "/v1/reverse" else self.server.adapter.lookup
                body = function(value, language, provider)
            self.respond(200, body)
        except AdapterError as exc:
            self.respond(exc.status, {"error": str(exc)})
        except sqlite3.Error:
            self.respond(503, {"error": "Local storage unavailable"})
        except (ValueError, TypeError):
            self.respond(400, {"error": "Invalid request"})
        except TimeoutError:
            self.respond(408, {"error": "Request body timed out"})
        except Exception:
            self.respond(500, {"error": "Request failed"})

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request(post=True)


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


def secret_env(name):
    value, path = os.environ.get(name, ""), os.environ.get(name + "_FILE", "")
    if value and path:
        raise ValueError("Set only one " + name + " source")
    if path:
        value = Path(path).read_text().strip()
    if len(value) > 512 or any(char.isspace() for char in value):
        raise ValueError("Invalid " + name + " configuration")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", metavar="DEST")
    args = parser.parse_args()
    os.umask(0o077)
    if "ADAPTER_DB" in os.environ:
        raise ValueError("Legacy ADAPTER_DB must be archived; configure ADAPTER_CACHE_DB")
    path = os.environ.get("ADAPTER_CACHE_DB", "/data/cache.sqlite3")
    if args.backup:
        # Refuse overwrite and source creation: a typo must not create a fake backup.
        with contextlib.closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as source:
            if not require_cache_schema(source):
                raise ValueError("Cache database is missing")
            source.execute("SELECT cache_key FROM cache LIMIT 1").fetchone()
            with open(args.backup, "xb"):
                pass
            with contextlib.closing(sqlite3.connect(args.backup)) as destination:
                source.backup(destination)
        return
    key, baidu_ak, baidu_sk = (secret_env(name) for name in ("AMAP_KEY", "BAIDU_AK", "BAIDU_SK"))
    user_agent = os.environ.get("NOMINATIM_USER_AGENT", "").strip()
    if len(user_agent) > 256 or any(ord(char) < 32 or ord(char) > 126 for char in user_agent):
        raise ValueError("Invalid Nominatim user agent")
    adapter = Adapter(path, key, number_env("CACHE_TTL_SECONDS", "86400", 31536000),
                      number_env("UPSTREAM_TIMEOUT_SECONDS", "8", 20),
                      number_env("LOOKUP_TIMEOUT_SECONDS", "20", 25), user_agent,
                      os.environ.get("GEOCODER_PROVIDER", "auto"), os.environ.get("MAINLAND_PROVIDER", "amap"),
                      baidu_ak, baidu_sk, os.environ.get("AMAP_API_REGION", "mainland"))
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
