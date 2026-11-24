"""Verify rejection contracts; write evidence only into a new output directory.

Core verify(project, out) accepts a C/Make fixture repository, including detached
HEAD. The CLI creates a disposable fixture unless --repo supplies such a project.
No Docker build or full pipeline execution is needed for these contract gates.
"""
import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path

import pipeline
from lab import commit, fixture, run, scan


CASES = (
    ('old_commit', 'STALE_REPORT'),
    ('wrong_schema', 'SCHEMA_MISMATCH'),
    ('wrong_kind', 'ARTIFACT_TYPE_MISMATCH'),
    ('changed_artifact', 'ARTIFACT_HASH_MISMATCH'),
    ('failed_upstream', 'UPSTREAM_FAILED'),
)


def snapshot(root):
    """Relative names and content hashes, including untracked and Git files."""
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
                    + '\n', encoding='utf-8')


def consume(project, artifact, digest, repair_output):
    """Use production gates before allowing the real patch generator to run."""
    envelope = pipeline.load_artifact(artifact, digest)
    target = run(['git', 'rev-parse', 'HEAD'], project).strip()
    pipeline.check_envelope(envelope, target, 'fixed-md')
    if envelope['data'].get('commit') != target:
        raise pipeline.Failure('STALE_REPORT', 'Fixed report data commit mismatch')
    diff, plan = pipeline.patch(project, envelope['data'])
    (repair_output / 'candidate.patch').write_text(diff, encoding='utf-8')
    save(repair_output / 'repair-plan.json', plan)


def verify(project, out):
    """Exercise five real invalid inputs; never overwrite even an empty directory."""
    project, out = Path(project).resolve(), Path(out).absolute()
    if out.exists() or out.is_symlink():
        raise pipeline.Failure('OUTPUT_EXISTS', 'Use a new output directory')
    # Prevent verification itself from writing inside the source repository.
    if out.resolve().is_relative_to(project):
        raise ValueError('Output must be outside the source project')
    source_before = snapshot(project)
    report = scan(project)
    envelope = {'schema_version': 'e11e12-1', 'kind': 'fixed-md',
                'status': 'SUCCEEDED', 'commit': report['commit'], 'data': report}
    pipeline.check_envelope(envelope, report['commit'], 'fixed-md')
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, expected in CASES:
        folder = out / name
        folder.mkdir()
        repair_output = folder / 'repair-output'
        repair_output.mkdir()
        invalid = copy.deepcopy(envelope)
        if name == 'old_commit':
            invalid['commit'] = run(['git', 'rev-parse', 'HEAD^'], project).strip()
        elif name == 'wrong_schema':
            invalid['schema_version'] = 'unsupported'
        elif name == 'wrong_kind':
            invalid['kind'] = 'incremental-check'
        elif name == 'failed_upstream':
            invalid['status'] = 'FAILED'
        artifact = folder / 'input.json'
        # Elapsed timing is irrelevant to the contract and not stable evidence.
        invalid['data'].pop('elapsed_s', None)
        save(artifact, invalid)
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if name == 'changed_artifact':
            artifact.write_bytes(artifact.read_bytes() + b'\n')
        before = snapshot(repair_output)
        actual = None
        try:
            consume(project, artifact, digest, repair_output)
        except pipeline.Failure as exc:
            actual = exc.code
        after = snapshot(repair_output)
        source_after = snapshot(project)
        row = {'case': name, 'expected_error': expected, 'actual_error': actual,
               'rejected': actual is not None,
               'patch_generated': any(folder.rglob('candidate.patch')),
               'source_unchanged': source_after == source_before,
               'output_unchanged': before == after,
               'input': f'{name}/input.json',
               'expected_sha256': digest,
               'actual_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
               'output_before': before, 'output_after': after}
        save(folder / 'result.json', row)
        rows.append(row)
    passed = all(r['actual_error'] == r['expected_error'] and r['rejected']
                 and not r['patch_generated'] and r['source_unchanged']
                 and r['output_unchanged'] for r in rows)
    save(out / 'source-before.json', source_before)
    save(out / 'source-after.json', snapshot(project))
    result = {'passed': passed, 'cases': len(rows), 'results': rows}
    save(out / 'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--repo', type=Path, help='C/Make fixture repository with HEAD parent')
    args = parser.parse_args()
    branch = run(['git', 'branch', '--show-current'], pipeline.ROOT).strip()
    if branch != 'student/241880360/e11-b3':
        parser.error('CLI requires student/241880360/e11-b3')
    try:
        if args.repo:
            result = verify(args.repo, args.out)
        else:
            with tempfile.TemporaryDirectory() as directory:
                project = Path(directory) / 'project'
                fixture(project)
                main = project / 'main.c'
                main.write_text('#include "extra.h"\n' + main.read_text())
                commit(project, 'two missing local headers')
                result = verify(project, args.out)
    except (pipeline.Failure, ValueError, OSError) as exc:
        parser.exit(1, f'{getattr(exc, "code", "VERIFY_FAILED")}: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
