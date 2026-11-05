from pathlib import Path
import json, sys
from lab import patch, save

out = Path(sys.argv[1])
project = out / 'project'
report = json.loads((out / 'fixed-md-report.json').read_text())
report['commit'] = '0' * 40
before = (project / 'Makefile').read_bytes()
try:
    patch(project, report)
except ValueError as error:
    assert str(error) == 'STALE_REPORT'
    save(out / 'expected-failure.json', {'error': str(error)})
    print('EXPECTED_REJECTION', error)
else:
    raise AssertionError('stale report was not rejected')
assert (project / 'Makefile').read_bytes() == before
print('SOURCE_BYTES_UNCHANGED')
