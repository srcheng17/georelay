#!/usr/bin/env python3
"""Record verified fixed image pairs using trusted main code; never build or push."""

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import zipfile

from image_context import commit, publication_receipt

PACKAGES = ('georelay', 'georelay-adapter')
REQUIRED = {'checks', 'build-amd64', 'build-arm64', 'verify'}
TITLE = re.compile(r'images/(pull_request|push|workflow_dispatch)/(0|[1-9]\d*)/([0-9a-f]{40})/publish/(-|[0-9a-f]{40})')
BEGIN = '<!-- georelay-release-record:start -->'
END = '<!-- georelay-release-record:end -->'
MARKER = re.compile(r'<!-- georelay-provenance:([A-Za-z0-9+/=]+) -->\n')
LIMIT = 1_048_576


class RecordError(ValueError):
    """Fixed safe failure category; no remote response text."""


class APIError(RecordError):
    def __init__(self, status=None):
        self.status = status
        super().__init__('api_permission' if status in {401, 403} else 'api_response')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def github(method, path, payload=None):
    """JSON via the native token, bounded, with distinguishable 404/403."""
    if not isinstance(path, str) or not path.startswith('repos/') or any(c in path for c in '\r\n'):
        raise RecordError('api_path')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
               'User-Agent': 'georelay-release-record', 'Authorization': 'Bearer ' + token}
    data = None if payload is None else json.dumps(payload).encode()
    request = Request('https://api.github.com/' + path, data=data, headers=headers, method=method)
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise RecordError('api_size')
        return json.loads(raw) if raw else None
    except HTTPError as error:
        raise APIError(error.code) from None
    except (URLError, TimeoutError, OSError):
        raise APIError() from None


def absent(api, path):
    try:
        return api('GET', path)
    except APIError as error:
        if error.status == 404:
            return None
        raise


def archive(path):
    """Follow only an HTTPS data redirect, never forward the token to storage."""
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
    request = Request('https://api.github.com/' + path, headers={'Authorization': 'Bearer ' + token})
    opener = build_opener(NoRedirect())
    try:
        try:
            response = opener.open(request, timeout=30)
        except HTTPError as error:
            if error.code != 302:
                raise APIError(error.code) from None
            location = error.headers.get('Location', '')
            url = urlsplit(location)
            if url.scheme != 'https' or url.username or url.password or not url.hostname:
                raise RecordError('artifact_redirect')
            # No Authorization header on the signed storage request.
            response = opener.open(Request(location), timeout=30)
        with response:
            raw = response.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise RecordError('artifact_size')
        return raw
    except (URLError, TimeoutError, OSError):
        raise RecordError('artifact_download') from None


def pages(api, path, key=None, max_pages=10):
    rows, seen = [], set()
    separator = '&' if '?' in path else '?'
    total = None
    for page in range(1, max_pages + 1):
        data = api('GET', path + separator + 'per_page=100&page=' + str(page))
        items = data if key is None else data[key]
        if not isinstance(items, list) or len(items) > 100:
            raise RecordError('pagination')
        if key is not None:
            if total is None:
                total = data['total_count']
            if type(total) is not int or total < 0 or data['total_count'] != total:
                raise RecordError('pagination')
        for item in items:
            identity = item.get('id')
            if type(identity) is not int or identity < 1 or identity in seen:
                raise RecordError('pagination')
            seen.add(identity)
            rows.append(item)
        if len(items) < 100:
            if total is not None and total != len(rows):
                raise RecordError('pagination')
            return rows
    raise RecordError('pagination_limit')


def text_file(api, root, path, revision, limit=65536):
    data = api('GET', root + '/contents/' + quote(path, safe='/') + '?ref=' + commit(revision))
    if data.get('type') != 'file' or data.get('encoding') != 'base64':
        raise RecordError('source_text')
    raw = base64.b64decode(data['content'].replace('\n', ''), validate=True)
    if len(raw) > limit:
        raise RecordError('source_text_size')
    return raw.decode('utf-8')


