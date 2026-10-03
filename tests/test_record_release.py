"""Trusted writer, data-only receipts and repair proofs; no remote writes/network."""

import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import record_release as recorder
from image_context import publication_receipt
from test_release_control import Fixture as ControlFixture, REPO, HEAD, MAIN, VERSION


def zipped(data, name='publication-receipt.json'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(name, json.dumps(data))
    return stream.getvalue()


class Fixture(ControlFixture):
    def __init__(self, stable=False):
        super().__init__()
        self.stable = stable
        self.version = 'v4.3.0-georelay-' + HEAD if stable else VERSION
        self.pin = {'repository': 'https://github.com/teslamate-org/teslamate.git', 'tag': 'v4.3.0', 'commit': MAIN}
        self.old_pin = dict(self.pin, tag='v4.2.0', commit='c' * 40)
        self.run.update(status='in_progress', conclusion=None)
        if stable:
            self.run.update(event='push', head_branch='main', display_title='images/push/0/' + HEAD + '/publish/-')
        self.main_sha = HEAD if stable else MAIN
        self.run['channel'] = 'stable' if stable else 'beta'
        self.images(HEAD, self.version)
        # Real OCI descriptors/configs from the controller fixture.
        raw = self.documents[VERSION]
        self.documents[self.version] = raw
        digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
        self.documents[digest] = raw
        for entry in json.loads(raw)['manifests']:
            self.documents[self.version + '-' + entry['platform']['architecture']] = self.documents[entry['digest']]
        self.documents['latest'] = raw
        self.receipt = publication_receipt(dict(source_sha=HEAD, channel=self.run['channel'], version=self.version), self.pin,
            {package: digest for package in recorder.PACKAGES},
            dict(tag='latest' if stable else 'beta-pr-7', status='promoted', reason='verified'), 10, 1)
        self.artifacts = [{'id': 50, 'name': recorder.receipt_name(10, 1, HEAD, self.version), 'expired': False,
                           'size_in_bytes': 1000, 'workflow_run': {'id': 10, 'head_sha': HEAD}}]
        self.tag = None
        self.release = None
        self.release_list = []
        self.diff = {'status': 'ahead', 'merge_base_commit': {'sha': MAIN}, 'total_commits': 1,
                     'commits': [{'sha': HEAD, 'commit': {'message': 'chore: follow official TeslaMate'}}],
                     'files': [{'filename': 'upstream.json', 'status': 'modified'}]}
        self.downloads = []
        self.api_error = None
        self.lost_response = None
        self.repair = {'id': 99, 'run_attempt': 1, 'workflow_id': 8, 'status': 'completed', 'conclusion': 'success',
                       'event': 'workflow_dispatch', 'head_branch': 'main', 'head_sha': self.main_sha,
                       'repository': {'full_name': REPO}, 'head_repository': {'full_name': REPO},
                       'display_title': 'release-record/10/1/' + HEAD + '/' + self.version}

    def api(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if (method, path) == self.api_error:
            raise recorder.APIError(403)
        root = 'repos/' + REPO
        local = path.removeprefix(root)
        if path.startswith('repos/teslamate-org/teslamate/releases/tags/'):
            return dict(tag_name=self.pin['tag'], draft=False, prerelease=False)
        if path.startswith('repos/teslamate-org/teslamate/git/ref/tags/'):
            return {'object': {'type': 'commit', 'sha': self.pin['commit']}}
        if local == '/actions/runs/10/attempts/1':
            return copy.deepcopy(self.run)
        if local == '/actions/workflows/ci.yml':
            return copy.deepcopy(self.workflow)
        if local.startswith('/actions/runs/10/attempts/1/jobs?'):
            return dict(total_count=len(self.jobs), jobs=copy.deepcopy(self.jobs))
        if local.startswith('/actions/runs/10/artifacts?'):
            return dict(total_count=len(self.artifacts), artifacts=copy.deepcopy(self.artifacts))
        if local.startswith('/check-runs/'):
            return copy.deepcopy(self.check)
        if local.startswith('/contents/upstream.json?ref='):
            pin = self.pin if local.endswith(HEAD) else self.old_pin
            return dict(type='file', encoding='base64', content=base64.b64encode(json.dumps(pin).encode()).decode())
        if method == 'GET' and local == '/git/ref/tags/' + self.version:
            if self.tag is None:
                raise recorder.APIError(404)
            return {'object': {'type': 'commit', 'sha': self.tag}}
        if method == 'POST' and local == '/git/refs':
            self.tag = payload['sha']
            if self.lost_response == 'tag':
                raise recorder.APIError()
            return {}
        if method == 'GET' and local == '/releases/tags/' + self.version:
            if self.release is None:
                raise recorder.APIError(404)
            return copy.deepcopy(self.release)
        if method == 'POST' and local == '/releases':
            self.release = dict(payload, id=90, author={'login': 'github-actions[bot]'}, immutable=False)
            if self.lost_response == 'release':
                raise recorder.APIError()
            return copy.deepcopy(self.release)
        if method == 'PATCH' and local == '/releases/90':
            self.release.update(payload)
            return copy.deepcopy(self.release)
        if local == '/releases/latest':
            if self.release is None:
                raise recorder.APIError(404)
            return copy.deepcopy(self.release)
        if local.startswith('/releases?'):
            return copy.deepcopy(self.release_list)
        if local == '/git/commits/' + HEAD:
            return {'parents': [{'sha': MAIN}]}
        if local.startswith('/compare/' + MAIN + '...' + HEAD):
            return copy.deepcopy(self.diff)
        if local == '/git/ref/heads/main':
            return {'object': {'type': 'commit', 'sha': self.main_sha}}
        if local == '/pulls/7':
            return copy.deepcopy(self.pull)
        if local.startswith('/actions/runs/99/attempts/1/jobs?'):
            return dict(total_count=1, jobs=[dict(id=70, name='release-record', run_id=99, status='completed', conclusion='success')])
        if local == '/actions/runs/99':
            return copy.deepcopy(self.repair)
        if local == '/actions/workflows/release-only.yml':
            return dict(id=8, path='.github/workflows/release-only.yml')
        if local.startswith('/contents/docs/changes/'):
            return dict(type='file', encoding='base64', content=base64.b64encode(b'# Better addresses\n\nPreserve original coordinates and refresh historical addresses.').decode())
        raise AssertionError((method, path, payload))

    def download(self, path):
        self.downloads.append(path)
        return zipped(self.receipt)

    def record(self, apply=True):
        return recorder.record(REPO, 10, 1, HEAD, self.version, api=self.api, fetch=self.fetch, download=self.download, apply=apply)

    def writes(self):
        return [call for call in self.calls if call[0] != 'GET']


class RecordTests(unittest.TestCase):
    def test_in_progress_run_records_exact_source_two_packages_upstream_transition(self):
        fixture = Fixture(stable=True)
        result = fixture.record()
        self.assertEqual(result['status'], 'recorded')
        self.assertTrue(result['make_latest'])
        self.assertEqual(fixture.tag, HEAD)
        self.assertEqual([call[0] for call in fixture.writes()], ['POST', 'POST'])
        self.assertNotIn('target_commitish', fixture.writes()[-1][2])
        body = fixture.release['body']
        self.assertIn('v4.2.0 → v4.3.0', body)
        self.assertIn('no local feature changes', body)
        self.assertIn('no provable previous published version', body)
        self.assertTrue(all(package in body for package in recorder.PACKAGES))
        self.assertIn('/attempts/1', body)
        self.assertEqual(fixture.downloads, ['repos/' + REPO + '/actions/artifacts/50/zip'])
        self.assertFalse(any('filter=latest' in call[1] for call in fixture.calls))

    def test_beta_stale_unlinked_and_failed_alias_never_take_latest(self):
        for case in ('beta', 'stale', 'no_pr', 'failed'):
            with self.subTest(case=case):
                fixture = Fixture(stable=case != 'beta')
                if case == 'stale':
                    fixture.main_sha = MAIN
                elif case == 'no_pr':
                    fixture = Fixture()
                    fixture.run['display_title'] = 'images/workflow_dispatch/0/' + HEAD + '/publish/-'
                    fixture.run['event'] = 'workflow_dispatch'
                    fixture.receipt['floating'] = dict(tag='', status='skipped', reason='no_pr')
                elif case == 'failed':
                    next(job for job in fixture.jobs if job['name'] == 'publish')['conclusion'] = 'failure'
                    fixture.receipt['floating'] = dict(tag='latest', status='failed', reason='promotion_incomplete')
                self.assertFalse(fixture.record()['make_latest'])
                self.assertEqual(fixture.release['make_latest'], 'false')
                self.assertEqual(fixture.release['prerelease'], not fixture.stable)

    def test_stale_pr_head_does_not_prevent_recording_verified_fixed_images(self):
        for reason in ('stale_source', 'stale_pr'):
            fixture = Fixture()
            fixture.receipt['floating'] = dict(tag='beta-pr-7', status='skipped', reason=reason)
            fixture.pull['head']['sha'] = MAIN
            self.assertEqual(fixture.record()['status'], 'recorded')
            self.assertFalse(fixture.release['make_latest'] == 'true')
            self.assertIn('PR link omitted', fixture.release['body'])
            self.assertNotIn('PR: https://github.com/', fixture.release['body'])

    def test_repeated_record_is_zero_write_baseline_frozen_manual_surroundings_preserved(self):
        fixture = Fixture()
        fixture.record()
        first = fixture.release['body']
        fixture.release['body'] = 'Human introduction\n' + first + '\nHuman addendum'
        fixture.calls.clear()
        fixture.release_list = [fixture.release]  # Do not select current release as its own baseline.
        self.assertEqual(fixture.record()['status'], 'recorded')
        self.assertEqual(fixture.writes(), [])
        self.assertEqual(fixture.release['body'], 'Human introduction\n' + first + '\nHuman addendum')
        self.assertFalse(any('/releases?' in call[1] for call in fixture.calls))

    def test_tampered_frozen_baseline_refuses_record_and_readiness_without_reselection(self):
        fixture = Fixture()
        fixture.record()
        meta, text, _, _ = recorder.owned(fixture.release['body'])
        meta['baseline']['source_sha'] = 'not-a-commit'
        encoded = base64.b64encode(json.dumps(meta).encode()).decode()
        fixture.release['body'] = recorder.BEGIN + '\n<!-- georelay-provenance:' + encoded + ' -->\n' + text + recorder.END
        fixture.calls.clear()
        with self.assertRaises(ValueError):
            fixture.record(apply=False)
        with self.assertRaises(ValueError):
            recorder.verify_record(REPO, 10, 1, HEAD, fixture.version, api=fixture.api, fetch=fixture.fetch, download=fixture.download)
        self.assertEqual(fixture.writes(), [])

    def test_renaming_unchanged_old_note_cannot_claim_a_new_product_update(self):
        fixture = Fixture()
        fixture.diff['files'] = [dict(filename='adapter/server.py', status='modified'),
                                 dict(filename='docs/changes/renamed.md', previous_filename='docs/changes/old.md', status='renamed')]
        # The fixture serves exactly identical text at baseline and target.
        with self.assertRaisesRegex(recorder.RecordError, 'product_changes_need_notes'):
            fixture.record()
        self.assertEqual(fixture.writes(), [])

    def test_candidate_receipt_and_actions_failures_write_nothing(self):
        cases = [lambda f: f.receipt.update(source_sha=MAIN), lambda f: f.receipt.update(attempt=2),
                 lambda f: f.receipt.update(fixed_verified=False), lambda f: f.receipt.update(fixed_verified=1),
                 lambda f: f.receipt.update(schema=True), lambda f: f.run.update(run_attempt=2),
                 lambda f: f.check['app'].update(id=0), lambda f: f.check.update(details_url='wrong'),
                 lambda f: f.jobs.pop(), lambda f: f.artifacts.clear(), lambda f: f.artifacts[0].update(expired=True),
                 lambda f: f.artifacts[0]['workflow_run'].update(head_sha=MAIN),
                 lambda f: f.receipt['digests'].update(georelay='sha256:' + '0' * 64)]
        for edit in cases:
            with self.subTest(edit=edit):
                fixture = Fixture()
                edit(fixture)
                with self.assertRaises((ValueError, KeyError)):
                    fixture.record()
                self.assertEqual(fixture.writes(), [])

    def test_missing_architecture_tag_tampered_config_and_index_digest_write_nothing(self):
        for case in ('architecture', 'config', 'index'):
            fixture = Fixture()
            if case == 'architecture':
                fixture.documents[fixture.version + '-amd64'] = b'wrong'
            elif case == 'config':
                index = json.loads(fixture.documents[fixture.version])
                manifest = json.loads(fixture.documents[index['manifests'][0]['digest']])
                fixture.documents[manifest['config']['digest']] = b'wrong'
            else:
                fixture.documents[fixture.receipt['digests']['georelay']] = b'wrong'
            with self.subTest(case=case), self.assertRaises(ValueError):
                fixture.record()
            self.assertEqual(fixture.writes(), [])

    def test_unknown_api_failure_is_not_absent_permission_categories_and_lost_responses(self):
        for path, expected in (('/git/refs', 'tag_permission'), ('/releases', 'release_permission')):
            fixture = Fixture()
            fixture.api_error = ('POST', 'repos/' + REPO + path)
            with self.assertRaisesRegex(recorder.RecordError, expected):
                fixture.record()
        fixture = Fixture()
        fixture.api_error = ('GET', 'repos/' + REPO + '/releases/tags/' + fixture.version)
        with self.assertRaises(recorder.APIError):
            fixture.record()
        self.assertEqual(fixture.writes(), [])
        for stage in ('tag', 'release'):
            fixture = Fixture()
            fixture.lost_response = stage
            self.assertEqual(fixture.record()['status'], 'recorded')
            self.assertEqual(len(fixture.writes()), 2)

    def test_wrong_tag_foreign_release_or_edited_owned_content_is_not_overwritten(self):
        fixture = Fixture()
        fixture.tag = MAIN
        with self.assertRaisesRegex(recorder.RecordError, 'tag_source_conflict'):
            fixture.record()
        self.assertEqual(fixture.writes(), [])
        for case in ('foreign', 'edited', 'digest'):
            fixture = Fixture()
            fixture.record()
            fixture.calls.clear()
            if case == 'foreign':
                fixture.release['author']['login'] = 'human'
            elif case == 'edited':
                fixture.release['body'] = fixture.release['body'].replace('Fixed image pair: verified', 'Changed by human')
            else:
                meta, text, prefix, suffix = recorder.owned(fixture.release['body'])
                meta['identity']['digests']['georelay'] = 'sha256:' + '0' * 64
                marker = base64.b64encode(json.dumps(meta).encode()).decode()
                fixture.release['body'] = recorder.BEGIN + '\n<!-- georelay-provenance:' + marker + ' -->\n' + text + recorder.END
            with self.subTest(case=case), self.assertRaises(recorder.RecordError):
                fixture.record()
            self.assertEqual(fixture.writes(), [])

    def test_product_changes_require_readable_fragment_same_upstream_and_mixed_notes(self):
        fixture = Fixture()
        fixture.old_pin = fixture.pin
        fixture.diff['files'] = [dict(filename='adapter/server.py', status='modified')]
        with self.assertRaisesRegex(recorder.RecordError, 'product_changes_need_notes'):
            fixture.record()
        self.assertEqual(fixture.writes(), [])
        fixture.diff['files'].append(dict(filename='docs/changes/addresses.md', status='added'))
        fixture.record()
        self.assertIn('(unchanged)', fixture.release['body'])
        self.assertIn('Preserve original coordinates', fixture.release['body'])
        fixture = Fixture()
        fixture.diff['files'] = [dict(filename='adapter/server.py', status='modified'), dict(filename='docs/changes/addresses.md', status='added')]
        fixture.record()
        self.assertIn('v4.2.0 → v4.3.0', fixture.release['body'])
        self.assertIn('Preserve original coordinates', fixture.release['body'])

    def test_receipt_archive_is_single_bounded_json_only(self):
        for raw in (zipped({}, '../publication-receipt.json'), b'x' * (recorder.LIMIT + 1), zipped('x' * 65536)):
            fixture = Fixture()
            fixture.download = lambda _: raw
            with self.assertRaises((ValueError, KeyError)):
                fixture.record()
            self.assertEqual(fixture.writes(), [])

    def test_repair_only_substitutes_record_failure_and_reads_exact_original_attempt(self):
        fixture = Fixture()
        fixture.record()
        fixture.run.update(status='completed', conclusion='failure')
        next(job for job in fixture.jobs if job['name'] == 'release-record')['conclusion'] = 'failure'
        self.assertEqual(recorder.repair_proof(REPO, 10, 1, HEAD, fixture.version, 99,
            api=fixture.api, fetch=fixture.fetch, download=fixture.download)['receipt']['version'], fixture.version)
        for case in ('verify', 'publish', 'other', 'wrong_repair', 'candidate_repair'):
            other = copy.deepcopy(fixture)
            if case in {'verify', 'publish'}:
                next(job for job in other.jobs if job['name'] == case)['conclusion'] = 'failure'
            elif case == 'other':
                other.jobs.append(dict(id=55, name='finalizer', run_id=10, status='completed', conclusion='failure'))
            elif case == 'wrong_repair':
                other.repair['display_title'] = 'release-record/10/2/' + HEAD + '/' + fixture.version
            else:
                other.repair['head_branch'] = 'feature'
            with self.subTest(case=case), self.assertRaises(ValueError):
                recorder.repair_proof(REPO, 10, 1, HEAD, other.version, 99, api=other.api, fetch=other.fetch, download=other.download)

    def test_repository_change_notes_are_bounded_readable_text(self):
        root = Path(__file__).resolve().parents[1]
        for fragment in (root / 'docs/changes').glob('*.md'):
            self.assertTrue(recorder.change_note(fragment.read_text()).startswith('# '))

    def test_alias_outcome_update_preserves_notes_baseline_and_manual_text(self):
        fixture = Fixture(stable=True)
        next(job for job in fixture.jobs if job['name'] == 'publish')['conclusion'] = 'failure'
        fixture.receipt['floating'] = dict(tag='latest', status='failed', reason='promotion_incomplete')
        fixture.record()
        previous, _, _, _ = recorder.owned(fixture.release['body'])
        fixture.release['body'] = 'Human intro\n' + fixture.release['body'] + '\nHuman note'
        fixture.calls.clear()
        next(job for job in fixture.jobs if job['name'] == 'publish')['conclusion'] = 'success'
        fixture.receipt['floating'] = dict(tag='latest', status='promoted', reason='verified')
        fixture.record()
        current, text, prefix, suffix = recorder.owned(fixture.release['body'])
        self.assertEqual(previous['baseline'], current['baseline'])
        self.assertIn('**promoted**', text)
        self.assertEqual(prefix, 'Human intro\n')
        self.assertEqual(suffix, '\nHuman note')
        self.assertEqual([method for method, _, _ in fixture.writes()], ['PATCH'])

    def test_compare_truncation_duplicate_receipts_and_prerequisite_pending_reject_before_writes(self):
        cases = [lambda f: f.diff.update(total_commits=101), lambda f: f.diff.update(commits=[]),
                 lambda f: f.diff['files'].append(copy.deepcopy(f.diff['files'][0])),
                 lambda f: f.artifacts.append(dict(f.artifacts[0], id=51)),
                 lambda f: f.jobs[0].update(status='in_progress')]
        for edit in cases:
            fixture = Fixture()
            edit(fixture)
            with self.assertRaises(ValueError):
                fixture.record()
            self.assertEqual(fixture.writes(), [])

    def test_native_api_distinguishes_status_and_never_includes_remote_body_in_errors(self):
        from urllib.error import HTTPError
        class Opener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 403, 'private remote body', {}, io.BytesIO(b'private token'))
        with patch.object(recorder, 'build_opener', return_value=Opener()):
            with self.assertRaises(recorder.APIError) as error:
                recorder.github('GET', 'repos/fixture/georelay/releases/latest')
        self.assertEqual(error.exception.status, 403)
        self.assertNotIn('private', str(error.exception))
        for status in (401, 403, 500, None):
            with self.assertRaises(recorder.APIError):
                recorder.absent(lambda *args: (_ for _ in ()).throw(recorder.APIError(status)), 'repos/fixture/georelay/releases/latest')
        self.assertIsNone(recorder.absent(lambda *args: (_ for _ in ()).throw(recorder.APIError(404)), 'repos/fixture/georelay/releases/latest'))

    def test_workflow_main_writer_isolated_with_minimum_permissions_and_no_rebuild_repair(self):
        root = Path(__file__).resolve().parents[1]
        ci = (root / '.github/workflows/ci.yml').read_text()
        job = ci.split('\n  release-record:\n')[1].split('\n  main-failure-notification:')[0]
        self.assertIn('ref: main', job)
        for permission in ('contents: write', 'actions: read', 'checks: read', 'packages: read', 'pull-requests: read'):
            self.assertIn(permission, job)
        self.assertNotIn('download-artifact', job)
        self.assertNotIn('contents: write', ci.split('\n  publish:\n')[1].split('\n  release-record:\n')[0])
        repair = (root / '.github/workflows/release-only.yml').read_text()
        self.assertIn('ref: main', repair)
        self.assertNotIn('docker ', repair)
        self.assertNotIn('download-artifact', repair)
        self.assertIn('bootstrap_not_enabled', job)


if __name__ == '__main__':
    unittest.main()
