"""E13 B3 orchestration. Formal execution requires an explicitly supplied environment."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
import zipfile


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fresh(path):
    if Path(path).is_symlink():
        raise ValueError('OUTPUT_IS_SYMLINK')
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False)
    return path


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def source_state(repo):
    repo = Path(repo).resolve()
    files = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z'])
    return {'head': git(repo, 'rev-parse', 'HEAD'),
            'status': git(repo, 'status', '--porcelain', '--untracked-files=all'),
            'sha256': {os.fsdecode(p): digest(repo / os.fsdecode(p)) for p in files.split(b'\0') if p}}


def observe():
    result = {}
    for key, cmd in [('processes', ['ps', '-eo', 'pid,ppid,pgid,args']),
                     ('containers', ['docker', 'ps', '-a', '--no-trunc', '--format', '{{.ID}} {{.Names}} {{.Status}}'])]:
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
            result[key] = {'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[key] = {'exit_code': None, 'error': str(exc)}
    return result


def stop_owned(kind, value, owned, runner=subprocess.run):
    """Only exact IDs explicitly registered by this task may be stopped."""
    if value not in owned.get(kind, []):
        raise ValueError('UNKNOWN_RESOURCE')
    if kind == 'pgids':
        if not isinstance(value, int) or value <= 1 or value == os.getpgrp():
            raise ValueError('UNSAFE_PGID')
        try:
            os.killpg(value, signal.SIGKILL)
            return {'kind': kind, 'id': value, 'ok': True}
        except ProcessLookupError:
            return {'kind': kind, 'id': value, 'ok': True, 'already_stopped': True}
        except OSError as exc:
            return {'kind': kind, 'id': value, 'ok': False, 'error': str(exc)}
    if kind == 'containers':
        if not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('INVALID_CONTAINER_ID')
        try:
            p = runner(['docker', 'rm', '-f', value], capture_output=True, text=True, timeout=15, check=False)
            return {'kind': kind, 'id': value, 'ok': p.returncode == 0, 'exit_code': p.returncode,
                    'stdout': p.stdout, 'stderr': p.stderr}
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {'kind': kind, 'id': value, 'ok': False, 'error': str(exc)}
    raise ValueError('UNKNOWN_RESOURCE_KIND')


def run_process(argv, timeout, log):
    """Own a process group and retain logs even if the timeout fires."""
    with Path(log).open('w', encoding='utf-8') as output:
        proc = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        owned = {'pids': [proc.pid], 'pgids': [proc.pid], 'containers': []}
        started = time.time()
        timed_out = False
        cleanup = []
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            cleanup.append(stop_owned('pgids', proc.pid, owned))
            code = proc.wait()
        return {'started_at': started, 'finished_at': time.time(), 'exit_code': code,
                'timed_out': timed_out, 'owned': owned, 'cleanup': cleanup}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


C4_SCOPE = ('结论仅覆盖检查时刻的相关 Docker 构建客户端和准确验证容器；'
            '不证明或清理 BuildKit 全局缓存；未执行 docker prune；'
            '未停止 Docker 服务；未清理无关容器。')
C4_PS = ['ps', '-eo', 'pid=,ppid=,pgid=,args=']
C4_DOCKER_PS = ['docker', 'ps', '--no-trunc', '--format', '{{.ID}} {{.Status}}']


def c4_markers(out, attempts):
    out = Path(out).resolve()
    markers = {str(out), str(out / 'draft-build')}
    try:
        root = Path(__file__).resolve().parents[2]
        relative = out.relative_to(root).as_posix()
        markers.update(('/course/' + relative, '/course/' + relative + '/run/draft-build'))
    except ValueError:
        pass
    for attempt in attempts:
        cmd = attempt.get('command')
        if not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd):
            raise ValueError('invalid build command')
        if not cmd or cmd[0] != 'docker' or cmd[1:2] != ['build'] or '-f' not in cmd or '-t' not in cmd:
            raise ValueError('invalid build attempt')
        dockerfile, tag = cmd[cmd.index('-f') + 1], cmd[cmd.index('-t') + 1]
        context = cmd[-1]
        if not all((dockerfile, tag, context)):
            raise ValueError('empty task marker')
        if attempt.get('tag') != tag:
            raise ValueError('attempt tag mismatch')
        markers.update((dockerfile, tag, context, str(Path(dockerfile).parent.parent)))
    return sorted(markers)


def _c4_scan(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=15, check=False)
        return {'checked_at':time.time(), 'command':argv, 'exit_code':p.returncode,
                'stdout':p.stdout, 'stderr':p.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'checked_at':time.time(), 'command':argv, 'exit_code':None,
                'stdout':'', 'stderr':str(exc)}


def inspect_c4(out, attempts):
    folder = Path(out) / 'processes-and-containers'
    folder.mkdir()
    process = _c4_scan(C4_PS)
    process.update(observer_pid=os.getpid(), observer_ppid=os.getppid(), task_markers=c4_markers(out, attempts))
    save(folder/'process-scan.json', process)
    save(folder/'docker-ps.json', _c4_scan(C4_DOCKER_PS))
    cidfile = Path(out)/'draft-build/verify-container-id.txt'
    if not cidfile.exists():
        (folder/'no-verify-container.txt').write_text('NO_VERIFY_CONTAINER_STARTED\n')
    else:
        cid = cidfile.read_text().strip()
        inspect = _c4_scan(['docker', 'inspect', '--type', 'container', cid]) if re.fullmatch(r'[0-9a-f]{64}', cid) else {
            'command':[], 'exit_code':None, 'stdout':'', 'stderr':'Invalid container ID', 'checked_at':time.time()}
        inspect['cid'] = cid
        save(folder/'verify-container-inspect.json', inspect)


def check_request_project(request, project):
    value = request.get('repo', '')
    if value.startswith('/course/'):
        value = str(Path(__file__).resolve().parents[2] / value[len('/course/'):])
    if not value or Path(value).resolve() != Path(project).resolve():
        raise ValueError('REQUEST_PROJECT_MISMATCH')


def run_c4(entry, project, request_file, out, timeout, build_timeout):
    before = source_state(project)
    save(out/'source-before.json', {'head':before['head'], 'status':before['status'], 'files':before['sha256']})
    request = read_json(request_file)
    check_request_project(request, project)
    if build_timeout <= 0:
        raise ValueError('INVALID_BUILD_TIMEOUT')
    request['build_timeout'] = build_timeout
    save(out/'request.json', request)
    run = launch(entry, out/'request.json', out/'run', out/'console.log', timeout)
    (out/'exit-code.txt').write_text(str(run['exit_code']) + '\n')
    after = source_state(project)
    save(out/'source-after.json', {'head':after['head'], 'status':after['status'], 'files':after['sha256']})
    for name in ('result.json', 'draft-build'):
        src = out/'run'/name
        if src.is_file():
            shutil.copy2(src, out/name)
        elif src.is_dir():
            shutil.copytree(src, out/name, ignore=shutil.ignore_patterns('project', '.git'))
    inner = read_json(out/'draft-build/result.json') if (out/'draft-build/result.json').is_file() else {}
    inspect_c4(out, inner.get('attempts', []))
    verdict = verify_c4_directory(out)
    save(out/'evidence.json', {'case':'C4', **verdict})
    return verdict


def verify_c4_directory(out):
    root = Path(out).resolve()
    verdict = {'status':'BLOCKED', 'outer_status':None, 'inner_status':None,
               'timeout_confirmed':False, 'source_unchanged':False, 'build_client_absent':False,
               'verify_container_stopped':False, 'candidate_not_successful':False,
               'observation_scope':C4_SCOPE, 'checked_files':{}, 'errors':[]}

    class C4Error(Exception):
        def __init__(self, status, message):
            self.status, self.message = status, message

    def reject(message, status='FAILED'):
        raise C4Error(status, message)

    def content(name):
        path = root/name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            reject('Missing or unsafe file: ' + name, 'BLOCKED')
        data = path.read_bytes()
        verdict['checked_files'][name] = {'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()}
        return data.decode('utf-8')

    def load(name):
        return json.loads(content(name))

    def successful(value):
        if isinstance(value, dict):
            for key, item in value.items():
                lower = key.lower()
                if lower == 'status' and isinstance(item, str) and item.upper() in ('SUCCEEDED','SUCCESS','PASS'):
                    return True
                if lower in ('candidate_success','build_success','output_matches') and item is True:
                    return True
                if lower in ('image_id','candidate_image_id') and item:
                    return True
                if lower == 'build_exit_code' and item == 0 and value.get('iteration') == 2:
                    return True
                if successful(item):
                    return True
        elif isinstance(value, list):
            return any(successful(item) for item in value)
        return False

    try:
        request = load('request.json')
        if not isinstance(request.get('build_timeout'), (int, float)) or isinstance(request.get('build_timeout'), bool) or request['build_timeout'] <= 0:
            reject('Invalid build timeout')
        if not content('console.log').strip() or int(content('exit-code.txt').strip()) == 0:
            reject('Missing failed execution evidence')
        outer, inner = load('result.json'), load('draft-build/result.json')
        before, after = load('source-before.json'), load('source-after.json')
        for state in (before, after):
            if (not isinstance(state, dict) or not re.fullmatch(r'[0-9a-f]{40}', state.get('head', '')) or
                    not isinstance(state.get('status'), str) or state['status'] or
                    not isinstance(state.get('files'), dict) or not state['files'] or
                    any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch(r'[0-9a-f]{64}', v)
                        for k, v in state['files'].items())):
                reject('Invalid source state')
        if before != after:
            reject('Source state changed')
        verdict['source_unchanged'] = True
        verdict['outer_status'], verdict['inner_status'] = outer.get('status'), inner.get('status')
        if outer.get('status') != 'FAILED' or outer.get('error', {}).get('code') != 'DRAFT_FAILED' or inner.get('status') != 'TIMED_OUT':
            reject('Timeout status mismatch')
        verdict['timeout_confirmed'] = True
        if successful(outer) or successful(inner) or any(x.get('name') == 'draft' for x in outer.get('stages', [])):
            reject('Successful candidate or stage found')
        verdict['candidate_not_successful'] = True
        attempts = inner.get('attempts')
        if not isinstance(attempts, list) or not attempts:
            reject('Missing build attempts')
        nonempty_build_log = False
        for attempt in attempts:
            number = attempt.get('iteration')
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                reject('Invalid build iteration')
            stdout = content(f'draft-build/iter-{number:02d}/build-stdout.log')
            stderr = content(f'draft-build/iter-{number:02d}/build-stderr.log')
            nonempty_build_log |= bool(stdout or stderr)
            cmd = attempt.get('command', [])
            if not isinstance(cmd, list) or '-f' not in cmd or not cmd[cmd.index('-f')+1].endswith(f'/iter-{number:02d}/Dockerfile'):
                reject('Build log does not match attempt')
        if not nonempty_build_log:
            reject('Empty build logs')
        expected = c4_markers(root, attempts)
        ps = load('processes-and-containers/process-scan.json')
        docker_ps = load('processes-and-containers/docker-ps.json')
        for record, command in ((ps,C4_PS), (docker_ps,C4_DOCKER_PS)):
            if (record.get('command') != command or record.get('exit_code') != 0 or
                    not isinstance(record.get('checked_at'), (int,float)) or not isinstance(record.get('stdout'), str) or
                    not isinstance(record.get('stderr'), str)):
                reject('Invalid observation', 'BLOCKED')
        if not ps['stdout'].strip() or not isinstance(ps.get('observer_pid'), int) or not isinstance(ps.get('observer_ppid'), int):
            reject('Invalid process snapshot', 'BLOCKED')
        markers = ps.get('task_markers')
        if not isinstance(markers, list) or not markers or not all(isinstance(x,str) and x for x in markers) or set(markers) != set(expected):
            reject('Invalid task markers', 'BLOCKED')
        parsed = 0
        for line in ps['stdout'].splitlines():
            match = re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+(.+)$', line)
            if not match:
                reject('Unparseable process snapshot', 'BLOCKED')
            parsed += 1
            pid, _, _, argv = match.groups()
            if int(pid) in (ps['observer_pid'], ps['observer_ppid']):
                continue
            if re.search(r'(?:^|[\s/])(ps|grep|rg)(?:\s|$)', argv):
                continue
            if re.search(r'(?:^|[\s/])docker\s+(?:buildx\s+)?build(?:\s|$)', argv) and any(marker in argv for marker in markers):
                reject('Related build client still running')
        if not parsed:
            reject('Empty process snapshot', 'BLOCKED')
        verdict['build_client_absent'] = True
        cid_path = root/'draft-build/verify-container-id.txt'
        if not cid_path.exists():
            if content('processes-and-containers/no-verify-container.txt').strip() != 'NO_VERIFY_CONTAINER_STARTED':
                reject('Missing no-container evidence')
        else:
            cid = content('draft-build/verify-container-id.txt').strip()
            if not re.fullmatch(r'[0-9a-f]{64}', cid):
                reject('Invalid container ID')
            if any(line.split() and line.split()[0] == cid for line in docker_ps['stdout'].splitlines()):
                reject('Verify container appears in running container snapshot')
            record = load('processes-and-containers/verify-container-inspect.json')
            if record.get('cid') != cid or record.get('command') != ['docker','inspect','--type','container',cid]:
                reject('Container identity mismatch')
            code = record.get('exit_code')
            if code == 0:
                info = json.loads(record['stdout'])
                if not isinstance(info,list) or len(info) != 1 or info[0].get('Id') != cid or not isinstance(info[0].get('State',{}).get('Running'),bool):
                    reject('Invalid container inspect')
                if info[0]['State']['Running']:
                    reject('Verify container still running')
            elif not isinstance(code,int) or code == 0 or not re.search(r'no such (?:container|object)',record.get('stderr',''),re.I):
                reject('Container absence unproven', 'BLOCKED')
        verdict['verify_container_stopped'] = True
        verdict['status'] = 'PASS'
    except C4Error as exc:
        verdict['status'] = exc.status
        verdict['errors'].append(exc.message)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        verdict['errors'].append(str(exc))
    return verdict


def artifacts(result, directory):
    job = result.get('job_id')
    if not job or not isinstance(result.get('artifacts'), list) or not result['artifacts']:
        raise ValueError('MISSING_ARTIFACTS_OR_JOB')
    root = Path(directory).resolve()
    prefix = 'artifact://' + job + '/'
    seen_uri, seen_paths = set(), set()
    for item in result['artifacts']:
        uri = item['uri']
        if not uri.startswith(prefix):
            raise ValueError('WRONG_JOB_URI')
        if uri in seen_uri:
            raise ValueError('DUPLICATE_ARTIFACT_URI')
        seen_uri.add(uri)
        relative = uri[len(prefix):]
        parts = PurePosixPath(relative)
        if not relative or parts.is_absolute() or '..' in parts.parts or '//' in relative:
            raise ValueError('UNSAFE_ARTIFACT_PATH')
        path = (root / relative).resolve()
        if path in seen_paths:
            raise ValueError('DUPLICATE_ARTIFACT_PATH')
        seen_paths.add(path)
        if not path.is_relative_to(root) or not path.is_file() or digest(path) != item['sha256']:
            raise ValueError('ARTIFACT_HASH_OR_PATH')
        for key in ('bytes', 'size'):
            if key in item and path.stat().st_size != item[key]:
                raise ValueError('ARTIFACT_SIZE')


def c7_validate_paths(work, project, failed, succeeded):
    work, project = Path(work).resolve(), Path(project).resolve()
    outputs = []
    for raw in (Path(failed).absolute(), Path(succeeded).absolute()):
        path = raw.resolve()
        if (raw.is_symlink() or raw.exists() or path == work or not path.is_relative_to(work)
                or path == project or path.is_relative_to(project)):
            raise ValueError('UNSAFE_C7_OUTPUT')
        # Refuse symlink ancestors beneath work even when they resolve inside work.
        for parent in (raw, *raw.parents):
            if parent.is_symlink():
                raise ValueError('SYMLINK_C7_OUTPUT')
            if parent.resolve() == work:
                break
        outputs.append(path)
    a, b = outputs
    if a == b or a in b.parents or b in a.parents:
        raise ValueError('OVERLAPPING_OUTPUTS')
    return a, b


def c7_source_valid(state):
    return (isinstance(state, dict) and isinstance(state.get('head'), str)
            and re.fullmatch(r'[0-9a-f]{40}', state['head']) is not None
            and state.get('status') == '' and isinstance(state.get('sha256'), dict)
            and bool(state['sha256']) and all(isinstance(k, str) and bool(k) and isinstance(v, str)
                and re.fullmatch(r'[0-9a-f]{64}', v) for k, v in state['sha256'].items()))


def c7_artifacts(result, directory):
    job = result.get('job_id')
    if not isinstance(job, str) or not job or not isinstance(result.get('artifacts'), list) or not result['artifacts']:
        raise ValueError('MISSING_ARTIFACTS_OR_JOB')
    root = Path(directory).resolve()
    prefix = 'artifact://' + job + '/'
    uris, targets, paths = set(), set(), []
    for item in result['artifacts']:
        uri = item.get('uri')
        if not isinstance(uri, str) or not uri.startswith(prefix):
            raise ValueError('WRONG_JOB_URI')
        if uri in uris:
            raise ValueError('DUPLICATE_ARTIFACT_URI')
        uris.add(uri)
        rel = uri[len(prefix):]
        parts = PurePosixPath(rel)
        if not rel or parts.is_absolute() or '..' in parts.parts or '//' in rel or '\\' in rel:
            raise ValueError('UNSAFE_ARTIFACT_PATH')
        path = root.joinpath(*parts.parts)
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root and parent.is_relative_to(root)):
            raise ValueError('SYMLINK_ARTIFACT')
        target = path.resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError('ARTIFACT_MISSING_OR_ESCAPE')
        if target in targets:
            raise ValueError('DUPLICATE_ARTIFACT_PATH')
        targets.add(target)
        if digest(target) != item.get('sha256'):
            raise ValueError('ARTIFACT_HASH')
        for key in ('bytes', 'size'):
            if key in item and item[key] != target.stat().st_size:
                raise ValueError('ARTIFACT_SIZE')
        paths.append(target)
    return paths


def verify_c7(bad, good, bad_dir, good_dir, before, after, bad_after, residual_clear):
    a, b = Path(bad_dir).resolve(), Path(good_dir).resolve()
    if a == b or a in b.parents or b in a.parents:
        raise ValueError('OVERLAPPING_OUTPUTS')
    for key in ('job_id', 'trace_id'):
        if (not isinstance(bad.get(key), str) or not bad[key] or
                not isinstance(good.get(key), str) or not good[key] or bad[key] == good[key]):
            raise ValueError('INVALID_' + key.upper())
    if bad.get('status') != 'FAILED' or good.get('status') != 'SUCCEEDED' or bad != bad_after:
        raise ValueError('STATE_ISOLATION_FAILED')
    if not c7_source_valid(before) or not c7_source_valid(after) or before != after or residual_clear is not True:
        raise ValueError('SOURCE_OR_RESIDUAL_FAILED')
    for result, other, root in ((bad, good, a), (good, bad, b)):
        forbidden = (other['job_id'], other['trace_id'])
        if any(x in json.dumps(result) for x in forbidden):
            raise ValueError('CROSS_JOB_REFERENCE')
        for path in c7_artifacts(result, root):
            try:
                content = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            if any(x in content for x in forbidden):
                raise ValueError('CROSS_JOB_ARTIFACT')
    return 'PASS'


def c7_preflight(folder, source_before, source_after, stage, residual_clear):
    folder = Path(folder)
    request = read_json(folder/'request.json')
    result = read_json(folder/'run/result.json')
    if request.get('base') != '0'*40 or result.get('status') != 'FAILED':
        raise ValueError('INVALID_FAILED_TASK')
    for key in ('job_id', 'trace_id'):
        if not isinstance(result.get(key), str) or not result[key]:
            raise ValueError('INVALID_FAILED_IDENTITY')
    if (stage.get('failure_stage') != 'revision_validation' or stage.get('docker_started') is not False or
            stage.get('build_resource_check') != 'NOT_APPLICABLE' or residual_clear is not True):
        raise ValueError('FAILED_STAGE_OR_RESIDUAL')
    if int((folder/'exit-code.txt').read_text().strip()) == 0 or not (folder/'console.log').is_file():
        raise ValueError('FAILED_EXECUTION_EVIDENCE')
    if not c7_source_valid(source_before) or source_before != source_after:
        raise ValueError('SOURCE_CHANGED')
    def success_field(value):
        if isinstance(value, dict):
            return any((k == 'status' and isinstance(v, str) and v.upper() in ('SUCCEEDED','SUCCESS','PASS'))
                       or (k in ('candidate_success','build_success','output_matches') and v is True)
                       or success_field(v) for k, v in value.items())
        return isinstance(value, list) and any(success_field(x) for x in value)
    if success_field(result):
        raise ValueError('FAILED_TASK_HAS_SUCCESS')
    c7_artifacts(result, folder/'run')
    return result


def c7_failure(out, stage, exc, completed):
    files = sorted(str(x.relative_to(out)) for x in out.rglob('*') if x.is_file())
    failure = {'failure_stage':stage, 'error_type':type(exc).__name__, 'error_message':str(exc),
               'completed_steps':completed, 'saved_files':files}
    save(out/'failure.json', failure)
    save(out/'isolation-check.json', {'case':'C7', 'status':'FAILED', **failure})


def c7_pid_gone(pid, group=False):
    if not isinstance(pid,int) or isinstance(pid,bool) or pid <= 1:
        return False
    try:
        (os.killpg if group else os.kill)(pid,0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return False
    return False


def c7_observe():
    result = {}
    for key, command in (('processes',['ps','-eo','pid,ppid,pgid,args']),
                         ('containers',['docker','ps','-a','--no-trunc','--format','{{.ID}} {{.Names}} {{.Status}}'])):
        try:
            completed=subprocess.run(command,capture_output=True,text=True,timeout=15,check=False)
            result[key]={'command':command,'exit_code':completed.returncode,
                         'stdout':completed.stdout,'stderr':completed.stderr,'checked_at':time.time()}
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[key]={'command':command,'exit_code':None,'stdout':'','stderr':str(exc),'checked_at':time.time()}
    return result


def c7_raw_path(root, name):
    root = Path(root).resolve()
    rel = PurePosixPath(name)
    if not name or rel.is_absolute() or '..' in rel.parts or '\\' in name or name != rel.as_posix():
        raise ValueError('C7_UNSAFE_PATH')
    path = root.joinpath(*rel.parts)
    if any(p.is_symlink() for p in (path, *path.parents) if p != root and p.is_relative_to(root)):
        raise ValueError('C7_SYMLINK_PATH')
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('C7_MISSING_FILE: '+name)
    return path


def c7_raw_index(root):
    names = ['failed/request.json','failed/result.json','failed/exit-code.txt','failed/console.log',
             'failed/source-before.json','failed/source-after.json','failed/observation-before.json','failed/observation-after.json',
             'failed/run-meta.json','failed/run/request.json','failed/run/result.json','failed/run/logs/base-project-resolve.log',
             'succeeded/request.json','succeeded/result.json','succeeded/exit-code.txt','succeeded/console.log',
             'succeeded/source-before.json','succeeded/source-after.json','succeeded/observation-before.json',
             'succeeded/observation-after.json','succeeded/run-meta.json','succeeded/run/request.json','succeeded/run/result.json']
    result = {}
    for name in names:
        path = c7_raw_path(root, name)
        result[name] = {'bytes':path.stat().st_size, 'sha256':digest(path)}
    return result


def c7_snapshot_residual(before, after, folder, meta):
    # Require successful raw ps and docker snapshots; compare exact container IDs,
    # ignoring unrelated container uptime text.
    for observation in (before, after):
        for name in ('processes','containers'):
            item=observation.get(name,{})
            expected = (['ps','-eo','pid,ppid,pgid,args'] if name == 'processes' else
                        ['docker','ps','-a','--no-trunc','--format','{{.ID}} {{.Names}} {{.Status}}'])
            if item.get('command') != expected or not isinstance(item.get('checked_at'),(int,float)) or item.get('exit_code') != 0 or not isinstance(item.get('stdout'),str) or not isinstance(item.get('stderr'),str):
                raise ValueError('C7_OBSERVATION_INVALID')
        if not observation['processes']['stdout'].strip():
            raise ValueError('C7_PROCESS_SNAPSHOT_EMPTY')
    def ids(observation):
        result=set()
        for line in observation['containers']['stdout'].splitlines():
            tokens=line.split()
            if not tokens or not re.fullmatch(r'[0-9a-f]{64}',tokens[0]):
                raise ValueError('C7_CONTAINER_SNAPSHOT_INVALID')
            result.add(tokens[0])
        return result
    if ids(after) - ids(before):
        raise ValueError('C7_CONTAINER_RESIDUAL_UNPROVEN')
    if meta.get('timed_out') is not False or not isinstance(meta.get('owned'),dict):
        raise ValueError('C7_TASK_TIMEOUT_OR_METADATA')
    owned=meta['owned']
    if (not isinstance(owned.get('pids'),list) or not owned['pids'] or
            not isinstance(owned.get('pgids'),list) or not owned['pgids'] or
            any(not isinstance(value,int) or isinstance(value,bool) or value <= 1
                for value in owned['pids']+owned['pgids'])):
        raise ValueError('C7_TASK_PROCESS_IDENTITY_MISSING')
    root=Path(__file__).resolve().parents[2]
    markers={str(folder)}
    try:
        markers.add('/course/'+Path(folder).resolve().relative_to(root).as_posix())
    except ValueError:
        pass
    parsed=0
    for line in after['processes']['stdout'].splitlines():
        match=re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+)\s+(.+)$',line)
        if not match:
            if re.match(r'^\s*PID\s+',line):
                continue
            raise ValueError('C7_PROCESS_SNAPSHOT_INVALID')
        parsed+=1
        pid, _, pgid, argv=match.groups()
        if int(pid) in meta['owned'].get('pids',[]) or int(pgid) in meta['owned'].get('pgids',[]):
            raise ValueError('C7_PROCESS_RESIDUAL')
        if re.search(r'(?:^|[\s/])docker\s+(?:buildx\s+)?build(?:\s|$)',argv) and any(m in argv for m in markers):
            raise ValueError('C7_PROCESS_RESIDUAL')
    if not parsed:
        raise ValueError('C7_PROCESS_SNAPSHOT_INVALID')
    return True


def verify_c7_evidence(case):
    case=Path(case)
    if case.is_symlink() or not case.is_dir():
        raise ValueError('C7_CASE_PATH_INVALID')
    root=case.resolve()
    def load(name): return read_json(c7_raw_path(root,name))
    summary=load('isolation-check.json')
    if summary.get('case') != 'C7' or summary.get('status') != 'PASS':
        raise ValueError('C7_SUMMARY_INVALID')
    index=c7_raw_index(root)
    if summary.get('raw_index') != index:
        raise ValueError('C7_RAW_INDEX_MISMATCH')
    data={}
    for name in ('failed','succeeded'):
        d={'request':load(name+'/request.json'), 'result':load(name+'/result.json'),
           'pipeline_request':load(name+'/run/request.json'), 'pipeline_result':load(name+'/run/result.json'),
           'before':load(name+'/source-before.json'), 'after':load(name+'/source-after.json'),
           'observation_before':load(name+'/observation-before.json'), 'observation_after':load(name+'/observation-after.json'),
           'meta':load(name+'/run-meta.json')}
        try:
            d['exit_code']=int(c7_raw_path(root,name+'/exit-code.txt').read_text().strip())
            d['console']=c7_raw_path(root,name+'/console.log').read_text(encoding='utf-8')
        except (ValueError, UnicodeError) as exc:
            raise ValueError('C7_EXECUTION_RECORD_INVALID') from exc
        if d['request'] != d['pipeline_request'] or d['result'] != d['pipeline_result']:
            raise ValueError('C7_PIPELINE_RECORD_MISMATCH')
        if not c7_source_valid(d['before']) or d['before'] != d['after']:
            raise ValueError('C7_SOURCE_CHANGED')
        c7_snapshot_residual(d['observation_before'],d['observation_after'],root/name,d['meta'])
        data[name]=d
    bad,good=data['failed'],data['succeeded']
    if bad['after'] != good['before']:
        raise ValueError('C7_SOURCE_CHANGED')
    if bad['observation_after'] != good['observation_before']:
        raise ValueError('C7_OBSERVATION_SEQUENCE_MISMATCH')
    try:
        for task in (bad,good):
            start, end = task['meta']['started_at'], task['meta']['finished_at']
            before_times = [task['observation_before'][key]['checked_at'] for key in ('processes','containers')]
            after_times = [task['observation_after'][key]['checked_at'] for key in ('processes','containers')]
            if (not all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in [start,end,*before_times,*after_times]) or
                    max(before_times) > start or start > end or end > min(after_times)):
                raise ValueError('C7_EXECUTION_SEQUENCE_INVALID')
        if bad['meta']['finished_at'] > good['meta']['started_at']:
            raise ValueError('C7_EXECUTION_SEQUENCE_INVALID')
    except (TypeError, KeyError) as exc:
        raise ValueError('C7_EXECUTION_SEQUENCE_INVALID') from exc
    if bad['request'].get('base') != '0'*40 or {**bad['request'],'base':good['request'].get('base')} != good['request']:
        raise ValueError('C7_REQUEST_MISMATCH')
    if bad['exit_code'] == 0 or good['exit_code'] != 0 or bad['meta'].get('exit_code') != bad['exit_code'] or good['meta'].get('exit_code') != good['exit_code']:
        raise ValueError('C7_EXIT_CODE_MISMATCH')
    stage=failure_stage(bad['result'],root/'failed/run',bad['meta'])
    if stage != {'failure_stage':'revision_validation','docker_started':False,'build_resource_check':'NOT_APPLICABLE'}:
        raise ValueError('C7_FAILURE_STAGE_MISMATCH')
    if not c7_raw_path(root,'failed/run/logs/base-project-resolve.log').read_text(encoding='utf-8').strip():
        raise ValueError('C7_REVISION_LOG_EMPTY')
    if good['result'].get('base_commit') != good['request'].get('base') or good['result'].get('target_commit') != good['request'].get('target'):
        raise ValueError('C7_COMMIT_MISMATCH')
    verify_c7(bad['result'],good['result'],root/'failed/run',root/'succeeded/run',bad['before'],good['after'],bad['pipeline_result'],True)
    c7_preflight(root/'failed',bad['before'],bad['after'],stage,True)
    for current,other in ((bad,good),(good,bad)):
        if any(x in current['console'] for x in (other['result']['job_id'],other['result']['trace_id'])):
            raise ValueError('C7_CONSOLE_CROSS_JOB')
    for current, other, name in ((bad,good,'failed'),(good,bad,'succeeded')):
        forbidden=(other['result']['job_id'],other['result']['trace_id'])
        folder=root/name
        for path in folder.rglob('*.json'):
            if '.git' in path.relative_to(folder).parts:
                continue
            safe=c7_raw_path(root,path.relative_to(root).as_posix())
            if any(identity in safe.read_text(encoding='utf-8') for identity in forbidden):
                raise ValueError('C7_JSON_CROSS_JOB')
    expected={'bad':bad['result'],'good':good['result'],'bad_after':bad['pipeline_result'],
              'source_before':bad['before'],'source_after':good['after'],'residual_clear':True,'stage':stage,
              'before':bad['observation_before'],'between':bad['observation_after'],
              'after':good['observation_after'],'runs':[bad['meta'],good['meta']],
              'bad_dir':'failed/run','good_dir':'succeeded/run'}
    if any(summary.get(k) != v for k,v in expected.items()):
        raise ValueError('C7_SUMMARY_MISMATCH')
    return {'case':'C7','status':'PASS','bad_job_id':bad['result']['job_id'],'good_job_id':good['result']['job_id']}


def run_c7(entry, project, failed_input, good_input, out, timeout, before, observation_before):
    completed, phase = [], 'validate_inputs'
    try:
        if not Path(entry).is_file() or not Path(project).is_dir():
            raise ValueError('ENTRY_OR_PROJECT_MISSING')
        failed_request, good_request = read_json(failed_input), read_json(good_input)
        check_request_project(good_request, project)
        if failed_request.get('base') != '0'*40 or {**failed_request, 'base':good_request.get('base')} != good_request:
            raise ValueError('FAILED_REQUEST_MUST_ONLY_CHANGE_BASE')
        if not c7_source_valid(before):
            raise ValueError('INVALID_SOURCE_STATE')
        failed_dir, good_dir = out/'failed', out/'succeeded'
        c7_validate_paths(Path(__file__).resolve().parents[2]/'work', project, failed_dir, good_dir)
        phase = 'write_requests'
        failed_dir.mkdir(); good_dir.mkdir()
        save(failed_dir/'request.json', failed_request)
        save(good_dir/'request.json', good_request)
        save(out/'source-before.json', before)
        save(failed_dir/'source-before.json',before)
        save(failed_dir/'observation-before.json',observation_before)
        completed.append('requests_saved')
        phase = 'failed_launch'
        failed = launch(entry, failed_dir/'request.json', failed_dir/'run', failed_dir/'console.log', timeout)
        (failed_dir/'exit-code.txt').write_text(str(failed['exit_code'])+'\n')
        save(failed_dir/'run-meta.json',failed)
        completed.append('failed_executed')
        phase = 'failed_preflight'
        preliminary = read_json(failed_dir/'run/result.json')
        save(failed_dir/'result.json',preliminary)
        between = c7_observe()
        failed_after = source_state(project)
        save(failed_dir/'source-after.json',failed_after)
        save(failed_dir/'observation-after.json',between)
        stage = failure_stage(preliminary, failed_dir/'run', failed)
        process_clear = all(c7_pid_gone(x) for x in failed['owned']['pids']) and all(c7_pid_gone(x, True) for x in failed['owned']['pgids'])
        containers_clear = (observation_before['containers'].get('exit_code') == 0 and
                            between['containers'].get('exit_code') == 0 and
                            observation_before['containers']['stdout'] == between['containers']['stdout'])
        residual_clear = process_clear and containers_clear
        bad = c7_preflight(failed_dir, before, failed_after, stage, residual_clear)
        completed.append('failed_verified')
        save(good_dir/'source-before.json',failed_after)
        save(good_dir/'observation-before.json',between)
        phase = 'good_launch'
        good_run = launch(entry, good_dir/'request.json', good_dir/'run', good_dir/'console.log', timeout)
        (good_dir/'exit-code.txt').write_text(str(good_run['exit_code'])+'\n')
        save(good_dir/'run-meta.json',good_run)
        completed.append('good_executed')
        phase = 'isolation_verification'
        good = read_json(good_dir/'run/result.json')
        save(good_dir/'result.json',good)
        if int((good_dir/'exit-code.txt').read_text().strip()) != 0 or not (good_dir/'console.log').is_file():
            raise ValueError('GOOD_EXECUTION_EVIDENCE')
        bad_after = read_json(failed_dir/'run/result.json')
        good_after = read_json(good_dir/'run/result.json')
        if good != good_after:
            raise ValueError('GOOD_STATE_CHANGED')
        after = source_state(project)
        save(out/'source-after.json', after)
        save(good_dir/'source-after.json',after)
        after_observation=c7_observe()
        save(good_dir/'observation-after.json',after_observation)
        verify_c7(bad, good, failed_dir/'run', good_dir/'run', before, after, bad_after, residual_clear)
        for path, identities in ((failed_dir/'console.log', (good['job_id'],good['trace_id'])),
                                 (good_dir/'console.log', (bad['job_id'],bad['trace_id'])),
                                 (failed_dir/'failure.json', (good['job_id'],good['trace_id']))):
            if path.exists() and any(x in path.read_text(encoding='utf-8') for x in identities):
                raise ValueError('LOG_CROSS_JOB')
        record = {'case':'C7', 'status':'PASS', 'bad':bad, 'good':good, 'bad_after':bad_after,
                  'bad_dir':'failed/run', 'good_dir':'succeeded/run',
                  'source_before':before, 'source_after':after, 'residual_clear':residual_clear,
                  'stage':stage, 'before':observation_before, 'between':between, 'after':after_observation,
                  'runs':[failed, good_run], 'completed_steps':completed}
        record['raw_index']=c7_raw_index(out)
        save(out/'isolation-check.json', record)
        verify_c7_evidence(out)
        return 0
    except Exception as exc:
        try:
            if phase in ('failed_launch', 'failed_preflight', 'good_launch'):
                folder = out/('failed' if phase.startswith('failed') else 'succeeded')
                if folder.is_dir():
                    if not (folder/'console.log').exists():
                        (folder/'console.log').write_text('')
                    if not (folder/'exit-code.txt').exists():
                        (folder/'exit-code.txt').write_text('NOT_AVAILABLE\n')
                    save(folder/'failure.json', {'failure_stage':phase, 'error_type':type(exc).__name__, 'error_message':str(exc)})
            c7_failure(out, phase, exc, completed)
        except OSError:
            pass
        return 1


def safe_extract(archive, work, dest):
    work = Path(work).resolve()
    dest = Path(dest).resolve()
    if dest == work or not dest.is_relative_to(work) or dest.exists():
        raise ValueError('UNSAFE_EXTRACTION_DESTINATION')
    with zipfile.ZipFile(archive) as z:
        seen = set()
        file_paths = set()
        for item in z.infolist():
            name = item.filename
            parts = PurePosixPath(name)
            if (not name or '\\' in name or parts.is_absolute() or '..' in parts.parts
                    or re.match(r'^[A-Za-z]:', name) or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('UNSAFE_ZIP_ENTRY')
            normalized = '/'.join(parts.parts).rstrip('/')
            if not normalized or normalized in seen:
                raise ValueError('DUPLICATE_ZIP_ENTRY')
            seen.add(normalized)
            if not item.is_dir():
                file_paths.add(normalized)
        if any('/'.join(name.split('/')[:i]) in file_paths for name in seen for i in range(1, len(name.split('/')))):
            raise ValueError('ZIP_FILE_DIRECTORY_CONFLICT')
        dest.mkdir(parents=True, exist_ok=False)
        z.extractall(dest)
    return digest(archive)


H3_BASE = 'dc8099306d7023b7337328d718149973e7b17978'
H3_TARGET = '5640bb69a01e64559207e9f74d15a9ae71a4d0f3'
H3_UPSTREAM = '23856752fbd139da0b8ca6e471a13d5bcc99a08d'
H3_PREFIX = 'e13-upstream-student/H3-tiny-aes/'


def h3_preflight(archive):
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) > 10000 or sum(x.file_size for x in entries) > 256*1024*1024:
            raise ValueError('ZIP_LIMIT_EXCEEDED')
        seen, files, members = set(), set(), {}
        for item in entries:
            name = item.filename
            parts = PurePosixPath(name)
            mode = item.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if (not name or '\\' in name or parts.is_absolute() or '..' in parts.parts or item.extra or
                    re.match(r'^[A-Za-z]:',name) or kind not in (0,stat.S_IFREG,stat.S_IFDIR)):
                raise ValueError('UNSAFE_ZIP_ENTRY')
            norm = '/'.join(parts.parts).rstrip('/')
            if not norm or norm != name.rstrip('/') or norm in seen:
                raise ValueError('DUPLICATE_OR_ABNORMAL_ZIP_PATH')
            seen.add(norm)
            if not item.is_dir():
                files.add(norm)
            if name.startswith(H3_PREFIX):
                data = z.read(item) if not item.is_dir() else b''
                members[norm] = {'size':item.file_size, 'crc':item.CRC,
                                 'sha256':hashlib.sha256(data).hexdigest(),
                                 'type':'directory' if item.is_dir() else 'file'}
        if any('/'.join(name.split('/')[:i]) in files for name in seen for i in range(1,len(name.split('/')))):
            raise ValueError('ZIP_FILE_DIRECTORY_CONFLICT')
        roots={name[:name.index('H3-tiny-aes/')+len('H3-tiny-aes/')] for name in seen if 'H3-tiny-aes/' in name}
        if roots != {H3_PREFIX}:
            raise ValueError('H3_ROOT_NOT_UNIQUE')
        required = ('repo/UPSTREAM.md','repo/LICENSE.upstream','candidate.Dockerfile','upstream-original/unlicense.txt')
        if any(H3_PREFIX+x not in files for x in required) or not any(x.startswith(H3_PREFIX+'repo/.git/objects/') for x in files):
            raise ValueError('H3_REQUIRED_MEMBERS_MISSING')
        return members


def h3_extract_checked(archive, dest):
    members = h3_preflight(archive)
    dest = Path(dest)
    if dest.exists() or dest.is_symlink():
        raise ValueError('OUTPUT_EXISTS')
    dest.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        z.extractall(dest)
    for name, item in members.items():
        path = dest/name
        if item['type'] == 'file' and (not path.is_file() or path.is_symlink() or path.stat().st_size != item['size'] or digest(path) != item['sha256']):
            raise ValueError('EXTRACTED_MEMBER_MISMATCH')
    return members


def h3_source_identity(folder):
    repo, candidate = folder/'repo', folder/'candidate.Dockerfile'
    upstream, license_path = repo/'UPSTREAM.md', repo/'LICENSE.upstream'
    text_upstream = upstream.read_text(encoding='utf-8')
    license_text = license_path.read_text(encoding='utf-8')
    if ('https://github.com/kokke/tiny-AES-c' not in text_upstream or
            not re.search(r'Pinned upstream commit:\s*'+H3_UPSTREAM+r'\b', text_upstream) or
            'unencumbered software released into the public domain' not in license_text.lower()):
        raise ValueError('H3_SOURCE_IDENTITY_MISMATCH')
    if git(repo,'rev-parse','--is-shallow-repository') != 'false':
        raise ValueError('SHALLOW_REPOSITORY')
    git(repo,'fsck','--full','--no-reflogs')
    head=git(repo,'rev-parse','HEAD')
    base=git(repo,'rev-parse','--verify',H3_BASE+'^{commit}')
    target=git(repo,'rev-parse','--verify',H3_TARGET+'^{commit}')
    if head != target:
        raise ValueError('H3_HEAD_MISMATCH')
    if base == target:
        raise ValueError('H3_IDENTICAL_COMMITS')
    if subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',base,target],check=False).returncode:
        raise ValueError('H3_NON_ANCESTOR')
    state=source_state(repo)
    if state['status']:
        raise ValueError('H3_SOURCE_DIRTY')
    return {'head':head,'base':base,'target':target,'tree':git(repo,'rev-parse',target+'^{tree}'),
            'history':git(repo,'log','--format=%H %P %T %s'), 'files':state['sha256'],
            'upstream_sha256':digest(upstream),'license_sha256':digest(license_path),
            'license_bytes':license_path.stat().st_size,'candidate_sha256':digest(candidate),
            'candidate_bytes':candidate.stat().st_size}


def h3_create_plan(archive, out):
    import tempfile
    archive, out = Path(archive).resolve(), Path(out).resolve()
    archive_sha = digest(archive)
    with tempfile.TemporaryDirectory() as tmp:
        extracted = Path(tmp)/'input'
        members=h3_extract_checked(archive,extracted)
        identity=h3_source_identity(extracted/H3_PREFIX)
    root=Path(__file__).resolve().parents[2]
    rel=out.relative_to(root).as_posix()
    request={'mode':'e12','repo':'/course/'+rel+'/input/'+H3_PREFIX+'repo',
             'candidate':'/course/'+rel+'/input/'+H3_PREFIX+'candidate.Dockerfile',
             'base':identity['base'],'target':identity['target'],'expected_output':'1','expected_stdout':'1\n',
             'expected_stderr':'','expected_exit_code':0,'build_timeout':600}
    save(out/'request.json',request)
    plan={'case':'H3','schema_version':'e13-h3-plan-1','status':'NOT_RUN','teacher_project':True,
          'project_name':'H3-tiny-aes','zip_path':str(archive),'zip_sha256':archive_sha,
          'members':members,'identity':identity,'request_sha256':digest(out/'request.json'),
          'request_bytes':(out/'request.json').stat().st_size}
    save(out/'plan.json',plan)
    return plan


def h3_verify_new_plan(plan, plan_dir):
    import tempfile
    if (plan.get('schema_version') != 'e13-h3-plan-1' or plan.get('status') != 'NOT_RUN' or
            plan.get('teacher_project') is not True or plan.get('project_name') != 'H3-tiny-aes'):
        raise ValueError('INVALID_PLAN')
    def forbidden(value):
        if isinstance(value, dict):
            return any(k in ('job_id','trace_id','result','passed','success','image_id') or
                       (k == 'status' and v in ('SUCCEEDED','PASS')) or forbidden(v) for k,v in value.items())
        return isinstance(value,list) and any(forbidden(x) for x in value)
    if forbidden(plan):
        raise ValueError('PREPOPULATED_RESULT')
    request_file=Path(plan_dir)/'request.json'
    if digest(request_file) != plan['request_sha256'] or request_file.stat().st_size != plan['request_bytes']:
        raise ValueError('REQUEST_MISMATCH')
    request=read_json(request_file)
    archive=Path(plan['zip_path'])
    if digest(archive) != plan['zip_sha256']:
        raise ValueError('ZIP_HASH_MISMATCH')
    with tempfile.TemporaryDirectory() as tmp:
        dest=Path(tmp)/'input'
        members=h3_extract_checked(archive,dest)
        identity=h3_source_identity(dest/H3_PREFIX)
    if members != plan['members'] or identity != plan['identity']:
        raise ValueError('H3_IDENTITY_MISMATCH')
    root=Path(__file__).resolve().parents[2]
    rel=Path(plan_dir).resolve().relative_to(root).as_posix()
    expected={'mode':'e12','repo':'/course/'+rel+'/input/'+H3_PREFIX+'repo',
              'candidate':'/course/'+rel+'/input/'+H3_PREFIX+'candidate.Dockerfile',
              'base':identity['base'],'target':identity['target'],'expected_output':'1','expected_stdout':'1\n',
             'expected_stderr':'','expected_exit_code':0,'build_timeout':600}
    if request != expected:
        raise ValueError('REQUEST_IDENTITY_MISMATCH')
    return {'status':'PASS','kind':'NOT_RUN'}


def h3_manifest_file(root, result):
    root=Path(root).resolve()
    job, trace=result['job_id'],result['trace_id']
    paths = {item['uri'][len('artifact://'+job+'/'):]:item for item in result['artifacts']
             if item['uri'].startswith('artifact://'+job+'/')}
    artifacts(result,root/'run')
    names=['plan.json','request.json','run/result.json','source-before.json','source-after.json','console.log','exit-code.txt']
    names += ['run/'+name for name in paths]
    entries=[]
    for name in sorted(set(names)):
        path=root/name
        item={'path':name,'bytes':path.stat().st_size,'sha256':digest(path),
              'kind':'pipeline' if name.startswith('run/') else 'execution', 'job_id':job,'trace_id':trace}
        if name.startswith('run/') and name[4:] in paths:
            item['uri']=paths[name[4:]]['uri']
        entries.append(item)
    return {'schema_version':'e13-h3-manifest-1','teacher_project':True,'project_name':'H3-tiny-aes',
            'job_id':job,'trace_id':trace,'files':entries}


def h3_verify_new_run(plan, root):
    root=Path(root).resolve()
    h3_verify_new_plan(plan,root)
    manifest=read_json(root/'evidence-manifest.json')
    if (manifest.get('schema_version') != 'e13-h3-manifest-1' or manifest.get('teacher_project') is not True or
            manifest.get('project_name') != 'H3-tiny-aes' or manifest.get('ab_real_project') is True or
            not manifest.get('job_id') or not manifest.get('trace_id')):
        raise ValueError('INVALID_MANIFEST')
    job,trace=manifest['job_id'],manifest['trace_id']
    entries,uris={},set()
    for item in manifest.get('files',[]):
        name=item['path']; rel=PurePosixPath(name)
        if not name or rel.is_absolute() or '..' in rel.parts or '\\' in name or name != rel.as_posix() or name in entries:
            raise ValueError('UNSAFE_MANIFEST_PATH')
        path=root.joinpath(*rel.parts)
        if (any(p.is_symlink() for p in (path,*path.parents) if p != root and p.is_relative_to(root)) or
                not path.resolve().is_relative_to(root) or not path.is_file() or
                item.get('bytes') != path.stat().st_size or item.get('sha256') != digest(path) or
                item.get('job_id') != job or item.get('trace_id') != trace):
            raise ValueError('MANIFEST_CONTENT_MISMATCH')
        uri=item.get('uri')
        if uri:
            if uri in uris or uri != 'artifact://'+job+'/'+name.removeprefix('run/') or not name.startswith('run/'):
                raise ValueError('MANIFEST_URI_MISMATCH')
            uris.add(uri)
        entries[name]=item
    required=('plan.json','request.json','run/result.json','source-before.json','source-after.json','console.log','exit-code.txt',
              'run/draft.json','run/full-check.json','run/incremental-check.json','run/repair.json','run/recheck.json',
              'run/draft-build/result.json','run/draft-build/verify.log','run/draft-build/verify-stderr.log',
              'run/candidate.patch','run/repair-plan.json','run/validation/validation.json')
    if any(name not in entries for name in required):
        raise ValueError('MANIFEST_REQUIRED_FILE_MISSING')
    def read(name):
        if name not in entries:
            raise ValueError('UNDECLARED_FILE')
        return read_json(root/name)
    result=read('run/result.json'); request=read('request.json')
    if result.get('job_id') != job or result.get('trace_id') != trace or result.get('status') != 'SUCCEEDED' or int((root/'exit-code.txt').read_text()) != 0:
        raise ValueError('INVALID_EXECUTION')
    if read('plan.json') != plan:
        raise ValueError('PLAN_MISMATCH')
    for artifact in result.get('artifacts', []):
        uri=artifact.get('uri','')
        prefix='artifact://'+job+'/'
        if not uri.startswith(prefix):
            raise ValueError('RESULT_ARTIFACT_URI_MISMATCH')
        path='run/'+uri[len(prefix):]
        if path not in entries or entries[path].get('uri') != uri or entries[path]['sha256'] != artifact.get('sha256') or entries[path]['bytes'] != artifact.get('bytes'):
            raise ValueError('RESULT_ARTIFACT_MISMATCH')
    if (result.get('base_commit') != plan['identity']['base'] or result.get('target_commit') != plan['identity']['target']):
        raise ValueError('COMMIT_MISMATCH')
    if read('run/request.json') != request:
        raise ValueError('REQUEST_MISMATCH')
    phases=['draft','full-check','incremental-check','repair','recheck']
    if [x.get('name') for x in result.get('stages',[])] != phases:
        raise ValueError('PHASE_ORDER')
    for stage in result['stages']:
        name=stage['name']; path='run/'+name+'.json'; item=stage['artifact']
        if item.get('uri') != entries[path].get('uri') or item.get('sha256') != entries[path]['sha256'] or item.get('bytes') != entries[path]['bytes']:
            raise ValueError('STAGE_ARTIFACT_MISMATCH')
        envelope=read(path)
        expected=plan['identity']['base'] if name=='full-check' else plan['identity']['target']
        if (envelope.get('job_id') != job or envelope.get('trace_id') != trace or envelope.get('status') != 'SUCCEEDED' or
                envelope.get('kind') != name or envelope.get('commit') != expected):
            raise ValueError('STAGE_IDENTITY_MISMATCH')
        for item in envelope.get('artifacts',[]):
            uri=item['uri']; path='run/'+uri.removeprefix('artifact://'+job+'/')
            if path not in entries or entries[path].get('uri') != uri or entries[path]['sha256'] != item['sha256'] or entries[path]['bytes'] != item['bytes']:
                raise ValueError('STAGE_REFERENCE_MISMATCH')
    draft=read('run/draft-build/result.json'); verify=draft['verification']
    actual=(root/'run/draft-build/verify.log').read_text()
    stderr=(root/'run/draft-build/verify-stderr.log').read_text()
    if (draft.get('status') != 'SUCCEEDED' or verify.get('exit_code') != 0 or stderr != '' or
            actual != verify.get('actual_output') or actual != request['expected_stdout'] or stderr != request['expected_stderr'] or
            verify.get('exit_code') != request['expected_exit_code'] or
            verify.get('expected_output') != request['expected_output'] or verify.get('output_matches') is not True):
        raise ValueError('PROGRAM_OUTPUT_MISMATCH')
    validation=read('run/validation/validation.json'); recheck=read('run/recheck.json')['data']
    if validation.get('accepted') is not True or recheck.get('validation') != validation:
        raise ValueError('VALIDATION_FAILED')
    findings=recheck['findings']
    if any(f.get('type') == 'MISSING' for f in findings):
        raise ValueError('MISSING_REMAINS')
    before,after=read('source-before.json'),read('source-after.json')
    if before != after or not c7_source_valid(before) or before['head'] != plan['identity']['head'] or before['sha256'] != plan['identity']['files']:
        raise ValueError('SOURCE_CHANGED')
    return {'status':'PASS','kind':'teacher_project','missing_count':0,'findings':findings}


def h3_plan(repo, candidate, output, base=None, target=None):
    repo, candidate = Path(repo).resolve(), Path(candidate).resolve()
    upstream, license_file = repo / 'UPSTREAM.md', repo / 'LICENSE.upstream'
    if not upstream.is_file() or not license_file.is_file() or not candidate.is_file():
        raise ValueError('MISSING_PROVENANCE')
    if ('https://github.com/kokke/tiny-AES-c' not in upstream.read_text(encoding='utf-8') or
            not re.search(r'Pinned upstream commit:\s*23856752fbd139da0b8ca6e471a13d5bcc99a08d\b', upstream.read_text(encoding='utf-8')) or
            'unencumbered software released into the public domain' not in license_file.read_text(encoding='utf-8').lower()):
        raise ValueError('INVALID_PROVENANCE')
    if git(repo, 'rev-parse', '--is-shallow-repository') != 'false':
        raise ValueError('SHALLOW_REPOSITORY')
    git(repo, 'fsck', '--full', '--strict')
    history = git(repo, 'rev-list', 'HEAD').splitlines()
    if len(history) < 2:
        raise ValueError('INSUFFICIENT_HISTORY')
    target = git(repo, 'rev-parse', '--verify', (target or 'HEAD') + '^{commit}')
    base = git(repo, 'rev-parse', '--verify', (base or target + '^') + '^{commit}')
    if base == target:
        raise ValueError('IDENTICAL_COMMITS')
    if target != git(repo, 'rev-parse', 'HEAD'):
        raise ValueError('TARGET_NOT_HEAD')
    if subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', base, target], check=False).returncode:
        raise ValueError('NOT_ANCESTOR')
    plan = {'case': 'H3', 'status': 'NOT_RUN', 'upstream': upstream.read_text(encoding='utf-8'),
            'license_sha256': digest(license_file), 'candidate_sha256': digest(candidate),
            'head': target, 'history': history, 'request': {'mode': 'e12', 'repo': str(repo),
            'base': base, 'target': target, 'candidate': str(candidate), 'expected_output': '1', 'build_timeout': 600}}
    save(output, plan)
    return plan


def launch(entry, request, out, log, timeout):
    return run_process([sys.executable, str(entry), 'run', '--request', str(request), '--out', str(out)], timeout, log)


def failure_stage(result, run_dir, run):
    # The pipeline snapshots base before any draft import or Docker command.
    before_draft = (result.get('status') == 'FAILED' and result.get('error', {}).get('code') == 'COMMAND_FAILED'
                    and not (Path(run_dir) / 'draft-build').exists()
                    and not (Path(run_dir) / 'base-project').exists()
                    and (Path(run_dir) / 'logs/base-project-resolve.log').is_file()
                    and not run.get('timed_out'))
    return {'docker_started': False if before_draft else None,
            'failure_stage': 'revision_validation' if before_draft else 'unknown',
            'build_resource_check': 'NOT_APPLICABLE' if before_draft else 'BLOCKED'}


def h3_zip_members(archive):
    prefix = 'e13-upstream-student/H3-tiny-aes/'
    with zipfile.ZipFile(archive) as z:
        return {item.filename: {'size':item.file_size, 'sha256':hashlib.sha256(z.read(item)).hexdigest()}
                for item in z.infolist() if item.filename.startswith(prefix) and not item.is_dir()}


def verify_h3_plan(plan):
    if plan.get('status') != 'NOT_RUN' or plan.get('project_kind') != 'teacher_project':
        raise ValueError('INVALID_PLAN_STATUS')
    if any(k in plan for k in ('job_id', 'trace_id', 'result', 'passed', 'success')):
        raise ValueError('PREPOPULATED_RESULT')
    archive = Path(plan['zip_path'])
    if digest(archive) != plan['zip_sha256'] or plan.get('zip_safety') != 'PASSED' or plan.get('zip_members') != h3_zip_members(archive):
        raise ValueError('ZIP_INVALID')
    repo = Path(plan['request']['repo'])
    candidate = Path(plan['request']['candidate'])
    with __import__('tempfile').TemporaryDirectory() as tmp:
        extracted = Path(tmp) / 'verified'
        safe_extract(archive, tmp, extracted)
        source = extracted/'e13-upstream-student/H3-tiny-aes'
        upstream_repo = source/'repo'
        if not upstream_repo.is_dir() or not (source/'upstream-original').is_dir() or not (source/'candidate.Dockerfile').is_file():
            raise ValueError('ZIP_H3_MISSING')
        files = [p for p in upstream_repo.rglob('*') if p.is_file() and ('.git' not in p.parts or 'objects' in p.parts or 'refs' in p.parts)]
        if not files or any(not (repo/p.relative_to(upstream_repo)).is_file() or digest(p) != digest(repo/p.relative_to(upstream_repo)) for p in files):
            raise ValueError('ZIP_REPO_MISMATCH')
        if digest(source/'candidate.Dockerfile') != digest(candidate):
            raise ValueError('ZIP_CANDIDATE_MISMATCH')
    with __import__('tempfile').TemporaryDirectory() as tmp:
        checked = h3_plan(repo, candidate, Path(tmp) / 'plan.json', plan['request']['base'], plan['request']['target'])
    for key in ('head', 'history', 'license_sha256', 'candidate_sha256', 'upstream', 'request'):
        if checked[key] != plan[key]:
            raise ValueError('PLAN_IDENTITY_MISMATCH')
    return {'status': 'PASS', 'kind': 'NOT_RUN'}


def verify_h3_run(plan, directory):
    verify_h3_plan(plan)
    root = Path(directory).resolve()
    # External execution and source state must be independently hash-bound.
    manifest = read_json(root/'evidence-manifest.json')
    for name in ('execution.json', 'source-before.json', 'source-after.json', 'request.json', 'run/result.json'):
        if name not in manifest or digest(root/name) != manifest[name]:
            raise ValueError('EVIDENCE_MANIFEST_MISMATCH')
    result = read_json(root / 'run/result.json')
    request = read_json(root / 'run/request.json')
    if result.get('status') != 'SUCCEEDED' or not result.get('job_id') or not result.get('trace_id'):
        raise ValueError('INVALID_JOB')
    if result.get('target_commit') != plan['request']['target'] or request.get('target') != plan['request']['target']:
        raise ValueError('WRONG_TARGET')
    if result.get('base_commit') != plan['request']['base'] or request.get('base') != plan['request']['base']:
        raise ValueError('WRONG_BASE')
    names = ['draft', 'full-check', 'incremental-check', 'repair', 'recheck']
    if [x['name'] for x in result.get('stages', [])] != names:
        raise ValueError('MISSING_STAGE')
    artifacts(result, root / 'run')
    for stage in result['stages']:
        if stage.get('artifact', {}).get('uri') != 'artifact://' + result['job_id'] + '/' + stage['name'] + '.json':
            raise ValueError('STAGE_ARTIFACT_PATH_MISMATCH')
        artifacts({'job_id': result['job_id'], 'artifacts': [stage['artifact']]}, root / 'run')
        envelope = read_json(root / 'run' / (stage['name'] + '.json'))
        expected_commit = plan['request']['base'] if stage['name'] == 'full-check' else plan['request']['target']
        if (envelope.get('commit') != expected_commit or envelope.get('status') != 'SUCCEEDED' or envelope.get('kind') != stage['name'] or
                envelope.get('job_id') != result['job_id'] or envelope.get('trace_id') != result['trace_id']):
            raise ValueError('STAGE_IDENTITY_MISMATCH')
        artifacts(envelope, root / 'run')
    manifest_paths = {item['uri'].split('/' + result['job_id'] + '/', 1)[-1] for item in result['artifacts']}
    for name in ('candidate.patch', 'validation/validation.json', 'draft-build/verify.log',
                 'draft-build/verify-stderr.log', 'draft-build/result.json', 'recheck.json', 'request.json'):
        if not (root / 'run' / name).is_file() or name not in manifest_paths:
            raise ValueError('MISSING_EVIDENCE_OR_HASH')
    draft = read_json(root / 'run/draft-build/result.json')
    verification = draft['verification']
    if (verification['exit_code'] != 0 or verification['actual_output'].rstrip('\r\n') != plan['request']['expected_output'] or verification['actual_output'] != (root/'run/draft-build/verify.log').read_text()
            or verification.get('output_matches') is not True or not (root/'execution.json').is_file()
            or read_json(root/'execution.json').get('exit_code') != 0):
        raise ValueError('PROGRAM_OUTPUT_MISMATCH')
    validation = read_json(root/'run/validation/validation.json')
    data = read_json(root/'run/recheck.json')['data']
    if validation != data['validation'] or validation.get('accepted') is not True:
        raise ValueError('VALIDATION_FAILED')
    findings = data['findings']
    if any(f.get('type') == 'MISSING' for f in findings):
        raise ValueError('MISSING_REMAINS')
    if read_json(root/'source-before.json') != read_json(root/'source-after.json'):
        raise ValueError('SOURCE_CHANGED')
    return {'status': 'PASS', 'kind': 'teacher_project', 'missing_count': 0, 'findings': findings}


_failure_output = None


def _main():
    global _failure_output
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    for name in ('c4', 'c7', 'h3', 'verify'):
        q = sub.add_parser(name)
        q.add_argument('--out', type=Path, required=True)
        if name in ('c4', 'c7'):
            q.add_argument('--entry', type=Path, required=True)
            q.add_argument('--project', type=Path, required=True)
            q.add_argument('--request', type=Path, required=True)
            q.add_argument('--timeout', type=float, default=1800)
        if name == 'c4':
            q.add_argument('--build-timeout', type=float, default=0.01)
        if name == 'c7':
            q.add_argument('--failed-request', type=Path, required=True)
        if name == 'h3':
            q.add_argument('--zip', type=Path, required=True)
            q.add_argument('--work', type=Path, required=True)
            q.add_argument('--entry', type=Path)
            q.add_argument('--run', action='store_true')
        if name == 'verify':
            q.add_argument('--evidence', type=Path, required=True)
    a = p.parse_args()
    proposed = a.out.absolute()
    work = Path(__file__).resolve().parents[2] / 'work'
    if a.mode != 'verify':
        resolved = proposed.resolve()
        if (proposed.is_symlink() or proposed.exists() or resolved == work or
                not resolved.is_relative_to(work.resolve())):
            p.error('Output must be a new directory below work/')
        if a.mode in ('c4', 'c7') and resolved.is_relative_to(a.project.resolve()):
            p.error('Output must be outside the source project')
    if a.mode == 'c7':
        try:
            if not a.entry.is_file() or not a.project.is_dir() or not a.request.is_file() or not a.failed_request.is_file():
                p.error('C7 input paths must exist')
            c7_validate_paths(work, a.project, proposed/'failed', proposed/'succeeded')
        except ValueError as exc:
            p.error(str(exc))
    out = fresh(a.out)
    _failure_output = out
    if a.mode == 'verify':
        record = read_json(a.evidence)
        if record.get('case') == 'C4':
            checked = verify_c4_directory(Path(a.evidence).resolve().parent)
            save(out / 'verification.json', checked)
            return 0 if checked['status'] == 'PASS' else 3 if checked['status'] == 'BLOCKED' else 1
        elif record.get('case') == 'C7':
            if a.evidence.is_symlink() or a.evidence.name != 'isolation-check.json':
                raise ValueError('C7_SUMMARY_PATH_INVALID')
            verdict = verify_c7_evidence(a.evidence.parent)['status']
        elif record.get('case') == 'H3':
            plan = record.get('plan', record)
            if plan.get('schema_version') == 'e13-h3-plan-1':
                verdict = h3_verify_new_run(plan, record['directory']) if record.get('directory') else h3_verify_new_plan(plan, Path(a.evidence).resolve().parent)
            else:
                raise ValueError('LEGACY_H3_EVIDENCE_NOT_SUPPORTED')
            verdict = verdict['status']
        else:
            raise ValueError('UNSUPPORTED_EVIDENCE')
        save(out / 'verification.json', {'status': verdict})
        return 0 if verdict == 'PASS' else 3 if verdict == 'BLOCKED' else 1
    if a.mode in ('c4', 'c7'):
        before = source_state(a.project)
        observation_before = observe()
        if a.mode == 'c4':
            record = run_c4(a.entry, a.project, a.request, out, a.timeout, a.build_timeout)
            return 0 if record['status'] == 'PASS' else 3 if record['status'] == 'BLOCKED' else 1
        else:
            return run_c7(a.entry, a.project, a.failed_request, a.request, out, a.timeout, before, c7_observe())
    try:
        plan = h3_create_plan(a.zip, out)
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        save(out/'failure.json', {'failure_stage':'h3_plan','status':'BLOCKED',
                                  'error_type':type(exc).__name__,'error_message':str(exc)})
        return 3
    if a.run:
        if not a.entry:
            raise ValueError('ENTRY_REQUIRED')
        h3_verify_new_plan(plan,out)
        extracted=out/'input'
        h3_extract_checked(a.zip,extracted)
        folder=extracted/H3_PREFIX
        if h3_source_identity(folder) != plan['identity'] or digest(a.zip) != plan['zip_sha256']:
            raise ValueError('FORMAL_SOURCE_MISMATCH')
        save(out/'source-before.json',source_state(folder/'repo'))
        run=launch(a.entry,out/'request.json',out/'run',out/'console.log',7200)
        (out/'exit-code.txt').write_text(str(run['exit_code'])+'\n')
        save(out/'source-after.json',source_state(folder/'repo'))
        result=read_json(out/'run/result.json')
        save(out/'evidence-manifest.json',h3_manifest_file(out,result))
        verdict=h3_verify_new_run(plan,out)
        save(out/'verification.json',verdict)
        return 0 if verdict['status'] == 'PASS' else 1

    return 0


def main():
    global _failure_output
    _failure_output = None
    try:
        return _main()
    except Exception as exc:
        if _failure_output is not None:
            try:
                evidence = sorted(str(p.relative_to(_failure_output)) for p in _failure_output.rglob('*') if p.is_file())
                save(_failure_output/'failure.json', {'failure_stage':'exception', 'error_type':type(exc).__name__,
                     'error':str(exc), 'evidence':evidence})
            except OSError:
                pass
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