def pin_at(api, root, revision):
    pin = json.loads(text_file(api, root, 'upstream.json', revision))
    if (pin.get('repository') != 'https://github.com/teslamate-org/teslamate.git'
            or not re.fullmatch(r'v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)', pin.get('tag', ''))):
        raise RecordError('upstream_pin')
    commit(pin['commit'])
    return pin


def resolve_ref(api, root, name, allow_absent=False):
    path = root + '/git/ref/' + name
    reference = absent(api, path) if allow_absent else api('GET', path)
    if reference is None:
        return None
    obj = reference['object']
    seen = set()
    for _ in range(8):
        revision = commit(obj['sha'])
        if revision in seen:
            raise RecordError('tag_cycle')
        seen.add(revision)
        if obj['type'] == 'commit':
            return revision
        if obj['type'] != 'tag':
            raise RecordError('tag_type')
        obj = api('GET', root + '/git/tags/' + revision)['object']
    raise RecordError('tag_depth')


def original_run(api, repository, run_id, attempt, source):
    root = 'repos/' + repository
    run = api('GET', root + '/actions/runs/' + str(run_id) + '/attempts/' + str(attempt))
    workflow = api('GET', root + '/actions/workflows/ci.yml')
    title = TITLE.fullmatch(run.get('display_title', ''))
    if (run.get('id') != run_id or run.get('run_attempt') != attempt
            or run.get('status') not in {'in_progress', 'completed'}
            or run.get('workflow_id') != workflow.get('id') or workflow.get('path') != '.github/workflows/ci.yml'
            or workflow.get('name') != 'Validate and build' or not title
            or run.get('repository', {}).get('full_name') != repository
            or run.get('head_repository', {}).get('full_name') != repository):
        raise RecordError('run_provenance')
    event, pull, revision, expected = title.groups()
    branch = run.get('head_branch')
    stable = branch == 'main'
    if (run.get('event') != event or run.get('head_sha') != source or revision != source
            or run.get('html_url') != 'https://github.com/' + repository + '/actions/runs/' + str(run_id)
            or (event == 'push' and not stable) or (event == 'pull_request' and (stable or pull == '0'))
            or (not stable and expected != '-')
            or (stable and event != 'workflow_dispatch' and (pull != '0' or expected != '-'))
            or (expected != '-' and expected != source)):
        raise RecordError('run_source')
    run['channel'] = 'stable' if stable else 'beta'
    run['source_pr'] = int(pull)
    jobs = pages(api, root + '/actions/runs/' + str(run_id) + '/attempts/' + str(attempt) + '/jobs', 'jobs')
    selected = {}
    for job in jobs:
        name = job.get('name')
        if job.get('run_id') != run_id or name in selected:
            raise RecordError('job_provenance')
        selected[name] = job
    for name in REQUIRED:
        job = selected.get(name, {})
        if job.get('status') != 'completed' or job.get('conclusion') != 'success':
            raise RecordError('prerequisite_jobs')
    publisher = selected.get('publish', {})
    if publisher.get('status') != 'completed' or publisher.get('conclusion') not in {'success', 'failure'}:
        raise RecordError('publication_job')
    verify = selected['verify']
    check_url = verify.get('check_run_url', '')
    if not re.fullmatch(r'https://api\.github\.com/' + re.escape(root) + r'/check-runs/[1-9]\d*', check_url):
        raise RecordError('verify_provenance')
    check = api('GET', check_url.removeprefix('https://api.github.com/'))
    if (check.get('app', {}).get('id') != 15368 or check.get('name') != 'verify'
            or check.get('head_sha') != source or check.get('status') != 'completed'
            or check.get('conclusion') != 'success'
            or check.get('details_url') != run['html_url'] + '/job/' + str(verify['id'])):
        raise RecordError('verify_provenance')
    return run, selected


def receipt_name(run_id, attempt, source, version):
    return 'publication-receipt-' + '-'.join(map(str, (run_id, attempt, source, version)))


