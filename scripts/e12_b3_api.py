"""E12 B3 API client and contract recorder.

The client talks to the existing loopback API, records the complete request /
poll / artifact exchange, and verifies the two idempotency contracts required
by the E12 handoff.  It deliberately uses only the Python standard library so
the same command runs on the course host and in CI.
"""

import argparse
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def http_json(url, method='GET', payload=None, timeout=30):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    headers = {'Accept': 'application/json'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = response.status
            response_headers = dict(response.headers.items())
    except HTTPError as exc:
        raw = exc.read()
        status = exc.code
        response_headers = dict(exc.headers.items())
    except URLError as exc:
        raise RuntimeError(f'API request failed: {url}: {exc}') from exc
    try:
        body = json.loads(raw.decode('utf-8')) if raw else None
    except json.JSONDecodeError:
        body = {'raw': raw.decode('utf-8', errors='replace')}
    return status, response_headers, body, raw


def artifact_path(uri, job_id):
    prefix = f'artifact://{job_id}/'
    if not isinstance(uri, str) or not uri.startswith(prefix):
        raise AssertionError(f'artifact URI is not bound to {job_id}: {uri!r}')
    relative = uri[len(prefix):]
    path = Path(relative)
    if (not relative or relative.startswith(('/', '\\')) or path.is_absolute()
            or '..' in path.parts or '\\' in relative):
        raise AssertionError(f'unsafe artifact URI: {uri!r}')
    return relative


def select_artifact(artifacts, job_id, relative):
    expected_uri = f'artifact://{job_id}/{relative}'
    for item in artifacts:
        if item.get('uri') == expected_uri:
            return item
    raise AssertionError(f'missing artifact: {expected_uri}')


def download_artifact(base_url, job_id, item, out):
    relative = artifact_path(item['uri'], job_id)
    url = f"{base_url}/v1/jobs/{job_id}/files/{quote(relative, safe='/')}"
    status, headers, body, raw = http_json(url)
    if status != 200:
        raise AssertionError(f'download failed for {relative}: HTTP {status} {body!r}')
    actual = sha256_bytes(raw)
    expected = item.get('sha256')
    header = headers.get('X-Content-SHA256') or headers.get('x-content-sha256')
    if actual != expected or header != actual:
        raise AssertionError(
            f'hash mismatch for {relative}: manifest={expected}, header={header}, actual={actual}')
    destination = Path(out) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return {'path': relative, 'uri': item['uri'], 'bytes': len(raw),
            'manifest_sha256': expected, 'header_sha256': header,
            'download_sha256': actual, 'matches': True}


def poll_job(base_url, job_id, out, interval, timeout):
    started = time.monotonic()
    records = []
    while True:
        status, _, body, _ = http_json(f'{base_url}/v1/jobs/{job_id}')
        if status != 200:
            raise AssertionError(f'job poll failed: HTTP {status} {body!r}')
        records.append(body)
        if body.get('status') in {'SUCCEEDED', 'FAILED', 'TIMED_OUT'}:
            write_json(Path(out) / 'poll.json', records)
            return body
        if time.monotonic() - started >= timeout:
            write_json(Path(out) / 'poll.json', records)
            raise AssertionError(f'job did not finish within {timeout}s')
        time.sleep(interval)


def run(args):
    out = Path(args.out)
    if out.exists():
        raise RuntimeError(f'OUTPUT_EXISTS: {out}')
    out.mkdir(parents=True)
    base_url = args.base_url.rstrip('/')
    request_input = json.loads(Path(args.request).read_text(encoding='utf-8'))
    key = args.idempotency_key
    payload = {'idempotency_key': key, 'input': request_input}
    write_json(out / 'api-request.json', payload)
    write_json(out / 'request-input.json', request_input)
    request_hash = sha256_bytes(canonical(request_input))

    health_status, _, health, _ = http_json(f'{base_url}/health')
    if health_status != 200 or health.get('status') != 'ok':
        raise AssertionError(f'health check failed: HTTP {health_status} {health!r}')
    write_json(out / 'health.json', health)

    submit_status, _, submit, _ = http_json(f'{base_url}/v1/jobs', 'POST', payload)
    if submit_status != 202 or not submit.get('job_id'):
        raise AssertionError(f'submit failed: HTTP {submit_status} {submit!r}')
    write_json(out / 'submit.json', submit)
    job_id = submit['job_id']

    final = poll_job(base_url, job_id, out, args.poll_interval, args.timeout)
    if final.get('status') != 'SUCCEEDED' or not final.get('trace_id'):
        raise AssertionError(f'job did not succeed: {final!r}')
    trace_id = final['trace_id']

    artifact_status, _, artifacts, _ = http_json(f'{base_url}/v1/jobs/{job_id}/artifacts')
    if artifact_status != 200 or not isinstance(artifacts.get('artifacts'), list):
        raise AssertionError(f'artifact listing failed: HTTP {artifact_status} {artifacts!r}')
    for item in artifacts['artifacts']:
        artifact_path(item.get('uri'), job_id)
    write_json(out / 'artifacts.json', artifacts)

    selected = [
        'candidate.patch',
        'repair-plan.json',
        'validation/validation.json',
        'recheck.json',
    ]
    downloads = []
    for relative in selected:
        item = select_artifact(artifacts['artifacts'], job_id, relative)
        downloads.append(download_artifact(base_url, job_id, item, out / 'downloads'))
    write_json(out / 'downloads.json', downloads)

    replay_status, _, replay, _ = http_json(f'{base_url}/v1/jobs', 'POST', payload)
    replay_ok = replay_status == 202 and replay.get('job_id') == job_id
    write_json(out / 'idempotent-replay.json', {
        'http_status': replay_status, 'same_job_id': replay.get('job_id'),
        'expected_job_id': job_id, 'passed': replay_ok, 'response': replay,
    })
    if not replay_ok:
        raise AssertionError(f'idempotent replay failed: HTTP {replay_status} {replay!r}')

    conflict_input = dict(request_input)
    conflict_input['target'] = '0' * 40
    conflict_payload = {'idempotency_key': key, 'input': conflict_input}
    conflict_status, _, conflict, _ = http_json(f'{base_url}/v1/jobs', 'POST', conflict_payload)
    conflict_ok = conflict_status == 409 and conflict.get('error') == 'IDEMPOTENCY_CONFLICT'
    write_json(out / 'conflict-request.json', conflict_payload)
    write_json(out / 'conflict-response.json', {
        'http_status': conflict_status, 'expected_status': 409,
        'expected_error': 'IDEMPOTENCY_CONFLICT', 'passed': conflict_ok,
        'response': conflict,
    })
    if not conflict_ok:
        raise AssertionError(f'conflict contract failed: HTTP {conflict_status} {conflict!r}')

    handoff = {
        'schema_version': 'e12-b3-handoff-1',
        'student_id': '241880300',
        'role': 'E12-B3',
        'status': 'SUCCEEDED',
        'branch': 'e12-zyh-b3',
        'base_url': base_url,
        'ssh_forwarding': 'ssh -N -L 18081:127.0.0.1:8080 <account>@<api-server>',
        'request_sha256': request_hash,
        'job_id': job_id,
        'trace_id': trace_id,
        'final_status': final['status'],
        'artifact_count': len(artifacts['artifacts']),
        'downloads': downloads,
        'contracts': {
            'submit': True,
            'poll': True,
            'artifact_hashes': all(item['matches'] for item in downloads),
            'idempotent_replay_same_job': replay_ok,
            'conflict_409': conflict_ok,
        },
    }
    write_json(out / 'handoff.json', handoff)
    return handoff


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--idempotency-key', default='e12-b3-241880300')
    parser.add_argument('--poll-interval', type=float, default=2)
    parser.add_argument('--timeout', type=float, default=900)
    args = parser.parse_args()
    try:
        result = run(args)
    except (AssertionError, OSError, RuntimeError, KeyError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
