"""Prepare a clean E10 B1 direct project and build only an isolated copy."""
import argparse
import hashlib
import platform
import shutil
import tempfile
from pathlib import Path

from lab import fixture, run, save

BASELINE = '7a7ff8de16930742201ad59f07b22e96380fcb15'
BRANCH = 'e10-yrh-b1'


def input_hashes(project):
    names = run(['git', 'ls-files', '-z'], project).split('\0')
    return {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
            for name in names if name}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def initialize(out, *, repository=None, image_id=None, expected_branch=None):
    """Create a new OUT; preserve its project for B3 report/patch generation.

    image_id, when supplied, is caller-provided metadata from image inspection;
    toolchain versions below are collected in the actual execution environment.
    """
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError(f'output directory already exists: {out}')
    repository = (Path(repository) if repository is not None
                  else Path(__file__).resolve().parents[2])
    branch = run(['git', 'branch', '--show-current'], repository).strip()
    if expected_branch is not None:
        require(branch == expected_branch, 'expected branch ' + expected_branch)
    head = run(['git', 'rev-parse', 'HEAD'], repository).strip()
    run(['git', 'merge-base', '--is-ancestor', BASELINE, head], repository)
    source_status = run(['git', 'status', '--porcelain', '--untracked-files=all'], repository)
    environment = {
        'system': platform.system(), 'architecture': platform.machine(),
        'python': platform.python_version(),
        'git': run(['git', '--version'], repository).strip(),
        'gcc': run(['gcc', '--version'], repository).splitlines()[0],
        'make': run(['make', '--version'], repository).splitlines()[0],
        'image_id': image_id,
        'image_id_source': 'caller-provided' if image_id else 'not-supplied',
    }
    out.mkdir(parents=True, exist_ok=False)
    project = out / 'project'
    fixture(project, 'direct')
    before = input_hashes(project)
    project_head = run(['git', 'rev-parse', 'HEAD'], project).strip()
    require(run(['git', 'status', '--porcelain', '--ignored'], project) == '',
            'initial project is not pristine')
    require('main.o: main.c unused.h' in (project / 'Makefile').read_text().splitlines(),
            'unexpected direct declaration')
    logs = out / 'build'
    logs.mkdir()
    # Keep build products outside the handoff, including on build failure.
    with tempfile.TemporaryDirectory(prefix='e10-b1-build-') as directory:
        isolated = Path(directory) / 'project'
        shutil.copytree(project, isolated, ignore=shutil.ignore_patterns('.git'))
        for name, command in [('clean', ['make', 'clean']), ('app', ['make', 'app']),
                              ('run', ['./app'])]:
            output = run(command, isolated)
            (logs / (name + '.log')).write_text(
                '$ ' + ' '.join(command) + '\n' + output + 'exit_code=0\n')
            if name == 'run':
                require(output.strip() == '1', 'expected application output 1')
    after = input_hashes(project)
    status = run(['git', 'status', '--porcelain', '--ignored'], project)
    require(before == after and status == '', 'handoff project changed during build')
    require(run(['git', 'rev-parse', 'HEAD'], project).strip() == project_head,
            'handoff HEAD changed')
    result = {
        'schema_version': 1, 'student_id': '241880360', 'stage': 'E10', 'role': 'B1',
        'branch': branch, 'baseline_commit': BASELINE, 'execution_commit': head,
        'source_state': {'porcelain': source_status, 'clean': source_status == ''},
        'out': str(out), 'environment': environment,
        'sample': {'style': 'direct', 'project_relative_path': 'project',
                   'project_commit': project_head, 'input_sha256': before,
                   'input_sha256_after_build': after, 'worktree_clean': True,
                   'build_artifacts_absent': True},
        'build': {'isolated': True, 'passed': True, 'output': '1',
                  'logs': ['build/clean.log', 'build/app.log', 'build/run.log']},
        'handoff_to': 'B3', 'reports_generated': False, 'patches_generated': False,
    }
    save(out / '241880360-handoff.json', result)
    (out / 'student-source-commit.txt').write_text(head + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--image-id', help='image ID obtained from docker image inspect')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = args.out.resolve()
    if out == root / 'work' or not out.is_relative_to(root / 'work'):
        parser.error('--out must be a new subdirectory of repository work/')
    result = initialize(out, repository=root, image_id=args.image_id,
                        expected_branch=BRANCH)
    print('E10_B1_READY', result['sample']['project_commit'], out)


if __name__ == '__main__':
    main()