def read_receipt(api, root, run_id, attempt, source, version, download=archive):
    name = receipt_name(run_id, attempt, source, version)
    artifacts = pages(api, root + '/actions/runs/' + str(run_id) + '/artifacts', 'artifacts')
    matches = [item for item in artifacts if item.get('name') == name]
    if len(matches) != 1:
        raise RecordError('receipt_missing')
    item = matches[0]
    if (item.get('expired') is not False or type(item.get('size_in_bytes')) is not int
            or not 0 < item['size_in_bytes'] <= LIMIT
            or item.get('workflow_run', {}).get('id') != run_id
            or item['workflow_run'].get('head_sha') != source):
        raise RecordError('receipt_artifact')
    raw = download(root + '/actions/artifacts/' + str(item['id']) + '/zip')
    if len(raw) > LIMIT:
        raise RecordError('receipt_archive_size')
    with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
        members = zipped.infolist()
        if (len(members) != 1 or members[0].filename != 'publication-receipt.json'
                or not 0 < members[0].file_size <= 65536 or members[0].flag_bits & 1):
            raise RecordError('receipt_archive')
        data = json.loads(zipped.read(members[0]))
    return data


def verify_images(repository, source, version, digests, fetch=None):
    # Reuse the existing registry transport, SHA256 descriptor and OCI validation.
    from release_control import registry_document, verify_beta
    fetch = fetch or registry_document
    verify_beta(repository, source, version, fetch)
    owner = repository.split('/')[0]
    for package in PACKAGES:
        raw = fetch(owner, package, version)
        digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
        if digest != digests[package] or fetch(owner, package, digest) != raw:
            raise RecordError('fixed_index_digest')
        index = json.loads(raw)
        for entry in index['manifests']:
            arch = entry['platform']['architecture']
            architecture_raw = fetch(owner, package, version + '-' + arch)
            if 'sha256:' + hashlib.sha256(architecture_raw).hexdigest() != entry['digest']:
                raise RecordError('architecture_tag_digest')


def evidence(repository, run_id, attempt, source, version, api=github, fetch=None, download=archive):
    if (not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)
            or type(run_id) is not int or run_id < 1 or type(attempt) is not int or attempt < 1):
        raise RecordError('input_identity')
    commit(source)
    root = 'repos/' + repository
    run, jobs = original_run(api, repository, run_id, attempt, source)
    pin = pin_at(api, root, source)
    official = 'repos/teslamate-org/teslamate'
    release = api('GET', official + '/releases/tags/' + pin['tag'])
    if (release.get('tag_name') != pin['tag'] or release.get('draft') is not False
            or release.get('prerelease') is not False or resolve_ref(api, official, 'tags/' + pin['tag']) != pin['commit']):
        raise RecordError('official_pin')
    data = read_receipt(api, root, run_id, attempt, source, version, download)
    normalized = publication_receipt(dict(source_sha=source, channel=run['channel'], version=version), pin,
                                     data['digests'], data['floating'], run_id, attempt)
    if (type(data.get('schema')) is not int or type(data.get('fixed_verified')) is not bool
            or type(data.get('run_id')) is not int or type(data.get('attempt')) is not int
            or data != normalized):
        raise RecordError('receipt_identity')
    expected_alias = 'latest' if run['channel'] == 'stable' else ('beta-pr-' + str(run['source_pr']) if run['source_pr'] else '')
    if data['floating']['tag'] != expected_alias:
        raise RecordError('receipt_alias')
    if ((jobs['publish']['conclusion'] == 'failure') != (data['floating']['status'] == 'failed')):
        raise RecordError('receipt_publication_outcome')
    verify_images(repository, source, version, data['digests'], fetch)
    return dict(receipt=data, run=run, jobs=jobs, pin=pin)


