import json, tempfile, unittest
from pathlib import Path
from lab import fixture,scan,patch,commit

class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'sample';fixture(self.p)

    def test_independent_known_edges(self):
        r=scan(self.p)
        self.assertEqual(r['actual']['main.o'],['config.h','main.c'])
        self.assertEqual({(f['type'],f['dependency']) for f in r['findings']},{('MISSING','config.h'),('REDUNDANT','unused.h')})

    def test_unchanged_reuses_both_targets(self):
        r=scan(self.p,scan(self.p));self.assertEqual(r['reused'],['main.o','helper.o']);self.assertEqual(r['refreshed'],[])

    def test_include_added_invalidates_cache(self):
        old=scan(self.p)
        (self.p/'main.c').write_text('#include "extra.h"\n'+(self.p/'main.c').read_text());commit(self.p,'new include')
        r=scan(self.p,old)
        self.assertIn(['MISSING','main.o','extra.h'],r['added']);self.assertEqual(len(r['refreshed']),2)

    def test_patch_preserves_redundant_dependency(self):
        r=scan(self.p);diff,plan=patch(self.p,r)
        self.assertIn('+main.o: main.c unused.h config.h',diff)
        self.assertNotIn('-\tgcc',diff)
        self.assertNotIn('config.h',(self.p/'Makefile').read_text())

    def test_old_report_rejected(self):
        r=scan(self.p);r['commit']='0'*40
        with self.assertRaisesRegex(ValueError,'STALE_REPORT'):patch(self.p,r)

    def test_unsafe_dependency_rejected(self):
        r=scan(self.p);r['findings']=[{'type':'MISSING','target':'main.o','dependency':'../outside.h'}]
        with self.assertRaisesRegex(ValueError,'UNSAFE_PATH'):patch(self.p,r)

    def test_unsupported_configuration_rejected(self):
        (self.p/'Makefile').write_text((self.p/'Makefile').read_text().replace('-O0','-include unknown.h'))
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_FLAGS'):scan(self.p)

class StudentE9B1(unittest.TestCase):
    def test_three_pristine_styles_are_separately_versioned(self):
        from init_e9_b1 import initialize
        from lab import run
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'e9'
            result = initialize(out)
            self.assertEqual([s['style'] for s in result['samples']],
                             ['direct', 'macro', 'mixed'])
            expected = {
                'direct': 'main.o: main.c unused.h',
                'macro': 'main.o: $(DEPS)',
                'mixed': 'main.o: main.c $(HEADERS)',
            }
            for style, rule in expected.items():
                project = out / style
                self.assertTrue((project / '.git').is_dir())
                self.assertIn(rule, (project / 'Makefile').read_text().splitlines())
                self.assertEqual(run(['git', 'status', '--porcelain'], project), '')
                self.assertFalse((out / (style + '-input.json')).exists())
                self.assertFalse((out / (style + '.patch')).exists())
            self.assertNotEqual((out/'direct/Makefile').read_bytes(),
                                (out/'macro/Makefile').read_bytes())

    def test_existing_evidence_directory_is_not_overwritten(self):
        from init_e9_b1 import initialize
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            marker = out / 'keep.txt'
            marker.write_bytes(b'previous evidence')
            with self.assertRaises(FileExistsError):
                initialize(out)
            self.assertEqual(marker.read_bytes(), b'previous evidence')
            self.assertEqual(list(out.iterdir()), [marker])

class StudentE8B(unittest.TestCase):
    def test_patch_keeps_recipe_bytes(self):
        from lab import run
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "sample"
            fixture(project)
            before = (project / "Makefile").read_bytes()
            diff, plan = patch(project, scan(project))
            candidate = Path(directory) / "candidate.patch"
            candidate.write_text(diff, encoding="utf-8")
            run(["git", "apply", str(candidate.resolve())], project)
            after = (project / "Makefile").read_bytes()
            recipes = lambda data: [
                line for line in data.splitlines()
                if line.startswith(b"\t")
            ]
            self.assertEqual(recipes(before), recipes(after))
            self.assertIn(
                b"main.o: main.c unused.h config.h",
                after,
            )
            self.assertEqual(plan[0]["style"], "direct")

class StudentE8B3(unittest.TestCase):
    def test_report_identity_changes_even_when_findings_do_not(self):
        """Equal findings do not make reports from different commits interchangeable."""
        from lab import run
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'sample'
            fixture(project)
            first = scan(project)
            first_commit = run(['git', 'rev-parse', 'HEAD'], project).strip()
            self.assertEqual(first['commit'], first_commit)

            source = project / 'helper.c'
            source.write_text(source.read_text() + '/* B3: identity-only change */\n')
            second_commit = commit(project, 'B3: change source without dependency changes')
            second = json.loads(json.dumps(scan(project)))

            self.assertNotEqual(first_commit, second_commit)
            self.assertEqual(second['commit'], second_commit)
            self.assertEqual(first['commit'], first_commit)
            expected = {
                ('MISSING', 'main.o', 'config.h'),
                ('REDUNDANT', 'main.o', 'unused.h'),
            }
            for report in (first, second):
                self.assertEqual({
                    (item['type'], item['target'], item['dependency'])
                    for item in report['findings']
                }, expected)
            self.assertEqual(run(['git', 'status', '--porcelain'], project), '')

class StudentE8B4(unittest.TestCase):
    def test_stale_report_rejected_without_changing_source(self):
        from lab import run

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'sample'
            fixture(project)
            report = scan(project)
            report['commit'] = '0' * 40
            before = (project / 'Makefile').read_bytes()

            with self.assertRaisesRegex(ValueError, 'STALE_REPORT'):
                patch(project, report)

            self.assertEqual((project / 'Makefile').read_bytes(), before)
            self.assertEqual(run(['git', 'status', '--porcelain'], project), '')

if __name__=='__main__':unittest.main()
