from pathlib import Path
import json, sys
from lab import patch, save

out = Path(sys.argv[1])
project = out / 'project'
report = json.loads((out / 'fixed-md-report.json').read_text())
before = (project / 'Makefile').read_bytes()
diff, edits = patch(project, report)
(out / 'candidate.patch').write_text(diff)
save(out / 'patch-plan.json', edits)
assert '+main.o: main.c unused.h config.h' in diff
assert edits == [{'target': 'main.o', 'dependency': 'config.h', 'style': 'direct'}]
assert (project / 'Makefile').read_bytes() == before
print(diff)
print(edits)
print('PATCH_GENERATED_SOURCE_UNCHANGED')
