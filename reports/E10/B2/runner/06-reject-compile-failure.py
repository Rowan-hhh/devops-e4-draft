from pathlib import Path
import difflib, json, subprocess, sys
from lab import run, validate

out = Path(sys.argv[1])
project = out / 'compile-project'
subprocess.run(['git', 'clone', '/course/reports/E10/B1/project.bundle', str(project)], check=True, text=True)
before = (project / 'Makefile').read_bytes()
original = before.decode()
broken = original.replace('\tgcc $(CFLAGS) -c main.c -o main.o', '\tfalse')
assert original != broken
candidate = out / 'compile-failure.patch'
candidate.write_text(''.join(difflib.unified_diff(
    original.splitlines(True), broken.splitlines(True),
    fromfile='a/Makefile', tofile='b/Makefile',
)))
result = validate(project, candidate, out / 'reject-compile')
assert result['accepted'] is False
assert result['checks']['patch_applies'] is True
assert 'build' not in result['checks']
assert result['rollback'] is True and result['source_unchanged'] is True
assert result['error'] and 'COMMAND_FAILED' in result['error']
assert (project / 'Makefile').read_bytes() == before
assert run(['git', 'status', '--porcelain'], project) == ''
print('EXPECTED_COMPILE_REJECTION', json.dumps(result, ensure_ascii=False, indent=2))
