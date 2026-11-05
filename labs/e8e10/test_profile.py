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

if __name__=='__main__':unittest.main()