def owned(body):
    if not isinstance(body, str) or len(body.encode()) > 131072 or body.count(BEGIN) != 1 or body.count(END) != 1:
        raise RecordError('release_ownership')
    start = body.index(BEGIN)
    finish = body.index(END)
    if finish < start:
        raise RecordError('release_ownership')
    block = body[start + len(BEGIN):finish]
    if not block.startswith('\n'):
        raise RecordError('release_ownership')
    match = MARKER.match(block[1:])
    if not match:
        raise RecordError('release_ownership')
    meta = json.loads(base64.b64decode(match[1], validate=True))
    text = block[1 + match.end():]
    if (set(meta) != {'schema', 'writer', 'identity', 'baseline', 'run_id', 'attempt', 'floating', 'text_sha256'}
            or type(meta.get('schema')) is not int or meta.get('schema') != 1 or meta.get('writer') != 'georelay-main'
            or type(meta.get('run_id')) is not int or meta['run_id'] < 1
            or type(meta.get('attempt')) is not int or meta['attempt'] < 1
            or hashlib.sha256(text.encode()).hexdigest() != meta.get('text_sha256')):
        raise RecordError('release_owned_content_modified')
    item = meta['identity']
    publication_receipt(dict(source_sha=item['source_sha'], channel=item['channel'], version=item['version']),
                        item['upstream'], item['digests'], meta['floating'], meta['run_id'], meta['attempt'])
    return meta, text, body[:start], body[finish + len(END):]


def identity(record):
    receipt = record['receipt']
    return {key: receipt[key] for key in ('source_sha', 'channel', 'version', 'upstream', 'digests')}


def validate_baseline(api, root, source, base):
    if not isinstance(base, dict) or set(base) != {'kind', 'source_sha', 'upstream', 'tag'}:
        raise RecordError('baseline_schema')
    if base['kind'] == 'unavailable':
        if (any(base[key] is not None for key in ('source_sha', 'upstream', 'tag'))
                or api('GET', root + '/git/commits/' + source)['parents']):
            raise RecordError('baseline_schema')
        return
    if base['kind'] not in {'previous_stable_release', 'source_parent_not_published'}:
        raise RecordError('baseline_schema')
    previous = commit(base['source_sha'])
    if previous == source:
        raise RecordError('baseline_source')
    ancestry = api('GET', root + '/compare/' + previous + '...' + source + '?per_page=100')
    if ancestry.get('status') != 'ahead' or ancestry.get('merge_base_commit', {}).get('sha') != previous:
        raise RecordError('baseline_source')
    pin = pin_at(api, root, previous)
    if base['upstream'] != {key: pin[key] for key in ('tag', 'commit')}:
        raise RecordError('baseline_pin')
    if base['kind'] == 'source_parent_not_published':
        parents = api('GET', root + '/git/commits/' + source)['parents']
        if not parents or parents[0].get('sha') != previous or base['tag'] is not None:
            raise RecordError('baseline_parent')
    else:
        expected = pin['tag'] + '-georelay-' + previous
        if base['tag'] != expected or resolve_ref(api, root, 'tags/' + expected) != previous:
            raise RecordError('baseline_tag')
        prior = api('GET', root + '/releases/tags/' + expected)
        meta, _, _, _ = owned(prior.get('body'))
        previous_identity = meta.get('identity', {})
        if (prior.get('author', {}).get('login') != 'github-actions[bot]' or prior.get('draft') is not False
                or prior.get('prerelease') is not False or prior.get('tag_name') != expected
                or previous_identity.get('source_sha') != previous or previous_identity.get('version') != expected
                or previous_identity.get('channel') != 'stable' or previous_identity.get('upstream') != base['upstream']):
            raise RecordError('baseline_record')


def validate_release(api, root, record, release):
    data = record['receipt']
    if (release.get('author', {}).get('login') != 'github-actions[bot]'
            or release.get('tag_name') != data['version'] or release.get('draft') is not False
            or release.get('prerelease') is not (data['channel'] == 'beta')
            or resolve_ref(api, root, 'tags/' + data['version']) != data['source_sha']):
        raise RecordError('release_source')
    meta, text, prefix, suffix = owned(release.get('body'))
    if meta.get('identity') != identity(record):
        raise RecordError('release_identity_conflict')
    validate_baseline(api, root, data['source_sha'], meta.get('baseline'))
    return meta, text, prefix, suffix


