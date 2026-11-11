"""E12 B1 only: validate maintained-project provenance and run isolated DRAFT.

No detector, repair, pipeline or API modules are imported here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from vendor.draft.autobuild import auto_build, instructions, prepare_candidate

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = {'name': '241880360', 'email': '241880360@smail.nju.edu.cn'}
INSTALL = ('RUN apt-get update && apt-get install -y --no-install-recommends '
           'gcc make libc6-dev && rm -rf /var/lib/apt/lists/*')
FORBIDDEN = {'incremental-check.json', 'candidate.patch', 'repair.json',
             'recheck.json', 'full-check.json'}


def git(repo, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(['git', '-C', str(repo), *args], env=env,
                            capture_output=True, timeout=60, check=True)
    return result.stdout


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{40}', value),
            'Full lowercase 40-character SHA required')
    return value


def local(root, value):
    require(isinstance(value, str) and not Path(value).is_absolute(), 'Relative repo path required')
    path = (root / value).resolve()
    require(path.is_relative_to(root.resolve()) and path != root.resolve(), 'Path outside outer repo')
    return path


def state(repo):
    files = {}
    for raw in git(repo, 'ls-files', '-z').split(b'\0'):
        if not raw:
            continue
        name = os.fsdecode(raw)
        p = repo / name
        require(p.is_file() and not p.is_symlink(), 'Tracked regular files required')
        files[name] = digest(p.read_bytes())
    return {'files': files, 'head': git(repo, 'rev-parse', 'HEAD').decode().strip(),
            'refs': git(repo, 'show-ref').decode(),
            'status': git(repo, 'status', '--porcelain=v1', '--untracked-files=all').decode(),
            'identity': {k: git(repo, 'config', '--local', '--get', 'user.' + k).decode().strip()
                         for k in ('name', 'email')}}


def check_candidate(broken, candidate):
    original, proposed = instructions(broken), instructions(candidate)
    require(len(original) == 5, 'Unexpected broken Dockerfile structure')
    require(re.fullmatch(r'FROM \S+@sha256:[0-9a-f]{64}', original[0]), 'Pinned broken FROM required')
    require(original[1:] == ['WORKDIR /work', 'COPY main.c helper.c *.h Makefile ./',
                            'RUN make app', 'CMD ["./app"]'], 'Unexpected project/build/runtime instructions')
    require(proposed == original[:3] + [INSTALL] + original[3:],
            'Only reviewed system dependency installation before make is allowed')
    prepare_candidate(broken, candidate)


def check_inputs(request, root=ROOT):
    repo = local(root, request['repo'])
    require(repo.is_dir() and (repo / '.git').is_dir(), 'Independent repository required')
    candidate = local(root, request['candidate'])
    source = json.loads(local(root, request['source']).read_text(encoding='utf-8'))
    require(source['project_type'] == 'e12-b-group-maintained', 'Wrong project type')
    require(source['derived_from_stage'] == 'E7' and source['derived_from_path'] == 'fixtures/draft',
            'Wrong fixture provenance')
    require(source['outer_repository_uri'] == 'https://github.com/Rowan-hhh/devops-e4-draft.git',
            'Wrong source repository')
    require(source['identity'] == IDENTITY, 'Wrong maintained-project identity')
    require(source['a_group_report_received'] is False and source['server_draft_executed'] is False,
            'Expected pre-server source manifest')
    base, target = sha(request['base']), sha(request['target'])
    require(base != target, 'Base and target must differ')
    require((base, target) == (source['base'], source['target']), 'Source/request version mismatch')
    require(source['commits']['P1'] == base and source['commits']['P2'] == target, 'Wrong commit roles')
    require(source['base_is_ancestor'] is True, 'Missing ancestor declaration')
    p0 = sha(source['commits']['P0'])
    require(git(repo, 'rev-parse', '--is-shallow-repository').strip() == b'false', 'Shallow repository')
    for revision in (p0, base, target):
        require(git(repo, 'rev-parse', '--verify', revision + '^{commit}').decode().strip() == revision,
                'Commit missing')
        author = git(repo, 'show', '-s', '--format=%an%n%ae%n%cn%n%ce', revision).decode().splitlines()
        require(author == [IDENTITY['name'], IDENTITY['email']] * 2, 'Commit identity mismatch')
    git(repo, 'merge-base', '--is-ancestor', p0, base)
    git(repo, 'merge-base', '--is-ancestor', base, target)
    before = state(repo)
    require(before['head'] == target, 'HEAD must equal target')
    require(before['status'] == '', 'Dirty project worktree')
    require(before['identity'] == IDENTITY, 'Local identity mismatch')
    require(before['files'] == source['project_files'], 'Project file hashes mismatch')
    outer = sha(source['source_outer_commit'])
    e7 = sha(source['source_e7_commit'])
    introduced = sha(source['source_fixture_introduced_commit'])
    for revision in (outer, e7, introduced):
        git(root, 'rev-parse', '--verify', revision + '^{commit}')
    fixture_names = git(root, 'ls-tree', '-r', '--name-only', outer, '--', 'fixtures/draft').decode().splitlines()
    expected = {name.removeprefix('fixtures/draft/'): digest(git(root, 'show', outer + ':' + name))
                for name in fixture_names}
    require(expected and expected == source['original_fixture_sha256'], 'Source hashes mismatch')
    for name in expected:
        path = 'fixtures/draft/' + name
        require(digest(git(root, 'show', e7 + ':' + path)) == expected[name], 'E7 source differs')
        require(digest(git(root, 'show', introduced + ':' + path)) == expected[name], 'Original fixture differs')
        require(digest(git(repo, 'show', p0 + ':' + name)) == expected[name], 'P0 import differs')
    bundle = local(root, source['bundle'])
    require(digest(bundle.read_bytes()) == source['bundle_sha256'], 'Bundle hash mismatch')
    git(repo, 'bundle', 'verify', str(bundle))
    provenance = json.loads(local(root, request['candidate_provenance']).read_text(encoding='utf-8'))
    require(provenance['acquisition'] == 'manual' and provenance['model_generated'] is False,
            'Candidate must record manual provenance')
    require(provenance['candidate_sha256'] == digest(candidate.read_bytes()), 'Candidate hash mismatch')
    require(source['expected_stdout'] == '1\n' and source['expected_stderr'] == ''
            and source['expected_exit_code'] == 0, 'Unexpected program contract')
    return repo, candidate, source, before


def check_structure(project):
    require({p.name for p in project.glob('*.c')} == {'main.c', 'helper.c'}, 'Two-source profile required')
    for name in ('config.h', 'output_format.h', 'Makefile', 'SOURCE.md', 'Dockerfile.broken'):
        require((project / name).is_file(), 'Missing project input: ' + name)
    require(not any(p.is_symlink() for p in project.rglob('*')), 'Symlinks unsupported')


def run(request, out, root=ROOT):
    out = Path(out).absolute()
    require(not out.exists() and not out.is_symlink(), 'Output path already exists')
    repo = local(root, request['repo'])
    require(not out.resolve().is_relative_to(repo), 'Output must be outside project')
    result = {'schema_version': 'e12-b1-1', 'status': 'RUNNING',
              'base': request['base'], 'target': request['target'],
              'a_group_report_received': False}
    output_created = False
    repo, candidate, source, before = check_inputs(request, root)
    try:
        out.mkdir(parents=True, exist_ok=False)
        output_created = True
        save(out / 'request.json', request)
        save(out / 'source-before.json', before)
        return run_draft(request, out, root, repo, candidate, result)
    finally:
        # A pending exception must survive best-effort evidence writes. Invariance
        # is decided in memory before attempting any further filesystem output.
        pending = sys.exc_info()[1]
        after = None
        invariant_error = None
        try:
            after = state(repo)
            result['source_unchanged'] = before == after
            if not result['source_unchanged']:
                invariant_error = ValueError('Original project changed')
        except Exception as exc:
            result['source_unchanged'] = False
            invariant_error = ValueError('Original project state verification failed: ' + str(exc))
        if pending is not None:
            result.update(status='FAILED', error=str(pending))
        if invariant_error is not None:
            result.update(status='FAILED', error=str(invariant_error))

        evidence_errors = []
        if output_created:
            try:
                unexpected = [str(p.relative_to(out)) for p in out.rglob('*') if p.name in FORBIDDEN]
                if unexpected:
                    result.update(status='FAILED', error='Forbidden downstream output', forbidden=unexpected)
                if after is not None:
                    save(out / 'source-after.json', after)
            except Exception as exc:
                evidence_errors.append(exc)
                result.update(status='FAILED', evidence_error=str(exc))
            try:
                save(out / 'result.json', result)
            except Exception as exc:
                evidence_errors.append(exc)

        if pending is not None:
            if invariant_error is not None:
                if isinstance(pending, Exception):
                    raise invariant_error from pending
                # Preserve KeyboardInterrupt/SystemExit, with the failed
                # invariance verdict attached instead of swallowing the signal.
                pending.add_note(str(invariant_error))
        elif evidence_errors:
            if invariant_error is not None:
                raise invariant_error from evidence_errors[0]
            raise evidence_errors[0]


def run_draft(request, out, root, repo, candidate, result):
    """Keep the existing DRAFT failure/timeout result contract inside run's guard."""
    try:
        project = out / 'target-project'
        git(repo, 'clone', '--no-hardlinks', '--no-checkout', str(repo), str(project))
        git(project, 'checkout', '--detach', request['target'])
        check_structure(project)
        check_candidate((project / 'Dockerfile.broken').read_text(), candidate.read_text())
        candidate_copy = out / 'candidate.Dockerfile'
        candidate_copy.write_bytes(candidate.read_bytes())
        provenance = json.loads(local(root, request['candidate_provenance']).read_text())
        require(digest(candidate_copy.read_bytes()) == provenance['candidate_sha256'], 'Candidate changed')
        draft = auto_build(project, candidate_copy, out / 'draft-build', '1',
                           timeout=request.get('build_timeout', 600),
                           verify_timeout=request.get('verify_timeout', 30),
                           candidate_source='Manually prepared; adapted from verified E5/E7 dependency installation; no model call')
        save(out / 'draft.json', draft)
        result['status'] = draft['status'] if draft['status'] in ('FAILED', 'TIMED_OUT') else 'FAILED'
        if draft['status'] == 'SUCCEEDED':
            attempts = draft['attempts']
            require(len(attempts) == 2 and attempts[0]['build_exit_code'] != 0
                    and attempts[0]['failure_class'] == 'MISSING_MAKE'
                    and attempts[1]['build_exit_code'] == 0, 'Incomplete build evidence')
            require(re.fullmatch('sha256:[0-9a-f]{64}', attempts[1]['image_id']), 'Invalid image ID')
            verification = draft['verification']
            require(verification['exit_code'] == 0 and verification['actual_output'] == '1\n'
                    and verification['output_matches'], 'Runtime contract mismatch')
            require((out / 'draft-build/verify-stderr.log').read_bytes() == b'', 'Runtime stderr not empty')
            result['status'] = 'SUCCEEDED'
    except (TimeoutError, subprocess.TimeoutExpired) as exc:
        result.update(status='TIMED_OUT', error=str(exc))
    except Exception as exc:
        result.update(status='FAILED', error=str(exc))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run(json.loads(args.request.read_text(encoding='utf-8')), args.out)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, str(exc) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'SUCCEEDED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
