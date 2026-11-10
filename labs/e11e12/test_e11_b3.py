"""Personal coverage for two-header repairs in variable-based declarations."""
import shutil
import tempfile
import unittest
from pathlib import Path

import pipeline  # Establish the existing lab import path for standalone discovery.
from lab import commit, fixture, patch, run, scan


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


class StudentE11B3(unittest.TestCase):
    def test_two_missing_headers_patch_macro_and_mixed_styles(self):
        for style in ('macro', 'mixed'):
            with self.subTest(style=style), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                project = root / 'project'
                fixture(project, style)
                main = project / 'main.c'
                main.write_text('#include "extra.h"\n' + main.read_text())
                target = commit(project, 'two missing local headers')
                status = run(['git', 'status', '--porcelain'], project)
                self.assertEqual(status, '')
                before = files(project)
                report = scan(project)
                self.assertEqual(report['commit'], target)
                self.assertEqual(
                    [(f['target'], f['dependency']) for f in report['findings']
                     if f['type'] == 'MISSING'],
                    [('main.o', 'config.h'), ('main.o', 'extra.h')])
                diff, plan = patch(project, report)
                self.assertEqual(plan, [
                    {'target': 'main.o', 'dependency': header, 'style': style}
                    for header in ('config.h', 'extra.h')])
                self.assertEqual(files(project), before)
                self.assertEqual(run(['git', 'status', '--porcelain'], project), status)
                candidate = root / 'candidate.patch'
                candidate.write_text(diff)
                run(['git', 'apply', '--check', str(candidate)], project)
                isolated = root / 'isolated'
                shutil.copytree(project, isolated)
                run(['git', 'apply', str(candidate)], isolated)
                original = before['Makefile']
                expected = original.replace(
                    b'DEPS = main.c unused.h' if style == 'macro'
                    else b'main.o: main.c $(HEADERS)',
                    b'DEPS = main.c unused.h config.h extra.h' if style == 'macro'
                    else b'main.o: main.c $(HEADERS) config.h extra.h')
                actual = (isolated / 'Makefile').read_bytes()
                self.assertEqual(actual, expected)
                recipes = lambda data: [line for line in data.splitlines(keepends=True)
                                        if line.startswith(b'\t')]
                self.assertEqual(recipes(actual), recipes(original))
                self.assertFalse(any(f['type'] == 'MISSING'
                                     for f in scan(isolated)['findings']))
                self.assertEqual(files(project), before)
                self.assertEqual(run(['git', 'status', '--porcelain'], project), status)


if __name__ == '__main__':
    unittest.main()
