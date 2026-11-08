from pathlib import Path
import json, sys
from lab import validate

out = Path(sys.argv[1])
project = out / 'project'
before = (project / 'Makefile').read_bytes()
assert before == (out / 'source-after-accept.Makefile').read_bytes()
(out / 'broken.patch').write_text('invalid patch\n')
result = validate(project, out / 'broken.patch', out / 'reject-patch')
assert result['accepted'] is False
assert result['rollback'] is True and result['source_unchanged'] is True
assert result['error'] and 'COMMAND_FAILED' in result['error']
assert (project / 'Makefile').read_bytes() == before
print('EXPECTED_BAD_PATCH_REJECTION', json.dumps(result, ensure_ascii=False, indent=2))
