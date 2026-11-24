from pathlib import Path
import hashlib, json, sys
from lab import run, save

out = Path(sys.argv[1])
project = out / 'project'
report = json.loads((out / 'fixed-md-report.json').read_text())
plan = json.loads((out / 'patch-plan.json').read_text())
head = run(['git', 'rev-parse', 'HEAD'], project).strip()
findings = {(f['type'], f['target'], f['dependency']) for f in report['findings']}
expected = {
    ('MISSING', 'main.o', 'config.h'),
    ('REDUNDANT', 'main.o', 'unused.h'),
}
checks = {
    'report_commit_matches_project_head': report['commit'] == head,
    'findings_match_expected': findings == expected,
    'plan_matches_expected': plan == [{'target': 'main.o', 'dependency': 'config.h', 'style': 'direct'}],
    'source_snapshot_matches_project': (out / 'source-before.Makefile').read_bytes() == (project / 'Makefile').read_bytes(),
    'project_clean_before_validation': run(['git', 'status', '--porcelain'], project) == '',
}
run(['git', 'apply', '--check', str((out / 'candidate.patch').resolve())], project)
checks['candidate_apply_check'] = True
assert all(checks.values()), checks
save(out / 'b3-input-check.json', {
    'project_head': head,
    'report_commit': report['commit'],
    'source_before_sha256': hashlib.sha256((out / 'source-before.Makefile').read_bytes()).hexdigest(),
    'checks': checks,
})
print('B3_INPUT_CHECK_PASS', json.dumps(checks, ensure_ascii=False, indent=2))
