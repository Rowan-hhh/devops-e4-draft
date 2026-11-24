"""Verify E9 B4 patches without changing the original fixture projects."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lab import fixture, scan, patch, run, save

STYLES = ('direct', 'macro', 'mixed')
EXPECTED = {
    'direct': 'main.o: main.c unused.h config.h',
    'macro': 'DEPS = main.c unused.h config.h',
    'mixed': 'main.o: main.c $(HEADERS) config.h',
}
B3 = '0636c8fb950e4048e186b8960a28fc0edfb04070'
B2 = '127b945bb91f4d56f176955d726b8004c87620a6'


def source_state(project):
    names = run(['git', 'ls-files', '-z'], project).split('\0')
    return {
        'head': run(['git', 'rev-parse', 'HEAD'], project).strip(),
        'status': run(['git', 'status', '--porcelain', '--untracked-files=all'], project),
        'sha256': {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
                   for name in names if name},
    }


def recipes(data):
    return [line for line in data.splitlines(keepends=True) if line.startswith(b'\t')]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(out, repository):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    branch = run(['git', 'branch', '--show-current'], repository).strip()
    head = run(['git', 'rev-parse', 'HEAD'], repository).strip()
    require(branch == 'e9-yrh-b4', 'unexpected B4 branch')
    run(['git', 'merge-base', '--is-ancestor', B2, head], repository)
    run(['git', 'merge-base', '--is-ancestor', B3, B2], repository)
    handoff = json.loads((repository / 'reports/E9/B1/241880179-handoff.json').read_text())
    expected_hashes = {s['style']: s['input_sha256'] for s in handoff['samples']}
    rows = []
    with tempfile.TemporaryDirectory(prefix='e9-b4-') as directory:
        root = Path(directory)
        for style in STYLES:
            source = root / style
            fixture(source, style)
            before_bytes = (source / 'Makefile').read_bytes()
            before = source_state(source)
            require(before['status'] == '', 'source is not clean')
            require(before['sha256'] == expected_hashes[style], 'B1 input hash mismatch')
            report = scan(source)
            require(report['commit'] == before['head'], 'report identity mismatch')
            save(out / f'{style}-input.json', report)
            diff, plan = patch(source, report)
            require(plan == [{'target': 'main.o', 'dependency': 'config.h', 'style': style}],
                    'unexpected patch plan')
            candidate = out / f'{style}.patch'
            candidate.write_text(diff, encoding='utf-8')
            save(out / f'{style}-plan.json', plan)
            generated = source_state(source)
            require(generated == before, 'candidate generation changed source')
            checked = run(['git', 'apply', '--check', str(candidate)], source)
            after_check = source_state(source)
            require(after_check == before, 'apply check changed source')
            isolated = root / f'{style}-isolated'
            shutil.copytree(source, isolated)
            isolated_check = run(['git', 'apply', '--check', str(candidate)], isolated)
            applied = run(['git', 'apply', str(candidate)], isolated)
            (out / f'{style}-apply-check.log').write_text(
                '$ git apply --check <candidate> (original)\n' + checked + 'exit_code=0\n'
                '$ git apply --check <candidate> (isolated)\n' + isolated_check + 'exit_code=0\n'
                '$ git apply <candidate> (isolated)\n' + applied + 'exit_code=0\n')
            after_bytes = (isolated / 'Makefile').read_bytes()
            require(EXPECTED[style] in after_bytes.decode().splitlines(), 'wrong declaration')
            require(recipes(before_bytes) == recipes(after_bytes), 'recipe bytes changed')
            recheck = scan(isolated)
            require(recheck['findings'] == [
                {'type': 'REDUNDANT', 'target': 'main.o', 'dependency': 'unused.h'}
            ], 'unexpected post-apply findings')
            save(out / f'{style}-recheck.json', recheck)
            build = run(['make', 'clean'], isolated) + run(['make', 'app'], isolated)
            (out / f'{style}-build.log').write_text('$ make clean && make app\n' + build + 'exit_code=0\n')
            output = run(['./app'], isolated)
            (out / f'{style}-run.log').write_text('$ ./app\n' + output + 'exit_code=0\n')
            require(output.strip() == '1', 'unexpected application output')
            final = source_state(source)
            require(final == before and (source / 'Makefile').read_bytes() == before_bytes,
                    'isolated application/build changed source')
            save(out / f'{style}-source-state.json', {
                'before_candidate': before, 'after_candidate': generated,
                'after_apply_check': after_check, 'after_isolated_build': final,
                'all_states_equal': True, 'makefile_bytes_unchanged': True,
                'input_hashes_match_b1': True,
            })
            rows.append({'style': style, 'report_commit': report['commit'],
                         'report_matches_local_head': True, 'plan_style_correct': True,
                         'patch_check_passed': True, 'applied_only_to_isolated_copy': True,
                         'source_unchanged_and_clean': True, 'recipe_bytes_preserved': True,
                         'no_missing': True, 'redundant_unused_preserved': True,
                         'build_exit_code': 0, 'run_exit_code': 0, 'run_output': output.strip()})
    command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'labs/e8e10',
               '-p', 'test_profile.py', '-v']
    tests = subprocess.run(command, cwd=repository, text=True, capture_output=True)
    (out / 'unit-tests.log').write_text(
        '$ python3 -B -m unittest discover -s labs/e8e10 -p test_profile.py -v\n'
        + tests.stdout + tests.stderr)
    (out / 'unit-tests-exit-code.txt').write_text(str(tests.returncode) + '\n')
    result = {'schema_version': 1, 'student_id': '241880360',
              'stage': 'E9', 'role': 'B4', 'branch': branch,
              'baseline_commit': B2, 'execution_commit': head,
              'upstream': {'B3': B3, 'B2_final': B2},
              'source_mode': 'independent-local-fixtures-with-B1-hash-check',
              'rows': rows, 'unit_tests': {'exit_code': tests.returncode,
                                         'log': 'unit-tests.log'},
              'passed': tests.returncode == 0 and len(rows) == 3}
    save(out / 'acceptance.json', result)
    require(result['passed'], 'B4 acceptance failed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    result = verify(args.out, repository)
    print('E9_B4_PASS', len(result['rows']), 'styles; unit test exit code',
          result['unit_tests']['exit_code'])


if __name__ == '__main__':
    main()
