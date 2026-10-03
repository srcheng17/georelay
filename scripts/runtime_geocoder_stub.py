"""Public-coordinate protocol fixture for the isolated compiled-release check."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

LAT, LON = "48.858400123", "2.294500456"
CONCURRENT_LAT = "48.858401123"
CONTEXT = {"source_osm_type": "node", "source_osm_id": 123, "outside_mainland": True}
EXPECTED = [("reverse", "en"), ("lookup", "zh-cn"), ("lookup", "en"),
            ("lookup", "missing"), ("lookup", "shifted"), ("lookup", "null-source"),
            ("lookup", "wrong-source"),
            ("lookup", "provider-fail"), ("reverse", "en")]


def address(item, refreshed=False):
    name = "Fixture Updated" if refreshed else "Fixture Original"
    return {
        "osm_id": item["osm_id"], "osm_type": "node", "lat": item["lat"], "lon": item["lon"],
        "name": name, "display_name": name + " Address", "namedetails": {"name": name},
        "address": {
            "road": "Fixture Updated Road" if refreshed else "Fixture Original Road",
            "house_number": "2" if refreshed else "1", "postcode": "75007",
            "city": "Fixture City", "county": "Fixture County", "state": "Fixture State",
            "state_district": "Fixture District", "country": "Fixture Country",
            "suburb": "Fixture Neighbourhood",
        },
        "fixture": "refreshed" if refreshed else "original",
        "upstream": {"provider": "osm", "osm_type": "node", "osm_id": 123},
        "georelay": {"version": 1, **CONTEXT},
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, body):
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"ok": True})
        elif self.path == "/legacy-assertions":
            self.respond(200, {"ok": self.server.events == [("reverse", "en")] and self.server.first_id is None})
        elif self.path == "/assertions":
            self.respond(200, {"ok": self.server.events[:len(EXPECTED)] == EXPECTED and
                                    1 <= len(self.server.events[len(EXPECTED):]) <= 8 and
                                    all(event == ("concurrent", "en") for event in self.server.events[len(EXPECTED):])})
        else:
            self.server.events.append(("unexpected-get", ""))
            self.respond(426, {"error": "fixture_protocol_required"})

    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 65536:
                raise ValueError
            payload = json.loads(self.rfile.read(size))
            if payload.get("version") != 1 or not isinstance(payload.get("language"), str):
                raise ValueError
            language = payload["language"].lower()
            if self.path == "/v1/reverse":
                kind, items = "reverse", [payload["address"]]
            elif self.path == "/v1/lookup":
                kind, items = "lookup", payload["addresses"]
            else:
                raise ValueError
            self.server.events.append((kind, language))
            if len(items) != 1:
                raise ValueError
            item = items[0]
            if (type(item["osm_id"]) is not int or item["osm_id"] >= 0
                    or item["osm_type"] != "node" or not isinstance(item.get("context", {}), dict)):
                raise ValueError
            if kind == "reverse":
                if (item["lat"], item["lon"]) == (CONCURRENT_LAT, LON):
                    self.server.events[-1] = ("concurrent", language)
                elif (item["lat"], item["lon"]) != (LAT, LON):
                    self.respond(502, {"error": "fixture_provider_failure"})
                    return
                if self.server.first_id is None and item["lat"] == LAT:
                    self.server.first_id = item["osm_id"]
                body = address(item)
            else:
                if (item["osm_id"] != self.server.first_id or (item["lat"], item["lon"]) != (LAT, LON)
                        or item.get("context") != CONTEXT):
                    raise ValueError
                if language == "provider-fail":
                    self.respond(502, {"error": "fixture_provider_failure"})
                    return
                body = [] if language == "missing" else [address(item, True)]
                if language == "shifted":
                    body[0]["lat"] = "49"
                if language == "wrong-source":
                    body[0]["georelay"]["source_osm_id"] = 456
                if language == "null-source":
                    body[0]["georelay"] = {"version": 1, "outside_mainland": False,
                                            "source_osm_type": None, "source_osm_id": None}
            self.respond(200, body)
        except (KeyError, TypeError, ValueError):
            self.respond(400, {"error": "fixture_request_invalid"})


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    server.events, server.first_id = [], None
    server.serve_forever()