def comparison(api, root, base, source):
    data = api('GET', root + '/compare/' + commit(base) + '...' + commit(source) + '?per_page=100')
    if (data.get('status') != 'ahead' or data.get('merge_base_commit', {}).get('sha') != base
            or type(data.get('total_commits')) is not int or not 0 < data['total_commits'] <= 100
            or len(data.get('commits', [])) != data['total_commits'] or len(data.get('files', [])) >= 300):
        raise RecordError('source_comparison')
    filenames = [item['filename'] for item in data['files']]
    if len(filenames) != len(set(filenames)):
        raise RecordError('source_comparison')
    return data


def baseline(api, root, record):
    source = record['receipt']['source_sha']
    candidates = []
    for release in pages(api, root + '/releases'):
        if release.get('draft') is not False or release.get('prerelease') is not False:
            continue
        body = release.get('body', '')
        if BEGIN not in body:
            continue  # Human releases are not a proven GeoRelay baseline.
        meta, _, _, _ = owned(body)
        item = meta['identity']
        previous = commit(item['source_sha'])
        if release.get('author', {}).get('login') != 'github-actions[bot]':
            raise RecordError('baseline_ownership')
        if item['channel'] != 'stable' or previous == source:
            continue
        expected_version = item['upstream']['tag'] + '-georelay-' + previous
        if item['version'] != expected_version or release.get('tag_name') != expected_version:
            raise RecordError('baseline_identity')
        if resolve_ref(api, root, 'tags/' + expected_version) != previous:
            raise RecordError('baseline_source')
        compare = api('GET', root + '/compare/' + previous + '...' + source + '?per_page=100')
        if compare.get('status') == 'ahead' and compare.get('merge_base_commit', {}).get('sha') == previous:
            candidates.append((compare['total_commits'], previous, item['upstream'], expected_version))
    if candidates:
        candidates.sort()
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise RecordError('baseline_ambiguous')
        _, previous, upstream, tag = candidates[0]
        if pin_at(api, root, previous)['tag'] != upstream['tag'] or pin_at(api, root, previous)['commit'] != upstream['commit']:
            raise RecordError('baseline_pin')
        return dict(kind='previous_stable_release', source_sha=previous, upstream=upstream, tag=tag)
    # A first release can describe the direct source diff but cannot call it published.
    parents = api('GET', root + '/git/commits/' + source)['parents']
    if parents:
        previous = commit(parents[0]['sha'])
        pin = pin_at(api, root, previous)
        return dict(kind='source_parent_not_published', source_sha=previous,
                    upstream={key: pin[key] for key in ('tag', 'commit')}, tag=None)
    return dict(kind='unavailable', source_sha=None, upstream=None, tag=None)


def change_note(text):
    text = text.strip()
    if (not text.startswith('# ') or len(text) < 32 or len(text.encode()) > 65536
            or any(marker in text for marker in (BEGIN, END, 'georelay-provenance:'))):
        raise RecordError('change_note_format')
    return text


def floating_line(outcome):
    return 'Fixed image pair: verified. Floating tag `' + (outcome['tag'] or '(none)') + '`: **' + outcome['status'] + '** (' + outcome['reason'] + ').'


