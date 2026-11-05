from pathlib import Path
import hashlib, json, subprocess, sys
from lab import fixture, save

out = Path(sys.argv[1])
project = out / 'project'
fixture(project)
tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=project).decode().split('\0')
hashes = {name: hashlib.sha256((project / name).read_bytes()).hexdigest() for name in tracked if name}
save(out / 'input-file-hashes-before.json', hashes)
(out / 'Makefile.before').write_bytes((project / 'Makefile').read_bytes())
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip()
(out / 'project-head.txt').write_text(head + '\n')
print('CREATED', project)
print('PROJECT_HEAD', head)
print((project / 'Makefile').read_text())
print((project / 'main.c').read_text())
