from pathlib import Path
import sys
from lab import run

out = Path(sys.argv[1])
project = out / 'project'
before = (project / 'Makefile').read_bytes()
print(run(['git', 'apply', '--check', str((out / 'candidate.patch').resolve())], project))
assert run(['git', 'status', '--porcelain'], project).strip() == ''
assert (project / 'Makefile').read_bytes() == before
print('APPLY_CHECK_PASS_SOURCE_CLEAN')