def notes(api, root, record, base):
    receipt, pin, run = record['receipt'], record['pin'], record['run']
    lines = ['## Updates', '']
    if base['kind'] != 'previous_stable_release':
        lines.append('First recorded release; no provable previous published version. Source-diff baseline: ' + base['kind'] + '.')
    previous = base['upstream']
    if previous and previous != receipt['upstream']:
        lines.extend(['TeslaMate upstream: **' + previous['tag'] + ' → ' + pin['tag'] + '**.',
                      'Official release: https://github.com/teslamate-org/teslamate/releases/tag/' + pin['tag'],
                      'Official changes: https://github.com/teslamate-org/teslamate/compare/' + previous['commit'] + '...' + pin['commit']])
    else:
        lines.append('TeslaMate upstream: ' + pin['tag'] + (' (unchanged).' if previous else '.'))
    if base['source_sha']:
        diff = comparison(api, root, base['source_sha'], receipt['source_sha'])
        paths = {item['filename'] for item in diff['files']}
        fragments = [item for item in diff['files'] if item['filename'].startswith('docs/changes/')
                     and item['filename'].endswith('.md') and item['status'] != 'removed']
        changed_fragments = []
        for item in fragments:
            current_text = change_note(text_file(api, root, item['filename'], receipt['source_sha']))
            if item['status'] in {'modified', 'renamed'}:
                previous_path = item.get('previous_filename', item['filename'])
                if text_file(api, root, previous_path, base['source_sha']).strip() == current_text:
                    continue
            changed_fragments.append((item['filename'], current_text))
        product_change = any(path.startswith(('adapter/', 'patches/')) for path in paths)
        if product_change and not changed_fragments:
            raise RecordError('product_changes_need_notes')
        if paths == {'upstream.json'}:
            lines.append('GeoRelay follows the pinned official upstream release; no local feature changes.')
        elif changed_fragments:
            lines += ['', '### GeoRelay changes']
            for filename, text in sorted(changed_fragments):
                lines += ['', text]
        else:
            lines += ['', 'GeoRelay maintenance changes (verified commit summaries):']
            for item in diff['commits']:
                revision = commit(item['sha'])
                summary = item['commit']['message'].splitlines()[0][:300]
                summary = summary.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                lines.append('- ' + summary + ' (https://github.com/' + record['repository'] + '/commit/' + revision + ')')
    else:
        lines.append('No provable source-diff baseline; consult the exact source below.')
    lines += ['', '## Published images', '', 'Platforms: `linux/amd64`, `linux/arm64`.']
    for package in PACKAGES:
        reference = 'ghcr.io/' + record['repository'].split('/')[0].lower() + '/' + package
        lines += ['- `' + reference + ':' + receipt['version'] + '`', '  Digest: `' + reference + '@' + receipt['digests'][package] + '`']
    outcome = receipt['floating']
    lines += ['', floating_line(outcome),
              'Upstream: `' + pin['tag'] + '` / `' + pin['commit'] + '`.',
              'Source: https://github.com/' + record['repository'] + '/commit/' + receipt['source_sha'],
              'Validation/publication: ' + run['html_url'] + '/attempts/' + str(receipt['attempt'])]
    if run['source_pr']:
        pull = absent(api, root + '/pulls/' + str(run['source_pr']))
        associated = (pull is not None and pull.get('number') == run['source_pr']
            and pull.get('head', {}).get('repo', {}).get('full_name') == record['repository']
            and pull.get('base', {}).get('repo', {}).get('full_name') == record['repository']
            and ((receipt['channel'] == 'beta' and pull['head'].get('sha') == receipt['source_sha'])
                 or (receipt['channel'] == 'stable' and pull.get('merge_commit_sha') == receipt['source_sha'])))
        if associated:
            lines.append('PR: https://github.com/' + record['repository'] + '/pull/' + str(run['source_pr']))
        else:
            lines.append('Current PR association is no longer provable; PR link omitted. Exact source and original Actions evidence remain above.')
    lines += ['No deployment performed.', '']
    result = '\n'.join(lines)
    if len(result.encode()) > 65536:
        raise RecordError('release_body_size')
    return result


def is_latest(api, root, record, fetch=None):
    receipt = record['receipt']
    if receipt['channel'] != 'stable' or receipt['floating']['status'] != 'promoted':
        return False
    if resolve_ref(api, root, 'heads/main') != receipt['source_sha']:
        return False
    if pin_at(api, root, receipt['source_sha']) != record['pin']:
        return False
    from release_control import registry_document
    fetch = fetch or registry_document
    owner = record['repository'].split('/')[0]
    return all('sha256:' + hashlib.sha256(fetch(owner, package, 'latest')).hexdigest() == receipt['digests'][package]
               for package in PACKAGES)


