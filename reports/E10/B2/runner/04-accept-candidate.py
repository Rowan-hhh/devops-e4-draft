from pathlib import Path
import json, sys
from lab import run, validate

out = Path(sys.argv[1])
project = out / 'project'
result = validate(project, out / 'candidate.patch', out / 'accept')
assert result['accepted'] is True and all(result['checks'].values())
assert result['source_unchanged'] is False and result['rollback'] is False
after = (project / 'Makefile').read_bytes()
assert b'main.o: main.c unused.h config.h' in after
assert (project / 'config.h').read_text() == '#define VALUE 1\n'
(out / 'source-after-accept.Makefile').write_bytes(after)
(out / 'accepted-project-diff.patch').write_text(run(['git', 'diff', '--', 'Makefile'], project))
print('ACCEPTED_ALL_CHECKS_PASS', json.dumps(result, ensure_ascii=False, indent=2))
