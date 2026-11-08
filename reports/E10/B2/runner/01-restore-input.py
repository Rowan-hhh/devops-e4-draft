from pathlib import Path
import hashlib, json, shutil, subprocess, sys
from lab import run, save

out = Path(sys.argv[1])
project = out / 'project'
bundle = Path('/course/reports/E10/B1/project.bundle')
subprocess.run(['git', 'clone', str(bundle), str(project)], check=True, text=True)
head = run(['git', 'rev-parse', 'HEAD'], project).strip()
assert head == '93ea08243be717cfe00502120ddebf2d090bdff7', head
assert run(['git', 'status', '--porcelain', '--ignored'], project) == ''

upstream = Path('/course/reports/E10/B3')
for name in ('fixed-md-report.json', 'candidate.patch', 'patch-plan.json', 'source-before.Makefile'):
    shutil.copy2(upstream / name, out / name)
assert (out / 'source-before.Makefile').read_bytes() == (project / 'Makefile').read_bytes()
tracked = run(['git', 'ls-files', '-z'], project).split('\0')
hashes = {name: hashlib.sha256((project / name).read_bytes()).hexdigest() for name in tracked if name}
save(out / 'input-file-hashes.json', hashes)
(out / 'project-head.txt').write_text(head + '\n')
print('RESTORED_B1_PROJECT', project)
print('PROJECT_HEAD', head)
print('SOURCE_BEFORE_SHA256', hashlib.sha256((project / 'Makefile').read_bytes()).hexdigest())
