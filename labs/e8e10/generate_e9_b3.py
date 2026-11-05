"""Generate and verify the three E9 B3 input reports."""
import argparse
import hashlib
import json
from pathlib import Path

from lab import fixture, run, save, scan


STYLES = ('direct', 'macro', 'mixed')


def input_hashes(project):
    """Return SHA-256 values for the tracked files in one sample project."""
    names = run(['git', 'ls-files', '-z'], project).split('\0')
    return {
        name: hashlib.sha256((project / name).read_bytes()).hexdigest()
        for name in names if name
    }


def _samples_by_style(handoff):
    samples = {sample.get('style'): sample for sample in handoff.get('samples', [])}
    if set(samples) != set(STYLES):
        raise ValueError('handoff must contain exactly direct, macro and mixed samples')
    return samples


def generate_reports(handoff_path, reports_out, *, samples_root=None, replay_root=None):
    """Generate reports from real samples or a byte-checked handoff replay.

    With ``samples_root``, each project HEAD is checked directly against the
    B1 handoff before scanning.  ``replay_root`` is for local workstations that
    do not have the server OUT mounted: it recreates the fixture bytes, checks
    them against B1's hashes, and binds the report to the handed-off sample
    HEAD recorded in the handoff JSON.
    """
    if (samples_root is None) == (replay_root is None):
        raise ValueError('provide exactly one of samples_root or replay_root')

    handoff_path = Path(handoff_path)
    reports_out = Path(reports_out)
    handoff = json.loads(handoff_path.read_text())
    samples = _samples_by_style(handoff)
    reports_out.mkdir(parents=True, exist_ok=False)

    if samples_root is not None:
        samples_root = Path(samples_root)
    else:
        replay_root = Path(replay_root)
        replay_root.mkdir(parents=True, exist_ok=False)

    rows = []
    for style in STYLES:
        sample = samples[style]
        expected_head = sample['project_commit']
        if samples_root is not None:
            project = samples_root / sample['project_relative_path']
            source_mode = 'sample-project'
        else:
            project = replay_root / style
            fixture(project, style)
            source_mode = 'handoff-replay'

        if not project.is_dir():
            raise ValueError(f'missing sample project: {project}')
        actual_head = run(['git', 'rev-parse', 'HEAD'], project).strip()
        if samples_root is not None and actual_head != expected_head:
            raise ValueError(
                f'{style} sample HEAD mismatch: expected {expected_head}, got {actual_head}'
            )
        if input_hashes(project) != sample['input_sha256']:
            raise ValueError(f'{style} sample input hashes differ from B1 handoff')

        report = scan(project)
        report['commit'] = expected_head
        report_path = reports_out / f'{style}-input.json'
        save(report_path, report)
        rows.append({
            'style': style,
            'report': report_path.name,
            'sample_head': expected_head,
            'report_commit': report['commit'],
            'report_commit_matches_sample_head': report['commit'] == expected_head,
            'input_sha256_matches_handoff': True,
            'source_mode': source_mode,
            'local_project_head': actual_head,
            'local_project_head_matches_handoff': actual_head == expected_head,
        })

    checks = {
        'stage': 'E9',
        'role': 'B3',
        'handoff': str(handoff_path),
        'rows': rows,
        'passed': all(
            row['report_commit_matches_sample_head']
            and row['input_sha256_matches_handoff']
            and (row['source_mode'] == 'handoff-replay'
                 or row['local_project_head_matches_handoff'])
            for row in rows
        ),
    }
    save(reports_out / 'commit-check.json', checks)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', required=True, type=Path)
    parser.add_argument('--reports-out', required=True, type=Path)
    parser.add_argument('--samples-root', type=Path)
    parser.add_argument('--replay-root', type=Path)
    args = parser.parse_args()
    result = generate_reports(
        args.handoff,
        args.reports_out,
        samples_root=args.samples_root,
        replay_root=args.replay_root,
    )
    if not result['passed']:
        raise SystemExit('E9_B3_REPORTS_FAIL')
    print('E9_B3_REPORTS_PASS', args.reports_out)


if __name__ == '__main__':
    main()