def record(repository, run_id, attempt, source, version, api=github, fetch=None, download=archive, apply=False, repair=False):
    proven = evidence(repository, run_id, attempt, source, version, api, fetch, download)
    if repair and proven['run'].get('status') != 'completed':
        raise RecordError('repair_original_pending')
    proven['repository'] = repository
    root = 'repos/' + repository
    release_path = root + '/releases/tags/' + version
    existing = absent(api, release_path)
    tag = resolve_ref(api, root, 'tags/' + version, allow_absent=True)
    if tag is not None and tag != source:
        raise RecordError('tag_source_conflict')
    if existing is not None:
        meta, text, prefix, suffix = validate_release(api, root, proven, existing)
        # Immutable text/baseline is frozen after first recording. Preserve manual surroundings.
        if existing.get('immutable') is True:
            if meta.get('floating') != proven['receipt']['floating']:
                raise RecordError('release_immutable')
            return dict(status='recorded', version=version, immutable=True)
        base = meta['baseline']
        if meta.get('floating') != proven['receipt']['floating']:
            previous_line = floating_line(meta['floating'])
            if text.count(previous_line) != 1:
                raise RecordError('release_owned_content_modified')
            text = text.replace(previous_line, floating_line(proven['receipt']['floating']))
            meta = dict(meta, floating=proven['receipt']['floating'], text_sha256=hashlib.sha256(text.encode()).hexdigest())
    else:
        base = baseline(api, root, proven)
        text = notes(api, root, proven, base)
        meta = dict(schema=1, writer='georelay-main', identity=identity(proven), baseline=base,
                    run_id=run_id, attempt=attempt, floating=proven['receipt']['floating'], text_sha256=hashlib.sha256(text.encode()).hexdigest())
        prefix = suffix = ''
    marker = base64.b64encode(json.dumps(meta, sort_keys=True, separators=(',', ':')).encode()).decode()
    body = prefix + BEGIN + '\n<!-- georelay-provenance:' + marker + ' -->\n' + text + END + suffix
    latest = is_latest(api, root, proven, fetch)
    if not apply:
        return dict(status='dry_run', version=version, baseline=base, make_latest=latest)
    if tag is None:
        try:
            api('POST', root + '/git/refs', dict(ref='refs/tags/' + version, sha=source))
        except APIError as error:
            if error.status in {401, 403}:
                raise RecordError('tag_permission') from None
            if error.status not in {None, 422}:
                raise
        if resolve_ref(api, root, 'tags/' + version) != source:
            raise RecordError('tag_write_unconfirmed')
    latest = is_latest(api, root, proven, fetch)  # Mutable source/aliases reread after tag write.
    payload = dict(tag_name=version, name=version, body=body, draft=False,
                   prerelease=proven['receipt']['channel'] == 'beta', make_latest='true' if latest else 'false')
    # Never set target_commitish: exact tag must already exist and have been reread.
    if existing is None:
        try:
            api('POST', root + '/releases', payload)
        except APIError as error:
            if error.status in {401, 403}:
                raise RecordError('release_permission') from None
            if error.status not in {None, 422}:
                raise
    else:
        # Identical owned content is already recorded; update only latest status if eligible.
        body_changed = existing['body'] != body
        current_latest = absent(api, root + '/releases/latest') if latest else None
        if body_changed or (latest and (current_latest is None or current_latest.get('id') != existing['id'])):
            try:
                api('PATCH', root + '/releases/' + str(existing['id']), payload)
            except APIError as error:
                if error.status in {401, 403}:
                    raise RecordError('release_permission') from None
                if error.status is not None:
                    raise
    reread = api('GET', release_path)
    validated = validate_release(api, root, proven, reread)
    if validated[0] != meta or reread['body'] != body:
        raise RecordError('release_write_unconfirmed')
    if latest and api('GET', root + '/releases/latest').get('id') != reread.get('id'):
        raise RecordError('latest_write_unconfirmed')
    return dict(status='recorded', version=version, run_id=run_id, attempt=attempt, source_sha=source,
                digests=proven['receipt']['digests'], baseline=base, make_latest=latest)


