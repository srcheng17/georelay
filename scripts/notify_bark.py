#!/usr/bin/env python3
"""Send a verified controller failure to Bark without exposing endpoint or response."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


STAGES = {"beta_validation", "beta_jobs", "beta_index", "release_record", "merge_readiness", "branch_protection", "merge", "main_dispatch", "main_publication"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def valid_url(url, allow_local_http=False):
    if not isinstance(url, str) or not url or len(url) > 4096 or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url):
        return False
    try:
        value = urlsplit(url)
        if not value.hostname or value.username or value.password or value.fragment or (value.port is not None and not 1 <= value.port <= 65535):
            return False
        if value.scheme == "https":
            return True
        return allow_local_http and value.scheme == "http" and ipaddress.ip_address(value.hostname).is_loopback
    except ValueError:
        return False


def payload(report):
    if not isinstance(report, dict) or report.get("status") != "failed" or report.get("notify") is not True:
        raise ValueError("Not a controller failure")
    item = report["notification"]
    if not isinstance(item, dict):
        raise ValueError("Invalid notification object")
    repository, run_id, attempt, pull, revision, stage = (item[k] for k in ("repository", "run_id", "attempt", "source_pr", "sha", "stage"))
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or any(type(n) is not int or n < 1 for n in (run_id, attempt)) or type(pull) is not int or pull < 0
            or not re.fullmatch(r"[0-9a-f]{40}", revision) or stage not in STAGES):
        raise ValueError("Invalid failure context")
    link = "https://github.com/" + repository + "/actions/runs/" + str(run_id)
    if item.get("run_url") != link:
        raise ValueError("Invalid run link")
    jobs = item.get("failed_jobs", [])
    if not isinstance(jobs, list) or any(job not in {"checks", "build-amd64", "build-arm64", "verify", "publish", "release-record"} for job in jobs):
        raise ValueError("Invalid failure jobs")
    result = item.get("conclusion", "failure")
    if result not in {"failure", "cancelled", "timed_out", "action_required", "startup_failure", "success"}:
        raise ValueError("Invalid workflow conclusion")
    body = repository + "\n阶段: " + stage + " (" + result + ")\n"
    if pull:
        body += "PR: #" + str(pull) + " https://github.com/" + repository + "/pull/" + str(pull) + "\n"
    body += "Commit: " + revision + "\n"
    expected = item.get("expected_main_sha")
    if expected is not None:
        if not re.fullmatch(r"[0-9a-f]{40}", expected) or stage != "main_publication":
            raise ValueError("Invalid expected main commit")
        body += "Expected main: " + expected + "\n"
    if jobs:
        body += "Jobs: " + ", ".join(jobs) + "\n"
    if report.get("merged_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", report["merged_sha"]) or stage != "main_dispatch":
            raise ValueError("Invalid merged failure context")
        body += "已合并: " + report["merged_sha"] + "；正式发布触发未确认\n"
    body += link
    return {"title": "GeoRelay GHCR 流程失败", "body": body, "level": "active", "group": "GeoRelay",
            "idempotency_key": "georelay/" + repository + "/" + str(run_id) + "/" + str(attempt) + "/" + stage}


def send(report, url, dry_run=False, allow_local_http=False, attempts=3, timeout=10, sleep=time.sleep, open_url=None):
    try:
        data = payload(report)
    except (ValueError, KeyError, TypeError):
        return {"status": "configuration_error", "attempts": 0}
    if not url:
        return {"status": "not_configured", "attempts": 0}
    if not valid_url(url, allow_local_http) or type(attempts) is not int or not 1 <= attempts <= 5 or not 0.1 <= timeout <= 30:
        return {"status": "configuration_error", "attempts": 0}
    if dry_run:
        return {"status": "dry_run", "attempts": 0}
    open_url = open_url or build_opener(NoRedirect()).open
    raw = json.dumps(data, ensure_ascii=False).encode()
    ambiguous_transport = False
    for attempt in range(1, attempts + 1):
        code = None
        retry_after = ""
        request = Request(url, data=raw, headers={"Content-Type": "application/json", "User-Agent": "georelay-notification/1"}, method="POST")
        try:
            with open_url(request, timeout=timeout) as response:
                code = response.status
                body = response.read(65537)
                retry_after = response.headers.get("Retry-After", "")
            if 200 <= code < 300:
                if len(body) > 65536 or json.loads(body).get("code") != 200:
                    return {"status": "verification_failed", "attempts": attempt, "http_status": code}
                return {"status": "sent", "attempts": attempt, "http_status": code}
        except HTTPError as error:
            code = error.code
            retry_after = error.headers.get("Retry-After", "") if error.headers else ""
        except (URLError, TimeoutError, OSError):
            # Retry only within this attempt budget. A terminal uncertain result
            # must be inspected before a caller starts any new delivery attempt.
            ambiguous_transport = True
            if attempt == attempts:
                return {"status": "uncertain", "attempts": attempt}
        except (ValueError, KeyError, TypeError, AttributeError):
            return {"status": "verification_failed", "attempts": attempt}
        if code is not None and code not in {408, 429} and not 500 <= code <= 599:
            return {"status": "rejected", "attempts": attempt, "http_status": code}
        if attempt == attempts:
            if ambiguous_transport:
                return {"status": "uncertain", "attempts": attempt}
            return {"status": "retry_exhausted", "attempts": attempts, "http_status": code}
        delay = min(30, 2 ** (attempt - 1))
        if isinstance(retry_after, str) and retry_after.isdigit():
            delay = max(delay, min(30, int(retry_after[:8])))
        sleep(delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-local-http", action="store_true")
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text())
        result = send(report, os.environ.get("BARK_URL", ""), dry_run=args.dry_run, allow_local_http=args.allow_local_http)
    except (OSError, ValueError, TypeError):
        result = {"status": "configuration_error", "attempts": 0}
    print(json.dumps(result, separators=(",", ":")))
    return 0 if result["status"] in {"sent", "dry_run"} else 1


if __name__ == "__main__":
    sys.exit(main())
