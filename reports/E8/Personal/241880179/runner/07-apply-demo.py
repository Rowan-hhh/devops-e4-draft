from pathlib import Path
import hashlib, json, shutil, subprocess, sys
from lab import run, save, scan

out = Path(sys.argv[1])
source = out / 'project'
demo = out / 'apply-demo'
shutil.copytree(source, demo)
tracked = run(['git', 'ls-files', '-z'], source).split('\0')
before_hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in tracked if name}
source_makefile = (source / 'Makefile').read_bytes()
source_recipes = [line for line in source_makefile.splitlines() if line.startswith(b'\t')]
run(['git', 'apply', str((out / 'candidate.patch').resolve())], demo)
demo_makefile = (demo / 'Makefile').read_bytes()
demo_recipes = [line for line in demo_makefile.splitlines() if line.startswith(b'\t')]
assert source_recipes == demo_recipes
assert b'main.o: main.c unused.h config.h' in demo_makefile
build_log = run(['make', 'clean'], demo) + run(['make', 'app'], demo)
(out / 'apply-build.log').write_text(build_log)
program_output = run(['./app'], demo).strip()
assert program_output == '1'
(out / 'apply-run.txt').write_text(program_output + '\n')
recheck = scan(demo)
save(out / 'apply-recheck.json', recheck)
findings = {(f['type'], f['target'], f['dependency']) for f in recheck['findings']}
assert not any(item[0] == 'MISSING' for item in findings)
assert ('REDUNDANT', 'main.o', 'unused.h') in findings
after_source_hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in tracked if name}
assert before_hashes == after_source_hashes
assert (source / 'Makefile').read_bytes() == source_makefile
assert run(['git', 'status', '--porcelain'], source).strip() == ''
result = {
    'patch_applied_in_copy': True,
    'build_passed': True,
    'program_output': program_output,
    'missing_edges_after_patch': [],
    'redundant_edge_preserved': True,
    'recipe_bytes_preserved': True,
    'original_project_clean': True,
    'original_input_hashes_unchanged': True,
    'demo_git_diff': run(['git', 'diff', '--', 'Makefile'], demo),
}
save(out / 'apply-result.json', result)
save(out / 'input-file-hashes-after.json', after_source_hashes)
print('APPLY_DEMO_PASS')
print(json.dumps(result, ensure_ascii=False, indent=2))
