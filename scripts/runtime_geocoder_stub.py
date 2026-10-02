"""Public-coordinate fixture for the isolated compiled-release check; no providers."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit


def address(refreshed=False):
    return {
        "osm_id": -10001, "osm_type": "node",
        # Refresh must never replace stored coordinates, even when the provider moves them.
        "lat": "49.0" if refreshed else "48.8584",
        "lon": "3.0" if refreshed else "2.2945",
        "name": "Fixture Updated" if refreshed else "Fixture Original",
        "display_name": "Fixture Updated Address" if refreshed else "Fixture Original Address",
        "namedetails": {"name": "Fixture Updated" if refreshed else "Fixture Original"},
        "address": {
            "road": "Fixture Updated Road" if refreshed else "Fixture Original Road",
            "house_number": "2" if refreshed else "1",
            "postcode": "75007", "city": "Fixture City", "county": "Fixture County",
            "state": "Fixture State", "state_district": "Fixture District",
            "country": "Fixture Country", "suburb": "Fixture Neighbourhood",
        },
        "fixture": "refreshed" if refreshed else "original",
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        request = urlsplit(self.path)
        query = parse_qs(request.query)
        language = self.headers.get("Accept-Language", "")
        status, body = 200, {"ok": True}
        if request.path == "/reverse":
            point = (query.get("lat", [""])[0], query.get("lon", [""])[0])
            self.server.events.append(("reverse", language, *point))
            if query.get("format") != ["jsonv2"] or language != "en":
                status, body = 400, {"error": "fixture_request_invalid"}
            elif point == ("48.8584", "2.2945"):
                body = address()
            else:
                status, body = 502, {"error": "fixture_provider_failure"}
        elif request.path == "/lookup":
            identities = ",".join(sorted(query.get("osm_ids", [""])[0].split(",")))
            self.server.events.append(("lookup", language, identities))
            if query.get("format") != ["jsonv2"] or identities != "N-10001,W42":
                status, body = 400, {"error": "fixture_request_invalid"}
            elif language == "zh-CN":
                body = [address(True)]
            elif language == "missing":
                body = []
            elif language == "provider-fail":
                status, body = 502, {"error": "fixture_provider_failure"}
            else:
                status, body = 400, {"error": "fixture_request_invalid"}
        elif request.path == "/assertions":
            body = {"ok": self.server.events == [
                ("reverse", "en", "48.8584", "2.2945"),
                ("reverse", "en", "48.8584", "2.2945"),
                ("lookup", "zh-CN", "N-10001,W42"),
                ("lookup", "missing", "N-10001,W42"),
                ("lookup", "provider-fail", "N-10001,W42"),
                ("reverse", "en", "48.8585", "2.2945"),
            ]}
        elif request.path != "/health":
            status, body = 404, {"error": "fixture_endpoint_unknown"}
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), Handler)
    server.events = []
    server.serve_forever()
