"""Offline package and registry APIs exercise the real retention planner."""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import retain_images as retention


REPOSITORY = "fixture/teslamate"
PACKAGES = ("teslamate-amap", "teslamate-amap-adapter")
INDEX = "application/vnd.oci.image.index.v1+json"
IMAGE = "application/vnd.oci.image.manifest.v1+json"


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def raw_manifest(data):
    return json.dumps(data, sort_keys=True).encode()


def group(number):
    return "v4.3." + str(number) + "-amap-" + format(number + 1, "040x")


class PackageFixture:
    def __init__(self, count=12, owner_type="User"):
        self.owner_type, self.events, self.fail = owner_type, [], None
        self.rows = {package: [] for package in PACKAGES}
        self.manifests = {package: {} for package in PACKAGES}
        for number in range(count):
            self.add_group(number)
        if count:
            self.latest(count - 1)

    def add_manifest(self, package, data, tags, number=0):
        identity = len(self.rows[package]) + 1
        name = digest(raw_manifest(data))
        self.manifests[package][name] = data
        self.rows[package].append({
            "id": identity, "name": name,
            "created_at": (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=number)).isoformat(),
            "metadata": {"package_type": "container", "container": {"tags": list(tags)}},
        })
        return name

    def add_image(self, package, seed, tags=(), number=0):
        return self.add_manifest(package, {"schemaVersion": 2, "mediaType": IMAGE, "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json", "digest": digest(seed.encode()), "size": 1,
        }, "layers": []}, tags, number)

    def entry(self, package, name, architecture):
        return {"mediaType": IMAGE, "digest": name, "size": len(raw_manifest(self.manifests[package][name])), "platform": {"os": "linux", "architecture": architecture}}

    def add_group(self, number):
        for package in PACKAGES:
            children = [self.add_image(package, package + str(number) + arch, [group(number) + "-" + arch], number) for arch in ("amd64", "arm64")]
            self.add_manifest(package, {"schemaVersion": 2, "mediaType": INDEX, "manifests": [self.entry(package, name, arch) for name, arch in zip(children, ("amd64", "arm64"))]}, [group(number)], number)

    def tagged(self, package, tag):
        return next(row for row in self.rows[package] if tag in row["metadata"]["container"]["tags"])

    def latest(self, number, package=None):
        for name in (PACKAGES if package is None else (package,)):
            for row in self.rows[name]:
                tags = row["metadata"]["container"]["tags"]
                if "latest" in tags:
                    tags.remove("latest")
            self.tagged(name, group(number))["metadata"]["container"]["tags"].append("latest")

    def share_child(self, old, new, architecture="amd64"):
        for package in PACKAGES:
            old_row = self.tagged(package, group(old) + "-" + architecture)
            new_row = self.tagged(package, group(new) + "-" + architecture)
            new_tag = group(new) + "-" + architecture
            new_row["metadata"]["container"]["tags"].remove(new_tag)
            old_row["metadata"]["container"]["tags"].append(new_tag)
            index_row = self.tagged(package, group(new))
            data = copy.deepcopy(self.manifests[package].pop(index_row["name"]))
            for entry in data["manifests"]:
                if entry["platform"]["architecture"] == architecture:
                    entry.update(self.entry(package, old_row["name"], architecture))
            index_row["name"] = digest(raw_manifest(data))
            self.manifests[package][index_row["name"]] = data

    def api(self, method, path):
        self.events.append((method, path))
        if self.fail == (method, path):
            raise RuntimeError("private-token-response")
        if path == "repos/" + REPOSITORY:
            return {"full_name": REPOSITORY, "owner": {"login": "fixture", "type": self.owner_type}}
        prefix = ("users/" if self.owner_type == "User" else "orgs/") + "fixture/packages/container/"
        suffix = path.removeprefix(prefix)
        package = suffix.split("/")[0]
        if package not in PACKAGES:
            raise AssertionError((method, path))
        if suffix == package:
            return {"name": package, "package_type": "container", "repository": {"full_name": REPOSITORY}}
        if method == "GET" and suffix.startswith(package + "/versions?"):
            page = int(parse_qs(path.split("?", 1)[1])["page"][0])
            rows = list(reversed(self.rows[package]))
            return copy.deepcopy(rows[(page - 1) * 100:page * 100])
        if method == "DELETE" and suffix.startswith(package + "/versions/"):
            return None  # GitHub DELETE has no JSON response body.
        raise AssertionError((method, path))

    def fetch(self, owner, package, name):
        self.events.append(("FETCH", package, name))
        if self.fail == ("FETCH", package, name):
            raise RuntimeError("private-token-response")
        return copy.deepcopy(self.manifests[package][name])

    def run(self, apply=False):
        return retention.retain_images(REPOSITORY, apply=apply, api=self.api, fetch=self.fetch)

    def deletes(self):
        return [event for event in self.events if event[0] == "DELETE"]


