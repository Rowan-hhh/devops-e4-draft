"""Initialize E9 B1 inputs; report and patch generation belong to later roles."""
import argparse
import hashlib
import shutil
from pathlib import Path

from lab import declarations, fixture, run, save


STYLES = ('direct', 'macro', 'mixed')
RULES = {
    'direct': 'main.o: main.c unused.h',
    'macro': 'main.o: $(DEPS)',
    'mixed': 'main.o: main.c $(HEADERS)',
}


def input_hashes(project):
    names = run(['git', 'ls-files', '-z'], project).split('\0')
    return {
        name: hashlib.sha256((project / name).read_bytes()).hexdigest()
        for name in names if name
    }


def initialize(out, smoke=False):
    """Create three pristine, separately versioned fixtures in a fresh directory."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    snapshots = out / 'initial-Makefiles'
    snapshots.mkdir()
    samples = []
    for style in STYLES:
        project = out / style
        fixture(project, style)
        text = (project / 'Makefile').read_text()
        assert RULES[style] in text.splitlines(), style
        if style == 'macro':
            assert 'DEPS = main.c unused.h' in text.splitlines()
        if style == 'mixed':
            assert 'HEADERS = unused.h' in text.splitlines()
        assert 'config.h' not in text
        declared, flags = declarations(project)
        assert declared == {
            'main.o': ['main.c', 'unused.h'],
            'helper.o': ['helper.c'],
        }
        assert flags == '-O0'
        assert run(['git', 'status', '--porcelain'], project) == ''
        assert run(['git', 'rev-list', '--count', 'HEAD'], project).strip() == '1'
        before = input_hashes(project)
        shutil.copyfile(project / 'Makefile', snapshots / (style + '.Makefile'))
        sample = {
            'style': style,
            'project_relative_path': style,
            'project_commit': run(['git', 'rev-parse', 'HEAD'], project).strip(),
            'declared': declared,
            'initial_rule': RULES[style],
            'input_sha256': before,
            'worktree_clean': True,
        }
        if smoke:
            check = out / 'smoke' / style
            shutil.copytree(project, check, ignore=shutil.ignore_patterns('.git'))
            build_log = run(['make', 'app'], check)
            output = run(['./app'], check)
            (check / 'build.log').write_text(build_log)
            (check / 'run.log').write_text(output)
            assert output.strip() == '1', style
            sample['smoke'] = {'passed': True, 'output': output.strip(),
                               'directory': 'smoke/' + style}
        assert before == input_hashes(project)
        assert run(['git', 'status', '--porcelain'], project) == ''
        samples.append(sample)
    manifest = {'stage': 'E9', 'role': 'B1', 'samples': samples,
                'reports_generated': False, 'patches_generated': False,
                'all_sample_worktrees_clean': True}
    save(out / 'sample-manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    out = args.out.resolve()
    if out == root / 'work' or not out.is_relative_to(root / 'work'):
        parser.error('--out must be a fresh subdirectory of the repository work/')
    result = initialize(out, smoke=args.smoke)
    source = run(['git', 'rev-parse', 'HEAD'], root).strip()
    (out / 'student-source-commit.txt').write_text(source + '\n')
    for sample in result['samples']:
        print('SAMPLE_READY', sample['style'], sample['project_commit'])
    print('E9_B1_INITIALIZATION_PASS', out)


if __name__ == '__main__':
    main()
