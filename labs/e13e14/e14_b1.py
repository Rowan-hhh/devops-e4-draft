"""E14 B1 local identity and evidence checks; no services are started."""
import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import traceback
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASELINE = '77da560719fe7835c227a289b6bc99295fa5abcc'
B4 = '1c7e79196c11f655d23f23e7e11d69f3bb045463'
STAGES = ('draft', 'full-check', 'incremental-check', 'repair', 'recheck')
ROLES = {'buildchecker': 18081, 'echecker': 18082, 'draft': 18083, 'mdfixer': 18084}
SHA = re.compile(r'[0-9a-f]{40}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    path = checked_path(path, Path('/'), must_exist=True)
    value = json.loads(path.read_bytes())
    require(isinstance(value, dict), 'JSON object required')
    return value


def git(repo, *args, check=True):
    return subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check).stdout


def commit(repo, value):
    require(isinstance(value, str) and SHA.fullmatch(value), 'full commit SHA required')
    require(git(repo, 'rev-parse', '--verify', value + '^{commit}').decode().strip() == value,
            'commit mismatch')
    return value


def ancestor(repo, a, b):
    require(subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', a, b],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0,
            'not an ancestor')


def preflight(root=ROOT):
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    commit(root, head)
    require(not git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all'), 'repository dirty')
    commit(root, BASELINE)
    commit(root, B4)
    ancestor(root, B4, BASELINE)
    ancestor(root, BASELINE, head)
    h = read(root / 'reports/E13/B4/handoff.json')
    r = read(root / 'reports/E13/B4/result.json')
    text = (root / 'reports/E13/B4/README.md').read_text(encoding='utf-8')
    require(h.get('status') == r.get('status') == 'PASS' and h.get('gate') == 'E13_PASS', 'gate failed')
    require(all(h.get('c1_c8', {}).get(f'C{i}') == r.get('cases', {}).get(f'C{i}') == 'PASS' for i in range(1, 9)), 'C gate failed')
    require(all(h.get('teacher_projects', {}).get(x) == r.get('teacher_projects', {}).get(x) == 'PASS' for x in ('H1-jsmn', 'H2-inih', 'H3-tiny-AES')), 'teacher gate failed')
    receipt = h.get('a_group_receipt', {})
    require(receipt.get('status') == r.get('a_group_receipt') == 'ACCEPTED' and set(receipt.get('scope', [])) >= {'C4', 'C7'} and '签收' in text, 'receipt missing')
    return {'status': 'E13_GATE_BASELINE', 'head': head, 'e13_baseline': BASELINE}


def checked_path(path, root, must_exist=False):
    raw = os.fspath(path)
    require(isinstance(raw, str) and '\x00' not in raw, 'invalid path')
    require('//' not in raw and all(part not in ('.', '..') for part in raw.split('/') if part), 'noncanonical path')
    root = Path(root).absolute()
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    require(path == root or path.is_relative_to(root), 'path outside allowed root')
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            require(not stat.S_ISLNK(current.lstat().st_mode), 'symlink forbidden')
        except FileNotFoundError:
            if must_exist: raise
    require(not must_exist or path.exists(), 'path missing')
    return path


def git_tree(repo, head):
    commit(repo, head)
    result = {}
    for entry in filter(None, git(repo, 'ls-tree', '-r', '-z', head).split(b'\0')):
        metadata, raw_name = entry.split(b'\t', 1)
        mode, typ, oid = metadata.decode('ascii').split(' ')
        name = os.fsdecode(raw_name)
        require(mode in ('100644', '100755') and typ == 'blob' and SHA.fullmatch(oid), 'unsupported tree entry')
        require(name not in result, 'duplicate tree entry')
        result[name] = (mode, oid)
    return result


def file_info(path):
    data = Path(path).read_bytes()
    return {'bytes': len(data), 'sha256': digest(data)}


def ensure_info(path, info):
    actual = file_info(path)
    require(type(info.get('bytes')) is int and actual == {'bytes': info['bytes'], 'sha256': info.get('sha256')}, 'file hash or size mismatch')
    return actual


def seal_run(out):
    out = Path(out); run = out / 'run'; sealed = out / 'sealed-run'
    require(not sealed.exists() and not sealed.is_symlink(), 'sealed directory exists')
    result_path = checked_path(run / 'result.json', run, must_exist=True)
    result_raw = result_path.read_bytes()
    result = json.loads(result_raw)
    job, trace = result['job_id'], result['trace_id']
    require(isinstance(job, str) and job and isinstance(trace, str) and trace, 'missing job or trace')
    sealed.mkdir(); files = sealed / 'files'; files.mkdir()
    entries = []; seen = set()
    for item in result['artifacts']:
        relative = checked_artifact(run, item, job)
        require(relative not in seen, 'duplicate artifact')
        seen.add(relative)
        source = checked_path(run / relative, run, must_exist=True)
        target = checked_path(files / relative, files)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as dest: dest.write(source.read_bytes())
        after = ensure_info(target, item)
        entries.append({'uri': item['uri'], 'relative_path': relative, 'declared_bytes': item['bytes'], 'declared_sha256': item['sha256'], 'sealed_path': 'files/' + relative, 'sealed_bytes': after['bytes'], 'sealed_sha256': after['sha256']})
    control = run / 'result.json'
    raw = control.read_bytes(); require(raw == result_raw, 'result changed during sealing')
    (sealed / 'result.json').write_bytes(raw)
    return {'schema_version': 'e14-b1-sealed-1', 'job_id': job, 'trace_id': trace,
            'result': {'bytes': len(raw), 'sha256': digest(raw)}, 'artifacts': entries,
            'sealed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}


def finish_manifest(out, manifest):
    controls = {}
    for name in ('request.json', 'source-before.json', 'source-after.json', 'console.log', 'exit-code.txt', 'execution.json', 'failure.json'):
        path = Path(out) / name
        if path.exists(): controls[name] = file_info(checked_path(path, out, must_exist=True))
    controls['sealed-inputs/manifest.json'] = file_info(checked_path(Path(out) / 'sealed-inputs/manifest.json', out, must_exist=True))
    manifest['control_files'] = controls
    write_new(Path(out) / 'sealed-run/manifest.json', manifest)


def verify_manifest(out, manifest):
    sealed = out / 'sealed-run'; files = sealed / 'files'
    require(manifest.get('schema_version') == 'e14-b1-sealed-1', 'invalid sealed manifest')
    ensure_info(checked_path(sealed / 'result.json', sealed, must_exist=True), manifest['result'])
    result = read(sealed / 'result.json')
    require(result.get('job_id') == manifest.get('job_id') and result.get('trace_id') == manifest.get('trace_id'), 'manifest identity mismatch')
    expected = result['artifacts']; entries = manifest['artifacts']
    require(len(expected) == len(entries), 'manifest artifact count mismatch')
    seen = set()
    for item, entry in zip(expected, entries):
        rel = checked_artifact(files, item, result['job_id'])
        require(rel not in seen and entry == {'uri': item['uri'], 'relative_path': rel, 'declared_bytes': item['bytes'], 'declared_sha256': item['sha256'], 'sealed_path': 'files/' + rel, 'sealed_bytes': item['bytes'], 'sealed_sha256': item['sha256']}, 'sealed manifest mismatch')
        seen.add(rel)
    controls = manifest['control_files']
    require(set(controls) >= {'request.json', 'source-before.json', 'source-after.json', 'console.log', 'exit-code.txt', 'execution.json', 'sealed-inputs/manifest.json'}, 'wrapper evidence missing')
    for name, info in controls.items():
        require(name in ('request.json', 'source-before.json', 'source-after.json', 'console.log', 'exit-code.txt', 'execution.json', 'failure.json', 'sealed-inputs/manifest.json'), 'invalid wrapper control')
        ensure_info(checked_path(out / name, out, must_exist=True), info)
    require(read(out / 'execution.json').get('run_return_code') == 0 and 'failure.json' not in controls, 'execution failed')


def seal_inputs(out, info, before, root=ROOT):
    out = Path(out); folder = out / 'sealed-inputs'; folder.mkdir()
    repo = Path(info['repo']); req = info['request']
    require(before['head'] == req['target'], 'source HEAD must equal target')
    for rev in (req['base'], req['target'], before['head']): commit(repo, rev)
    ancestor(repo, req['base'], req['target'])
    input_files = [('request.json', out / 'request.json'), ('candidate.Dockerfile', Path(info['candidate_path']))]
    if req.get('fixed_report') is not None: input_files.append(('fixed-report.json', safe_path(root, req['fixed_report'])))
    for name, src in input_files:
        src = checked_path(src, root, must_exist=True)
        (folder / name).write_bytes(src.read_bytes())
    require(digest((folder / 'request.json').read_bytes()) == info['request_sha256'], 'request copy changed')
    require(digest((folder / 'candidate.Dockerfile').read_bytes()) == info['candidate_sha256'], 'candidate changed')
    if info['fixed_report_sha256'] is not None: require(digest((folder / 'fixed-report.json').read_bytes()) == info['fixed_report_sha256'], 'fixed report changed')
    bundle = folder / 'source.bundle'
    git(repo, 'bundle', 'create', str(bundle), '--all')
    git(repo, 'bundle', 'verify', str(bundle))
    with tempfile.TemporaryDirectory(prefix='e14-b1-bundle-') as temp:
        recovered = recover_bundle(bundle, Path(temp), req, before)
        require(git_tree(recovered, before['head']) == git_tree(repo, before['head']), 'bundle tree differs')
    entries = {name: {'path': name, **file_info(folder / name)} for name in
               ('request.json', 'candidate.Dockerfile', 'source.bundle')}
    entries['fixed-report.json'] = ({'path': 'fixed-report.json', **file_info(folder / 'fixed-report.json')} if info['fixed_report_sha256'] is not None else None)
    manifest = {'schema_version': 'e14-b1-inputs-1', 'files': entries,
                'request_paths': {k: req.get(k) for k in ('repo', 'candidate', 'fixed_report')},
                'base': req['base'], 'target': req['target'], 'head': before['head'],
                'bundle_verified': True, 'restore_verified': True}
    write_new(folder / 'manifest.json', manifest)
    return manifest


def recover_bundle(bundle, temp, req, before):
    temp = Path(temp)
    probe = temp / 'probe'; probe.mkdir()
    git(probe, 'init', '-q')
    git(probe, 'bundle', 'verify', str(bundle))
    recovered = temp / 'recovered'
    subprocess.run(['git', 'clone', '--quiet', '--no-checkout', str(bundle), str(recovered)],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for rev in (req['base'], req['target'], before['head']): commit(recovered, rev)
    ancestor(recovered, req['base'], req['target'])
    require(before['head'] == req['target'], 'snapshot target differs')
    git(recovered, 'checkout', '--quiet', '--detach', before['head'])
    tree = git_tree(recovered, before['head'])
    require(set(tree) == {x['path'] for x in before['tracked_files']}, 'bundle paths differ')
    for item in before['tracked_files']:
        require(tree[item['path']] == (item['git_mode'], item['git_blob_oid']), 'bundle blob differs')
        data = git(recovered, 'cat-file', 'blob', item['git_blob_oid'])
        require(len(data) == item['bytes'] and digest(data) == item['sha256'], 'bundle content differs')
    return recovered


def verify_inputs(out, before, temp):
    folder = out / 'sealed-inputs'
    manifest = read(folder / 'manifest.json')
    require(manifest.get('schema_version') == 'e14-b1-inputs-1' and manifest.get('bundle_verified') is True and manifest.get('restore_verified') is True, 'invalid input manifest')
    require(set(manifest['files']) == {'request.json', 'candidate.Dockerfile', 'fixed-report.json', 'source.bundle'}, 'input manifest incomplete')
    for name, item in manifest['files'].items():
        if name == 'fixed-report.json' and item is None: continue
        require(item['path'] == name, 'invalid input path')
        ensure_info(checked_path(folder / name, folder, must_exist=True), item)
    req = read(folder / 'request.json')
    require(req == read(out / 'request.json') and manifest['request_paths'] == {k: req.get(k) for k in ('repo', 'candidate', 'fixed_report')}, 'request identity differs')
    require(manifest['base'] == req['base'] and manifest['target'] == req['target'] and manifest['head'] == before['head'], 'input commits differ')
    require(file_info(folder / 'request.json')['sha256'] == before['request_sha256'] and file_info(folder / 'candidate.Dockerfile')['sha256'] == before['candidate_sha256'] and ((manifest['files']['fixed-report.json'] is None and before['fixed_report_sha256'] is None and req.get('fixed_report') is None) or (manifest['files']['fixed-report.json'] is not None and file_info(folder / 'fixed-report.json')['sha256'] == before['fixed_report_sha256'] and req.get('fixed_report') is not None)), 'snapshot input mismatch')
    recovered = recover_bundle(folder / 'source.bundle', temp, req, before)
    return {'request': req, 'request_sha256': file_info(folder / 'request.json')['sha256'],
            'candidate_sha256': file_info(folder / 'candidate.Dockerfile')['sha256'],
            'repo': before['canonical_repo_path'], 'proof_repo': str(recovered)}


def safe_path(root, value):
    require(isinstance(value, str) and value.startswith('/course/data/'), 'path must be under /course/data')
    parts = PurePosixPath(value).parts
    require('//' not in value and all(p not in ('.', '..') for p in value.split('/')) and len(parts) > 3, 'invalid path')
    path = root.joinpath(*parts[2:])
    current = root
    for part in parts[2:]:
        current = current / part
        require(not current.is_symlink(), 'symlink forbidden')
    require(path.resolve().is_relative_to((root / 'data').resolve()), 'path escape')
    return path.resolve()


def inspect_request(path, root=ROOT):
    path = checked_path(path, root, must_exist=True)
    raw = path.read_bytes()
    req = json.loads(raw)
    require(isinstance(req, dict) and req.get('mode') == 'e12', 'mode must be e12')
    for key in ('repo', 'base', 'target', 'candidate', 'expected_output', 'build_timeout'):
        require(key in req, 'missing ' + key)
    require(isinstance(req['expected_output'], str) and req['expected_output'] != '', 'invalid expected output')
    require(type(req['build_timeout']) in (int, float) and 0 < req['build_timeout'] < float('inf'), 'invalid timeout')
    repo, candidate = [safe_path(root, req[x]) for x in ('repo', 'candidate')]
    fixed = safe_path(root, req['fixed_report']) if req.get('fixed_report') is not None else None
    require(repo.is_dir() and candidate.is_file() and (fixed is None or fixed.is_file()), 'input missing')
    require(Path(os.fsdecode(git(repo, 'rev-parse', '--show-toplevel')).strip()).resolve() == repo, 'repo must be git root')
    commit(repo, req['base']); commit(repo, req['target']); ancestor(repo, req['base'], req['target'])
    lines = [x.strip() for x in candidate.read_text(encoding='utf-8').splitlines() if re.match(r'^\s*FROM\s', x, re.I)]
    require(len(lines) == 1, 'single pinned FROM required')
    match = re.fullmatch(r'FROM\s+([^\s@]+)@sha256:([0-9a-f]{64})(?:\s+AS\s+\S+)?', lines[0], re.I)
    require(match is not None and not match.group(1).lower().endswith(':latest'), 'floating FROM')
    return {'request': req, 'request_sha256': digest(raw), 'candidate_sha256': digest(candidate.read_bytes()),
            'fixed_report_sha256': digest(fixed.read_bytes()) if fixed is not None else None, 'from_image': match.group(1),
            'from_digest': 'sha256:' + match.group(2), 'repo': str(repo), 'root': str(root), 'request_path': str(Path(path).resolve()), 'candidate_path': str(candidate)}


def snapshot(info, evidence_dir, run_dir, require_clean=False):
    repo = Path(info['repo'])
    status = git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all')
    require(not require_clean or not status, 'source repository dirty')
    head = git(repo, 'rev-parse', 'HEAD').decode().strip(); commit(repo, head)
    branch_result = subprocess.run(['git', '-C', str(repo), 'symbolic-ref', '--quiet', '--short', 'HEAD'], capture_output=True)
    require(branch_result.returncode in (0, 1), 'cannot inspect branch')
    entries = git(repo, 'ls-files', '--stage', '-z').split(b'\0')
    tree = git_tree(repo, head)
    files = []; seen = set()
    for entry in filter(None, entries):
        meta, name = entry.split(b'\t', 1)
        mode, oid, stage = meta.decode('ascii').split(' ')
        require(stage == '0' and mode in ('100644', '100755'), 'unsupported tracked mode')
        name = os.fsdecode(name)
        parts = PurePosixPath(name).parts
        require(parts and not PurePosixPath(name).is_absolute() and all(p not in ('.', '..') for p in parts) and name not in seen, 'invalid tracked path')
        seen.add(name)
        file = repo.joinpath(*parts)
        for parent in [file, *file.parents]:
            if parent == repo: break
            require(not parent.is_symlink(), 'tracked symlink forbidden')
        require(file.resolve().is_relative_to(repo) and stat.S_ISREG(file.lstat().st_mode), 'unsupported tracked file')
        content = file.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        require(tree.get(name) == (mode, oid) and blob == oid, 'tree, index and worktree differ')
        files.append({'path': name, 'git_mode': mode, 'git_blob_oid': oid, 'type': 'file', 'bytes': len(content), 'sha256': digest(content)})
    require(seen == set(tree), 'tree and index paths differ')
    return {'schema_version': 'e14-b1-source-1', 'captured_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'canonical_repo_path': str(repo), 'head': head, 'detached': branch_result.returncode == 1,
            'branch': branch_result.stdout.decode().strip() if branch_result.returncode == 0 else None,
            'status_base64': base64.b64encode(status).decode(), 'status_sha256': digest(status),
            'tracked_files': files, 'request_sha256': digest(Path(info['request_path']).read_bytes()), 'candidate_sha256': digest(Path(info['candidate_path']).read_bytes()),
            'fixed_report_sha256': digest(safe_path(Path(info['root']), info['request']['fixed_report']).read_bytes()) if info['request'].get('fixed_report') is not None else None,
            'request_repo': info['request']['repo'], 'resolved_request_repo': str(repo),
            'evidence_dir': str(Path(evidence_dir).resolve()), 'run_dir': str(Path(run_dir).resolve())}


def compare_snapshots(before, after, info, evidence, run):
    keys = ('schema_version', 'canonical_repo_path', 'head', 'detached', 'branch', 'status_base64', 'status_sha256', 'tracked_files', 'request_sha256', 'candidate_sha256', 'fixed_report_sha256', 'request_repo', 'resolved_request_repo', 'evidence_dir', 'run_dir')
    require(all(k in before and k in after and before[k] == after[k] for k in keys), 'source boundary changed')
    require(before['schema_version'] == 'e14-b1-source-1' and before['canonical_repo_path'] == before['resolved_request_repo'] == info['repo'] and before['request_repo'] == info['request']['repo'], 'source path mismatch')
    require(before['request_sha256'] == info['request_sha256'] and before['candidate_sha256'] == info['candidate_sha256'], 'source input binding mismatch')
    require(before['run_dir'] == str(Path(before['evidence_dir']) / 'run'), 'run binding mismatch')
    status = base64.b64decode(before['status_base64'], validate=True)
    require(not status and digest(status) == before['status_sha256'], 'source not clean')
    require(SHA.fullmatch(before['head']) and isinstance(before['tracked_files'], list) and before['tracked_files'], 'invalid source snapshot')
    names = set()
    repo = Path(info.get('proof_repo', info['repo']))
    tree = git_tree(repo, before['head']) if repo.exists() else None
    if tree is not None: require(git(repo, 'rev-parse', 'HEAD').decode().strip() == before['head'], 'current repository HEAD differs')
    for item in before['tracked_files']:
        name = item['path']; parts = PurePosixPath(name).parts
        require(parts and not PurePosixPath(name).is_absolute() and all(p not in ('.', '..') for p in parts) and name not in names, 'invalid source file')
        names.add(name)
        require(item['git_mode'] in ('100644', '100755') and item['type'] == 'file' and type(item['bytes']) is int and item['bytes'] >= 0 and HASH.fullmatch(item['sha256']) and SHA.fullmatch(item['git_blob_oid']), 'invalid source metadata')
        if tree is not None:
            require(tree.get(name) == (item['git_mode'], item['git_blob_oid']), 'snapshot differs from git tree')
            blob = git(repo, 'cat-file', 'blob', item['git_blob_oid'])
            require(len(blob) == item['bytes'] and digest(blob) == item['sha256'], 'snapshot differs from blob')
    if tree is not None: require(names == set(tree), 'snapshot tree paths differ')


def checked_artifact(run, item, job):
    uri = item['uri']; prefix = 'artifact://' + job + '/'
    require(isinstance(uri, str) and uri.startswith(prefix), 'artifact job mismatch')
    relative = uri[len(prefix):]
    parts = PurePosixPath(relative).parts
    require(parts and not PurePosixPath(relative).is_absolute() and PurePosixPath(relative).as_posix() == relative and all(x not in ('', '.', '..') for x in relative.split('/')), 'invalid artifact path')
    path = run.joinpath(*parts)
    current = run
    for part in parts:
        current = current / part
        require(not current.is_symlink(), 'artifact symlink')
    require(path.is_file() and path.resolve().is_relative_to(run.resolve()), 'artifact missing')
    content = path.read_bytes()
    require(type(item.get('bytes')) is int and len(content) == item['bytes'] and digest(content) == item.get('sha256'), 'artifact hash or size mismatch')
    return relative


def verify_run(evidence, root=ROOT, live_source=None):
    evidence = checked_path(evidence, Path('/'), must_exist=True)
    original_run = evidence / 'run'
    manifest = read(evidence / 'sealed-run/manifest.json')
    verify_manifest(evidence, manifest)
    run = evidence / 'sealed-run/files'
    before = read(evidence / 'source-before.json'); after = read(evidence / 'source-after.json')
    with tempfile.TemporaryDirectory(prefix='e14-b1-verify-') as temp:
        info = verify_inputs(evidence, before, Path(temp))
        require(read(run / 'request.json') == info['request'], 'run request mismatch')
        compare_snapshots(before, after, info, evidence, original_run)
        if live_source is not None:
            live = checked_path(live_source, Path('/'), must_exist=True)
            require(str(live) == before['canonical_repo_path'], 'live source path differs')
            require(git(live, 'rev-parse', 'HEAD').decode().strip() == before['head'] and git_tree(live, before['head']) == git_tree(Path(info['proof_repo']), before['head']), 'live source differs')
            require(not git(live, 'status', '--porcelain=v1', '-z', '--untracked-files=all'), 'live source dirty')
            for item in before['tracked_files']:
                path = checked_path(live / item['path'], live, must_exist=True)
                require(file_info(path) == {'bytes': item['bytes'], 'sha256': item['sha256']}, 'live source bytes differ')
    require((evidence / 'exit-code.txt').read_text().strip() == '0' and (evidence / 'console.log').is_file(), 'run exit evidence missing')
    result = read(evidence / 'sealed-run/result.json'); job = result.get('job_id'); trace = result.get('trace_id')
    require(result.get('schema_version') == 'e11e12-1' and result.get('status') == 'SUCCEEDED' and isinstance(job, str) and job and isinstance(trace, str) and trace, 'run identity missing')
    require(result.get('base_commit') == info['request']['base'] and result.get('target_commit') == info['request']['target'], 'run target mismatch')
    require([x.get('name') for x in result['stages']] == list(STAGES), 'stage order mismatch')
    artifacts = result['artifacts']; seen = set()
    for item in artifacts:
        name = checked_artifact(run, item, job); require(name not in seen, 'duplicate artifact'); seen.add(name)
    stages = {}
    for item in result['stages']:
        name = item['name']; ref = item['artifact']
        require(checked_artifact(run, ref, job) == name + '.json' and name + '.json' in seen, 'stage artifact missing')
        stage = read(run / (name + '.json')); stages[name] = stage
        expected_commit = info['request']['base'] if name == 'full-check' else info['request']['target']
        require(stage.get('schema_version') == 'e11e12-1' and stage.get('kind') == name and stage.get('status') == 'SUCCEEDED' and stage.get('job_id') == job and stage.get('trace_id') == trace and stage.get('commit') == expected_commit, 'stage identity mismatch')
        nested = set()
        for ref in stage['artifacts']:
            n = checked_artifact(run, ref, job); require(n not in nested and n in seen, 'stage artifact missing or duplicate'); nested.add(n)
    inc = stages['incremental-check']; require(inc['data'].get('commit') == info['request']['target'], 'report target mismatch')
    require(checked_artifact(run, stages['repair']['data']['input_report'], job) == 'incremental-check.json', 'wrong report')
    require('candidate.patch' in seen and (run / 'candidate.patch').stat().st_size > 0 and 'validation/validation.json' in seen and any(x['uri'] == 'artifact://' + job + '/candidate.patch' for x in stages['repair']['artifacts']) and any(x['uri'] == 'artifact://' + job + '/validation/validation.json' for x in stages['recheck']['artifacts']), 'patch or validation missing')
    validation = read(run / 'validation/validation.json'); recheck = stages['recheck']['data']
    require(validation.get('accepted') is True and recheck.get('validation') == validation and all(validation.get('checks', {}).get(k) is True for k in ('patch_applies', 'build', 'test', 'header_change', 'no_missing')), 'validation failed')
    require(isinstance(recheck.get('findings'), list) and not any(x.get('type') == 'MISSING' for x in recheck['findings']), 'missing dependencies')
    require('draft-build/verify.log' in seen and 'draft-build/result.json' in seen, 'draft verification evidence missing')
    require(read(run / 'draft-build/result.json') == stages['draft']['data'], 'draft execution record mismatch')
    verify = stages['draft']['data']['verification']; expected = info['request']['expected_output']
    stdout = (run / 'draft-build/verify.log').read_bytes().decode('utf-8')
    require(stdout == verify.get('actual_output'), 'verification log differs from stage')
    require(stages['draft']['data'].get('candidate_sha256') == info['candidate_sha256'] and verify.get('exit_code') == 0 and verify.get('expected_output') == expected and verify.get('actual_output', '').rstrip('\r\n') == expected and verify.get('output_matches') is True, 'output mismatch')
    return {'status': 'VERIFIED', 'source_boundary': '原始输入仓库在运行前后边界状态一致。'}


def handoff(path, root=ROOT):
    root = Path(root).resolve()
    path = checked_path(path, root / 'work')
    if not path.exists(): return {'status': 'BLOCKED_ON_B2_HANDOFF'}
    path = checked_path(path, root / 'work', must_exist=True)
    h = read(path)
    require(isinstance(h.get('candidate_commit'), str) and SHA.fullmatch(h['candidate_commit']), 'candidate SHA invalid')
    def package_file(item):
        require(isinstance(item, dict), 'file metadata required')
        name = item.get('path')
        require(isinstance(name, str) and not Path(name).is_absolute(), 'relative package path required')
        file = checked_path(path.parent / name, path.parent, must_exist=True)
        require(file.is_file(), 'package file missing')
        ensure_info(file, item)
        return file
    package_file(h['compose'])
    config = read(package_file(h['rendered_config']))
    services = config.get('services'); require(isinstance(services, dict) and set(services) == set(ROLES), 'four services required')
    image = h['image']; tag = image.get('tag')
    require(isinstance(tag, str) and re.fullmatch(r'[^\s@]+:[A-Za-z0-9_][A-Za-z0-9_.-]*', tag) and tag.rsplit(':', 1)[-1].lower() not in {'latest', 'main', 'master', 'dev', 'edge', 'stable', 'nightly'}, 'explicit non-latest tag required')
    require(re.fullmatch(r'sha256:[0-9a-f]{64}', image.get('image_id', '')), 'image ID missing')
    require((isinstance(image.get('repo_digest'), str) and re.fullmatch(r'.+@sha256:[0-9a-f]{64}', image['repo_digest'])) or (image.get('repo_digest') is None and isinstance(image.get('repo_digest_absent_reason'), str) and image['repo_digest_absent_reason'].strip()), 'RepoDigest missing reason')
    require(set(h['health']) == set(ROLES) and set(h['logs']) == set(ROLES), 'health and logs require four roles')
    for role, port in ROLES.items():
        s = services[role]; require(h['health'][role] == 'healthy', 'service unhealthy')
        require(s.get('image') == tag, 'service image mismatch')
        ports = s.get('ports'); require(isinstance(ports, list) and len(ports) == 1 and ports[0].get('host_ip') == '127.0.0.1' and str(ports[0].get('published')) == str(port) and ports[0].get('target') == 8080, 'invalid ports')
        sockets = [x for x in s.get('volumes', []) if x.get('source') == '/var/run/docker.sock' or x.get('target') == '/var/run/docker.sock']
        require((len(sockets) == 1 and sockets[0].get('source') == sockets[0].get('target') == '/var/run/docker.sock') if role == 'draft' else not sockets, 'invalid socket mount')
        package_file(h['logs'][role])
    e2e = h.get('e2e')
    require(isinstance(e2e, dict), 'E2E metadata required')
    e2e_file = package_file({
        'path': e2e.get('result_path'),
        'bytes': e2e.get('result_bytes'),
        'sha256': e2e.get('result_sha256'),
    })
    e2e_result = read(e2e_file)
    expected_stages = [
        'draft',
        'full-check',
        'incremental-check',
        'repair',
        'recheck',
    ]
    require(
        isinstance(e2e.get('job_id'), str) and e2e['job_id']
        and isinstance(e2e.get('trace_id'), str) and e2e['trace_id'],
        'E2E job or trace missing',
    )
    require(
        e2e.get('status') == 'SUCCEEDED'
        and e2e.get('exit_code') == 0,
        'E2E outcome invalid',
    )
    require(e2e.get('stages') == expected_stages, 'E2E stages invalid')
    require(
        e2e_result.get('job_id') == e2e['job_id']
        and e2e_result.get('trace_id') == e2e['trace_id'],
        'E2E identity mismatch',
    )
    require(
        e2e_result.get('status') == e2e['status'],
        'E2E status mismatch',
    )
    require(
        [x.get('name') for x in e2e_result.get('stages', [])]
        == expected_stages,
        'E2E result stages invalid',
    )
    require(
        e2e_result.get('base_commit') == e2e.get('base_commit')
        and e2e_result.get('target_commit') == e2e.get('target_commit'),
        'E2E commits mismatch',
    )
    return {'status': 'HANDOFF_VERIFIED', 'scope': 'B2 交接包内部一致性核验', 'candidate_commit': h['candidate_commit']}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as f: json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')


def exception_record(exc):
    return {'type': type(exc).__name__, 'message': str(exc),
            'traceback': ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}


def single_run(request, out, root=ROOT, runner=subprocess.run):
    root = Path(root).resolve()
    request = checked_path(request, root, must_exist=True)
    out = checked_path(out, root / 'work')
    require(out != root / 'work' and not out.exists(), 'new output under work required')
    info = inspect_request(request, root)
    raw = request.read_bytes()
    require(digest(raw) == info['request_sha256'], 'request changed during inspection')
    before = snapshot(info, out, out / 'run', require_clean=True)
    out.mkdir(parents=True, exist_ok=False)
    errors = {'run_exception': None, 'sealing_exception': None, 'source_after_exception': None,
              'finish_manifest_exception': None, 'failure_record_exception': None, 'run_return_code': None}
    primary = None; manifest = None
    try:
        write_new(out / 'source-before.json', before)
        with (out / 'request.json').open('xb') as f: f.write(raw)
        seal_inputs(out, info, before, root)
        require(digest((out / 'request.json').read_bytes()) == info['request_sha256'], 'request copy mismatch')
        result = runner([sys.executable, str(root / 'run_e11e12.py'), 'run', '--request', str((out / 'request.json').relative_to(root)), '--out', str((out / 'run').relative_to(root))], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        errors['run_return_code'] = result.returncode
        (out / 'console.log').write_bytes(result.stdout)
        (out / 'exit-code.txt').write_text(str(result.returncode) + '\n', encoding='utf-8')
        if result.returncode != 0:
            raise RuntimeError('single-container command exited ' + str(result.returncode))
    except BaseException as exc:
        errors['run_exception'] = exception_record(exc); primary = exc
    try:
        manifest = seal_run(out)
    except BaseException as exc:
        errors['sealing_exception'] = exception_record(exc)
        if primary is None: primary = exc
    try:
        write_new(out / 'source-after.json', snapshot(info, out, out / 'run'))
    except BaseException as exc:
        errors['source_after_exception'] = exception_record(exc)
        if primary is None: primary = exc
    errors['primary_failure'] = next((key for key in ('run_exception', 'sealing_exception', 'source_after_exception') if errors[key] is not None), None)
    errors['primary_failure_kind'] = errors['primary_failure'].removesuffix('_exception') if errors['primary_failure'] else None
    errors['status'] = 'FAILED' if primary is not None else 'RUN_COMPLETED'
    try:
        write_new(out / 'execution.json', errors)
    except BaseException as exc:
        errors['failure_record_exception'] = exception_record(exc)
        if primary is None:
            primary = exc
            errors['primary_failure_kind'] = 'failure_record'
        errors['status'] = 'FAILED'
    if manifest is not None:
        try:
            finish_manifest(out, manifest)
        except BaseException as exc:
            errors['finish_manifest_exception'] = exception_record(exc)
            if primary is None:
                primary = exc
                errors['primary_failure_kind'] = 'finish_manifest'
                errors['primary_failure'] = 'finish_manifest_exception'
            errors['status'] = 'FAILED'
    if primary is not None:
        try:
            (out / 'execution.json').write_text(json.dumps(errors, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except BaseException as exc:
            errors['failure_record_exception'] = exception_record(exc)
            try:
                primary.add_note('Execution recording also failed: ' + repr(exc))
            except AttributeError:
                pass
        try:
            write_new(out / 'failure.json', {'status': 'FAILED', **errors})
        except BaseException as exc:
            errors['failure_record_exception'] = exception_record(exc)
            try:
                (out / 'execution.json').write_text(json.dumps(errors, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            except BaseException:
                pass
            try:
                primary.add_note('Failure recording also failed: ' + repr(exc))
            except AttributeError:
                pass
    if primary is not None:
        raise primary.with_traceback(primary.__traceback__)
    return {'status': 'RUN_COMPLETED', 'evidence': str(out)}


def main():
    parser = argparse.ArgumentParser(description=__doc__); subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('preflight')
    p = subs.add_parser('inspect-request'); p.add_argument('--request', required=True)
    p = subs.add_parser('snapshot-source'); p.add_argument('--request', required=True); p.add_argument('--out', required=True); p.add_argument('--run-dir', required=True)
    p = subs.add_parser('single-run'); p.add_argument('--request', required=True); p.add_argument('--out', required=True)
    p = subs.add_parser('verify-single-run'); p.add_argument('--evidence', required=True); mode = p.add_mutually_exclusive_group(); mode.add_argument('--offline', action='store_true'); mode.add_argument('--live-source')
    p = subs.add_parser('verify-service-handoff'); p.add_argument('--handoff', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'preflight': result = preflight()
        elif args.command == 'inspect-request': result = inspect_request(args.request)
        elif args.command == 'snapshot-source':
            out = checked_path(args.out, ROOT / 'work'); require(out != ROOT / 'work' and not out.exists(), 'new output under work required'); checked_path(args.run_dir, ROOT / 'work')
            info = inspect_request(args.request); data = snapshot(info, out.parent, args.run_dir, require_clean=True); write_new(out, data); result = {'status': 'SNAPSHOT_WRITTEN'}
        elif args.command == 'single-run': result = single_run(args.request, args.out)
        elif args.command == 'verify-single-run': result = verify_run(args.evidence, live_source=args.live_source)
        else: result = handoff(args.handoff)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 2 if result.get('status') == 'BLOCKED_ON_B2_HANDOFF' else 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'FAILED', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr); return 1


if __name__ == '__main__': sys.exit(main())