class RetentionTests(unittest.TestCase):
    def test_default_preview_paginates_and_keeps_ten_by_creation_date(self):
        fixture = PackageFixture(40)
        for package in PACKAGES:
            fixture.tagged(package, group(0))["created_at"] = "2026-12-01T00:00:00Z"
        report = fixture.run()
        self.assertEqual(report["mode"], "preview")
        self.assertEqual(report["complete_releases"], 40)
        self.assertEqual(report["retained_releases"], [group(0), *[group(number) for number in range(39, 30, -1)]])
        self.assertEqual(fixture.deletes(), [])
        for package in PACKAGES:
            self.assertEqual(len(report["packages"][package]["delete"]), 90)
            self.assertIn(("GET", "users/fixture/packages/container/" + package + "/versions?per_page=100&page=2"), fixture.events)

    def test_old_latest_protects_the_complete_group_in_both_packages(self):
        fixture = PackageFixture(13)
        fixture.latest(0, PACKAGES[0])
        fixture.latest(1, PACKAGES[1])
        report = fixture.run(apply=True)
        self.assertEqual(set(report["retained_releases"]), {group(number) for number in (*range(3, 13), 0, 1)})
        self.assertEqual(report["candidate_releases"], [group(2)])
        for package in PACKAGES:
            self.assertEqual(len(report["packages"][package]["delete"]), 3)

    def test_shared_children_and_unknown_retained_indexes_are_protected(self):
        fixture = PackageFixture(12)
        fixture.share_child(0, 11)
        package = PACKAGES[0]
        old_index = fixture.tagged(package, group(1))
        data = copy.deepcopy(fixture.manifests[package][old_index["name"]])
        data["annotations"] = {"fixture": "unknown pinned tag"}
        unknown = fixture.add_manifest(package, data, ["custom-pin"])
        orphan = fixture.add_image(package, "unassociated")
        report = fixture.run(apply=True)
        for name in PACKAGES:
            shared = fixture.tagged(name, group(0) + "-amd64")["name"]
            self.assertNotIn(shared, {row["digest"] for row in report["packages"][name]["delete"]})
        removed = {row["digest"] for row in report["packages"][package]["delete"]}
        self.assertNotIn(unknown, removed)
        self.assertNotIn(orphan, removed)
        self.assertIn(old_index["name"], removed)
        for entry in data["manifests"]:
            self.assertNotIn(entry["digest"], removed)

    def test_incomplete_groups_stay_and_organization_packages_are_supported(self):
        fixture = PackageFixture(13, owner_type="Organization")
        fixture.tagged(PACKAGES[1], group(0) + "-arm64")["metadata"]["container"]["tags"].clear()
        # A valid partial index also makes this a preserved incomplete group.
        row = fixture.tagged(PACKAGES[0], group(1))
        fixture.manifests[PACKAGES[0]][row["name"]]["manifests"].pop()
        report = fixture.run(apply=True)
        self.assertEqual(report["incomplete_releases"], 2)
        self.assertEqual(report["candidate_releases"], [group(2)])
        for package in PACKAGES:
            removed = {item["digest"] for item in report["packages"][package]["delete"]}
            self.assertNotIn(fixture.tagged(package, group(0))["name"], removed)
            self.assertNotIn(fixture.tagged(package, group(1))["name"], removed)
        self.assertTrue(any(event[1].startswith("orgs/fixture/packages/") for event in fixture.events if event[0] == "DELETE"))

    def test_apply_validates_both_packages_then_deletes_indexes_before_children(self):
        fixture = PackageFixture()
        report = fixture.run(apply=True)
        self.assertEqual(report["mode"], "apply")
        deleted = fixture.deletes()
        self.assertEqual(len(deleted), 12)
        index_paths = {"users/fixture/packages/container/" + package + "/versions/" + str(row["id"]) for package in PACKAGES for row in report["packages"][package]["delete"] if row["kind"] == "index"}
        self.assertEqual({event[1] for event in deleted[:4]}, index_paths)
        first_delete = next(index for index, event in enumerate(fixture.events) if event[0] == "DELETE")
        self.assertTrue(all(event[0] == "DELETE" for event in fixture.events[first_delete:]))

    def test_read_errors_malformed_metadata_and_missing_dependencies_never_write(self):
        for failure in ("second_inventory", "second_manifest", "digest", "id", "tags", "date", "duplicate", "schema", "descriptor", "platform", "missing_child", "missing_config"):
            with self.subTest(failure=failure):
                fixture = PackageFixture()
                row = fixture.rows[PACKAGES[1]][-1]
                manifest = fixture.manifests[PACKAGES[1]][row["name"]]
                if failure == "second_inventory":
                    fixture.fail = ("GET", "users/fixture/packages/container/" + PACKAGES[1] + "/versions?per_page=100&page=1")
                elif failure == "second_manifest":
                    fixture.fail = ("FETCH", PACKAGES[1], row["name"])
                elif failure == "digest":
                    row["name"] = "not-a-digest"
                elif failure == "id":
                    row["id"] = True
                elif failure == "tags":
                    row["metadata"]["container"]["tags"] = ["private/token"]
                elif failure == "date":
                    row["created_at"] = "invalid"
                elif failure == "duplicate":
                    fixture.rows[PACKAGES[1]].append(copy.deepcopy(row))
                elif failure == "schema":
                    manifest["schemaVersion"] = 1
                elif failure == "descriptor":
                    del manifest["manifests"][0]["digest"]
                elif failure == "platform":
                    manifest["manifests"][0]["platform"] = "invalid"
                elif failure == "missing_child":
                    manifest["manifests"][0]["digest"] = "sha256:" + "a" * 64
                elif failure == "missing_config":
                    del fixture.manifests[PACKAGES[1]][fixture.rows[PACKAGES[1]][0]["name"]]["config"]
                with self.assertRaises((ValueError, KeyError, RuntimeError, TypeError)):
                    fixture.run(apply=True)
                self.assertEqual(fixture.deletes(), [])

    def test_unknown_owner_wrong_repository_and_cyclic_indexes_fail_closed(self):
        for failure in ("owner", "repository", "package", "cycle"):
            with self.subTest(failure=failure):
                fixture = PackageFixture(owner_type="Bot" if failure == "owner" else "User")
                api = fixture.api

                def altered(method, path):
                    result = api(method, path)
                    if method == "GET" and path == "repos/" + REPOSITORY and failure == "repository":
                        result["full_name"] = "fixture/other"
                    if method == "GET" and path.endswith("/" + PACKAGES[1]) and failure == "package":
                        result["repository"]["full_name"] = "fixture/other"
                    return result

                if failure == "cycle":
                    row = fixture.tagged(PACKAGES[1], group(0))
                    fixture.manifests[PACKAGES[1]][row["name"]]["manifests"][0]["digest"] = row["name"]
                with self.assertRaises(ValueError):
                    retention.retain_images(REPOSITORY, apply=True, api=altered, fetch=fixture.fetch)
                self.assertEqual(fixture.deletes(), [])

    def test_delete_error_stops_before_any_child_deletion(self):
        fixture = PackageFixture()
        failed = fixture.tagged(PACKAGES[1], group(0))
        fixture.fail = ("DELETE", "users/fixture/packages/container/" + PACKAGES[1] + "/versions/" + str(failed["id"]))
        with self.assertRaises(RuntimeError):
            fixture.run(apply=True)
        for event in fixture.deletes():
            package, identity = event[1].split("/")[4], int(event[1].split("/")[-1])
            row = next(row for row in fixture.rows[package] if row["id"] == identity)
            self.assertEqual(fixture.manifests[package][row["name"]]["mediaType"], INDEX)

    def test_cli_preview_defaults_and_secret_safe_failure_and_empty_delete(self):
        with patch.object(sys, "argv", ["retain_images", "--repository", REPOSITORY]), patch.object(retention, "retain_images", return_value={"mode": "preview"}) as run, patch.object(sys, "stdout", new_callable=io.StringIO):
            self.assertEqual(retention.main(), 0)
        run.assert_called_once_with(REPOSITORY, apply=False)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with patch.object(sys, "argv", ["retain_images", "--repository", REPOSITORY, "--apply", "--output", str(output)]), patch.object(retention, "retain_images", side_effect=RuntimeError("private-token-response")), patch.object(sys, "stderr", new_callable=io.StringIO) as error:
                self.assertEqual(retention.main(), 1)
            self.assertNotIn("private-token-response", error.getvalue())
            self.assertFalse(output.exists())
        with patch.object(retention, "command", return_value=""):
            self.assertIsNone(retention.github("DELETE", "users/fixture/packages/container/example/versions/1"))

    def test_registry_reads_are_bounded_and_verify_actual_manifest_digest(self):
        data = {"schemaVersion": 2, "mediaType": INDEX, "manifests": []}
        raw = raw_manifest(data)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = raw
        with patch.object(retention, "urlopen", return_value=response) as fetch, patch.object(retention, "registry_token", return_value="fixture-token"):
            self.assertEqual(retention.registry_manifest("fixture", PACKAGES[0], digest(raw)), data)
            self.assertEqual(fetch.call_args.kwargs["timeout"], 20)
            with self.assertRaises(ValueError):
                retention.registry_manifest("fixture", PACKAGES[0], "sha256:" + "a" * 64)
        response.__enter__.return_value.read.return_value = b"x" * 1_048_577
        with patch.object(retention, "urlopen", return_value=response), self.assertRaises(ValueError):
            retention.response_bytes("https://ghcr.io/token", {})


if __name__ == "__main__":
    unittest.main()
