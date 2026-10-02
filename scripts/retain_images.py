#!/usr/bin/env python3
"""Preview conservative GHCR retention; delete only with explicit --apply."""

import argparse
import base64
from datetime import datetime
from functools import lru_cache
from graphlib import TopologicalSorter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from update_release import command


KEEP_RELEASES = 10
RELEASE = re.compile(r"(v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)-georelay-[0-9a-f]{40})(?:-(amd64|arm64))?")
INDEX_TYPES = {"application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"}
IMAGE_TYPES = {"application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"}


def github(method, path):
    output = command("gh", "api", "--method", method, "-H", "X-GitHub-Api-Version: 2022-11-28", path)
    return json.loads(output) if method == "GET" else None


def response_bytes(url, headers):
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        raw = response.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("Registry response exceeded size limit")
    return raw


@lru_cache
def registry_token(owner, package):
    headers = {"User-Agent": "georelay-retention"}
    credential = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if credential:
        actor = os.environ.get("GITHUB_ACTOR") or owner
        headers["Authorization"] = "Basic " + base64.b64encode((actor + ":" + credential).encode()).decode()
    query = urlencode({"service": "ghcr.io", "scope": "repository:" + owner.lower() + "/" + package + ":pull"})
    token = json.loads(response_bytes("https://ghcr.io/token?" + query, headers))["token"]
    if not isinstance(token, str) or not token:
        raise ValueError("Invalid registry token response")
    return token


def registry_manifest(owner, package, digest):
    raw = response_bytes("https://ghcr.io/v2/" + owner.lower() + "/" + package + "/manifests/" + digest, {
        "Authorization": "Bearer " + registry_token(owner, package),
        "Accept": ", ".join(sorted(INDEX_TYPES | IMAGE_TYPES)),
        "User-Agent": "georelay-retention",
    })
    if "sha256:" + hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Registry manifest does not match the inventory digest")
    return json.loads(raw)


def valid_digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError("Invalid package digest")
    return value


def descriptor(value):
    if (not isinstance(value, dict) or not isinstance(value.get("mediaType"), str)
            or type(value.get("size")) is not int or value["size"] < 0):
        raise ValueError("Invalid manifest descriptor")
    return valid_digest(value.get("digest"))


def inventory(api, endpoint):
    versions, ids, tags = {}, set(), {}
    # ponytail: 20,000 versions per package; raise this bound if a reviewed inventory reaches it.
    for page in range(1, 201):
        rows = api("GET", endpoint + "/versions?per_page=100&page=" + str(page))
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Invalid package inventory page")
        for row in rows:
            identity, digest = row["id"], valid_digest(row["name"])
            created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            names = row["metadata"]["container"]["tags"]
            if (type(identity) is not int or identity <= 0 or created.tzinfo is None
                    or row["metadata"]["package_type"] != "container"
                    or not isinstance(names, list) or any(
                        not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", tag)
                        for tag in names)):
                raise ValueError("Invalid package version metadata")
            if identity in ids or digest in versions or len(set(names)) != len(names) or any(tag in tags for tag in names):
                raise ValueError("Ambiguous package inventory")
            ids.add(identity)
            versions[digest] = {"id": identity, "created": created, "tags": names}
            tags.update({tag: digest for tag in names})
        if len(rows) < 100:
            return versions, tags
    raise ValueError("Package inventory exceeded pagination limit")


def manifest_graph(owner, package, versions, fetch):
    manifests, children = {}, {}
    for digest in versions:
        data = fetch(owner, package, digest)
        if not isinstance(data, dict) or data.get("schemaVersion") != 2:
            raise ValueError("Invalid registry manifest")
        kind = data.get("mediaType")
        if kind in INDEX_TYPES:
            entries = data["manifests"]
            if not isinstance(entries, list) or not entries:
                raise ValueError("Invalid registry index")
            dependencies = [descriptor(entry) for entry in entries]
            for entry in entries:
                platform = entry.get("platform", {})
                if not isinstance(platform, dict) or any(
                    key in platform and (not isinstance(platform[key], str) or not platform[key])
                    for key in ("os", "architecture", "variant")
                ):
                    raise ValueError("Invalid index platform metadata")
        elif kind in IMAGE_TYPES:
            descriptor(data["config"])
            if not isinstance(data["layers"], list):
                raise ValueError("Invalid registry image")
            for layer in data["layers"]:
                descriptor(layer)
            dependencies = []
        else:
            raise ValueError("Unsupported registry manifest")
        if "subject" in data:
            dependencies.append(descriptor(data["subject"]))
        if any(child not in versions for child in dependencies):
            raise ValueError("Referenced manifest missing from package inventory")
        manifests[digest], children[digest] = data, dependencies
    # Cyclic indexes are invalid; never decide deletion from such a graph.
    tuple(TopologicalSorter(children).static_order())
    return manifests, children