def verify_record(repository, run_id, attempt, source, version, api=github, fetch=None, download=archive):
    proven = evidence(repository, run_id, attempt, source, version, api, fetch, download)
    root = 'repos/' + repository
    release = api('GET', root + '/releases/tags/' + version)
    meta, _, _, _ = validate_release(api, root, proven, release)
    # Original recording attribution remains frozen across attempts. Current
    # run/attempt still independently proves the identical immutable image pair.
    return proven


def repair_proof(repository, run_id, attempt, source, version, repair_id, api=github, fetch=None, download=archive):
    """Only a trusted successful repair can replace the one failed record gate."""
    root = 'repos/' + repository
    repair = api('GET', root + '/actions/runs/' + str(repair_id))
    workflow = api('GET', root + '/actions/workflows/release-only.yml')
    expected = 'release-record/' + '/'.join(map(str, (run_id, attempt, source, version)))
    if (repair.get('id') != repair_id or repair.get('workflow_id') != workflow.get('id')
            or workflow.get('path') != '.github/workflows/release-only.yml'
            or repair.get('status') != 'completed' or repair.get('conclusion') != 'success'
            or repair.get('event') != 'workflow_dispatch' or repair.get('head_branch') != 'main'
            or repair.get('repository', {}).get('full_name') != repository
            or repair.get('head_repository', {}).get('full_name') != repository or repair.get('display_title') != expected):
        raise RecordError('repair_provenance')
    repair_attempt = repair.get('run_attempt')
    if type(repair_attempt) is not int or repair_attempt < 1:
        raise RecordError('repair_attempt')
    repair_jobs = pages(api, root + '/actions/runs/' + str(repair_id) + '/attempts/' + str(repair_attempt) + '/jobs', 'jobs')
    if (len(repair_jobs) != 1 or repair_jobs[0].get('name') != 'release-record'
            or repair_jobs[0].get('run_id') != repair_id or repair_jobs[0].get('status') != 'completed'
            or repair_jobs[0].get('conclusion') != 'success'):
        raise RecordError('repair_jobs')
    # Trust main ancestry, not a title saying main; historical trusted code must be an ancestor.
    repaired_by = commit(repair['head_sha'])
    current_main = resolve_ref(api, root, 'heads/main')
    if repaired_by != current_main:
        ancestry = api('GET', root + '/compare/' + repaired_by + '...' + current_main)
        if ancestry.get('status') != 'ahead' or ancestry.get('merge_base_commit', {}).get('sha') != repaired_by:
            raise RecordError('repair_main_source')
    proven = verify_record(repository, run_id, attempt, source, version, api, fetch, download)
    if proven['run'].get('status') != 'completed':
        raise RecordError('repair_original_pending')
    jobs = proven['jobs']
    record_gate = jobs.get('release-record', {}).get('conclusion')
    gate_repairable = record_gate in {'failure', 'cancelled'} or (record_gate == 'success' and proven['run'].get('conclusion') == 'success')
    if (not gate_repairable
            or any(job.get('status') != 'completed' or job.get('conclusion') != 'success'
                   for name, job in jobs.items() if name != 'release-record')):
        raise RecordError('repair_other_failure')
    return proven


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--run-id', type=int, default=os.environ.get('ORIGINAL_RUN_ID'))
    parser.add_argument('--attempt', type=int, default=os.environ.get('ORIGINAL_ATTEMPT'))
    parser.add_argument('--source', default=os.environ.get('ORIGINAL_SOURCE'))
    parser.add_argument('--version', default=os.environ.get('ORIGINAL_VERSION'))
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--repair', action='store_true', help='Require completed original publication; never build or push')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = record(args.repository, args.run_id, args.attempt, args.source, args.version, apply=args.apply, repair=args.repair)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile) as error:
        report = dict(status='failed', reason=str(error) if isinstance(error, RecordError) else 'record_validation')
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, separators=(',', ':')))
    return 0 if report['status'] in {'recorded', 'dry_run'} else 1


if __name__ == '__main__':
    sys.exit(main())
