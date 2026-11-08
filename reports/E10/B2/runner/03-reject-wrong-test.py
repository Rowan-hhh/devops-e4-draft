from pathlib import Path
import json, sys
from lab import validate

out = Path(sys.argv[1])
project = out / 'project'
before = (project / 'Makefile').read_bytes()
result = validate(project, out / 'candidate.patch', out / 'reject-test', fail_test=True)
assert result['accepted'] is False
assert result['checks']['patch_applies'] is True
assert result['checks']['build'] is True
assert result['checks']['test'] is False
assert result['checks']['header_change'] is True
assert result['checks']['no_missing'] is True
assert result['rollback'] is True and result['source_unchanged'] is True
assert (project / 'Makefile').read_bytes() == before == (out / 'source-before.Makefile').read_bytes()
print('EXPECTED_TEST_REJECTION', json.dumps(result, ensure_ascii=False, indent=2))