def plan_retention(repository, api=github, fetch=registry_manifest):
    if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository):
        raise ValueError("Invalid GitHub repository")
    owner = repository.split("/")[0]
    source = api("GET", "repos/" + repository)
    if source["full_name"].lower() != repository.lower() or source["owner"]["login"].lower() != owner.lower():
        raise ValueError("Repository owner does not match")
    owner_type = source["owner"]["type"]
    if owner_type not in ("User", "Organization"):
        raise ValueError("Unsupported repository owner")
    prefix = ("users/" if owner_type == "User" else "orgs/") + owner + "/packages/container/"
    packages, groups = {}, set()
    for package in ("georelay", "georelay-adapter"):
        endpoint = prefix + package
        metadata = api("GET", endpoint)
        if (metadata["name"] != package or metadata["package_type"] != "container"
                or metadata["repository"]["full_name"].lower() != repository.lower()):
            raise ValueError("Package is not linked to the selected repository")
        versions, tags = inventory(api, endpoint)
        manifests, children = manifest_graph(owner, package, versions, fetch)
        packages[package] = {"endpoint": endpoint, "versions": versions, "tags": tags, "manifests": manifests, "children": children}
        groups.update(match[1] for tag in tags if (match := RELEASE.fullmatch(tag)))

    complete = {}
    for group in groups:
        members, dates = {}, []
        for package, data in packages.items():
            tags, manifests = data["tags"], data["manifests"]
            if not all(group + suffix in tags for suffix in ("", "-amd64", "-arm64")):
                break
            index_digest = tags[group]
            index = manifests[index_digest]
            entries = index.get("manifests", [])
            actual = [(entry.get("platform", {}).get("os"), entry.get("platform", {}).get("architecture"), entry["digest"]) for entry in entries]
            expected = [("linux", arch, tags[group + "-" + arch]) for arch in ("amd64", "arm64")]
            if (index["mediaType"] not in INDEX_TYPES or len(actual) != 2 or set(actual) != set(expected)
                    or any(manifests[digest]["mediaType"] not in IMAGE_TYPES for _, _, digest in expected)):
                break
            members[package] = {index_digest, *(digest for _, _, digest in expected)}
            dates.append(data["versions"][index_digest]["created"])
        else:
            complete[group] = {"members": members, "created": max(dates)}

    newest = sorted(complete, key=lambda group: (complete[group]["created"], group), reverse=True)
    retained = set(newest[:KEEP_RELEASES])
    retained.update(group for group in complete if any(
        data["tags"].get("latest") == data["tags"][group] for data in packages.values()
    ))
    obsolete = set(complete) - retained
    report = {
        "repository": repository, "keep_releases": KEEP_RELEASES,
        "complete_releases": len(complete), "incomplete_releases": len(groups - set(complete)),
        "retained_releases": [group for group in newest if group in retained],
        "candidate_releases": [group for group in reversed(newest) if group in obsolete], "packages": {},
    }
    for package, data in packages.items():
        candidates = set().union(*(complete[group]["members"][package] for group in obsolete))
        protected = set(data["versions"]) - candidates
        for digest in candidates:
            if any(not (match := RELEASE.fullmatch(tag)) or match[1] not in obsolete for tag in data["versions"][digest]["tags"]):
                protected.add(digest)
        pending = list(protected)
        while pending:
            for child in data["children"][pending.pop()]:
                if child not in protected:
                    protected.add(child)
                    pending.append(child)
        deletion = [{
            "id": data["versions"][digest]["id"], "digest": digest,
            "kind": "index" if data["manifests"][digest]["mediaType"] in INDEX_TYPES else "image",
        } for digest in candidates - protected]
        deletion.sort(key=lambda row: (row["kind"] != "index", row["id"]))
        report["packages"][package] = {
            "versions": len(data["versions"]), "protected": len(protected),
            "latest": data["tags"].get("latest"), "delete": deletion,
        }
    return report, packages


def retain_images(repository, apply=False, api=github, fetch=registry_manifest):
    report, packages = plan_retention(repository, api=api, fetch=fetch)
    report["mode"] = "apply" if apply else "preview"
    if apply:
        # Validate both packages first, then remove all old indexes before any children.
        for kind in ("index", "image"):
            for package, data in packages.items():
                for row in report["packages"][package]["delete"]:
                    if row["kind"] == kind:
                        api("DELETE", data["endpoint"] + "/versions/" + str(row["id"]))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        report = retain_images(args.repository, apply=args.apply)
        text = json.dumps(report, indent=2) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                summary.write("## Image retention\n\n```json\n" + text + "```\n")
        print(text, end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, subprocess.SubprocessError):
        # Do not print remote bodies, exception URLs, headers, or credentials.
        print("Image retention stopped; review package access and metadata before retrying. No further deletion attempted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
