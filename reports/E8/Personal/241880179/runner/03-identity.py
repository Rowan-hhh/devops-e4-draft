from pathlib import Path
import json, sys
from lab import run, save

out = Path(sys.argv[1])
report = json.loads((out / 'fixed-md-report.json').read_text())
head = run(['git', 'rev-parse', 'HEAD'], out / 'project').strip()
missing = [f for f in report['findings'] if f['type'] == 'MISSING']
checks = {
    'report_commit_matches_project_head': report['commit'] == head,
    'one_missing_edge': len(missing) == 1,
    'missing_is_main_o_config_h': missing == [{'type': 'MISSING', 'target': 'main.o', 'dependency': 'config.h'}],
}
assert all(checks.values()), checks
save(out / 'report-identity.json', {'report_commit': report['commit'], 'project_head': head, 'checks': checks})
print('COMMIT_MATCH', head)
print('MD', missing)
