"""Collect the E10 B3 fixed report and candidate patch artifacts."""
import argparse
import hashlib
from pathlib import Path

from lab import patch, run, save, scan


def generate(project, output, *, expected_head, evidence=None):
    """Generate B3 artifacts from one pristine, versioned project."""
    project = Path(project).resolve()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)

    actual_head = run(['git', 'rev-parse', 'HEAD'], project).strip()
    if actual_head != expected_head:
        raise ValueError(
            f'sample HEAD mismatch: expected {expected_head}, got {actual_head}'
        )
    status_before = run(['git', 'status', '--porcelain', '--untracked-files=all'], project)
    if status_before:
        raise ValueError(f'sample project is not clean: {status_before!r}')

    source_before = (project / 'Makefile').read_bytes()
    report = scan(project)
    if report['commit'] != actual_head:
        raise ValueError('scan report commit does not match sample HEAD')
    save(output / 'fixed-md-report.json', report)

    diff, plan = patch(project, report)
    (output / 'candidate.patch').write_text(diff, encoding='utf-8')
    save(output / 'patch-plan.json', plan)
    (output / 'source-before.Makefile').write_bytes(source_before)

    source_unchanged = (project / 'Makefile').read_bytes() == source_before
    status_after = run(['git', 'status', '--porcelain', '--untracked-files=all'], project)
    checks = {
        'passed': source_unchanged and not status_after,
        'sample_head': actual_head,
        'report_commit': report['commit'],
        'report_commit_matches_head': report['commit'] == actual_head,
        'source_before_sha256': hashlib.sha256(source_before).hexdigest(),
        'source_before_bytes_preserved': source_unchanged,
        'worktree_clean_before': not status_before,
        'worktree_clean_after': not status_after,
    }
    if evidence is not None:
        save(Path(evidence) / 'b3-identity.json', checks)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    result = generate(
        args.project,
        args.out,
        expected_head=args.expected_head,
        evidence=args.evidence,
    )
    if not result['passed']:
        raise SystemExit('E10_B3_REPORTS_FAIL')
    print('E10_B3_REPORTS_PASS', result['sample_head'])


if __name__ == '__main__':
    main()
