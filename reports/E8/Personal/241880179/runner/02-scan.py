from pathlib import Path
import sys
from lab import save, scan

out = Path(sys.argv[1])
report = scan(out / 'project')
save(out / 'fixed-md-report.json', report)
expected = {
    ('MISSING', 'main.o', 'config.h'),
    ('REDUNDANT', 'main.o', 'unused.h'),
}
actual = {(f['type'], f['target'], f['dependency']) for f in report['findings']}
assert actual == expected, actual
print('REPORT_COMMIT', report['commit'])
print('FINDINGS', report['findings'])
