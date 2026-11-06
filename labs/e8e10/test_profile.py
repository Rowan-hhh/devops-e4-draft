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

class StudentE9B3(unittest.TestCase):
    def test_reports_bind_to_each_sample_head(self):
        from generate_e9_b3 import generate_reports, input_hashes
        from lab import run

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            samples_root = root / 'samples'
            samples_root.mkdir()
            samples = []
            for style in ('direct', 'macro', 'mixed'):
                project = samples_root / style
                fixture(project, style)
                samples.append({
                    'style': style,
                    'project_relative_path': style,
                    'project_commit': run(['git', 'rev-parse', 'HEAD'], project).strip(),
                    'input_sha256': input_hashes(project),
                })
            handoff = root / 'handoff.json'
            handoff.write_text(json.dumps({'stage': 'E9', 'samples': samples}))

            output = root / 'reports'
            result = generate_reports(handoff, output, samples_root=samples_root)

            self.assertTrue(result['passed'])
            self.assertTrue((output / 'commit-check.json').is_file())
            for sample in samples:
                report = json.loads((output / (sample['style'] + '-input.json')).read_text())
                self.assertEqual(report['commit'], sample['project_commit'])

class StudentE9B2(unittest.TestCase):
    def test_macro_duplicate_dependencies_are_normalized_before_patch(self):
        """Duplicate declarations do not change the target graph or patch style."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'macro'
            fixture(project, 'macro')
            makefile = project / 'Makefile'
            makefile.write_text(
                makefile.read_text().replace(
                    'DEPS = main.c unused.h',
                    'DEPS = main.c unused.h unused.h',
                )
            )
            report = scan(project)
            self.assertEqual(
                report['declared']['main.o'],
                ['main.c', 'unused.h'],
            )
            diff, plan = patch(project, report)
            self.assertEqual(
                plan,
                [{
                    'target': 'main.o',
                    'dependency': 'config.h',
                    'style': 'macro',
                }],
            )
            self.assertIn('config.h', diff)
            self.assertIn('DEPS = main.c unused.h unused.h config.h', diff)
            self.assertNotIn('config.h', makefile.read_text())

class StudentE9B4(unittest.TestCase):
    def test_three_style_patches_apply_only_to_isolated_copies(self):
        import shutil
        from lab import run

        expected = {
            'direct': b'main.o: main.c unused.h config.h',
            'macro': b'DEPS = main.c unused.h config.h',
            'mixed': b'main.o: main.c $(HEADERS) config.h',
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for style, declaration in expected.items():
                with self.subTest(style=style):
                    source = root / style
                    fixture(source, style)
                    before = (source / 'Makefile').read_bytes()
                    status = run(['git', 'status', '--porcelain', '--untracked-files=all'], source)
                    self.assertEqual(status, '')
                    report = scan(source)
                    self.assertEqual(report['commit'], run(['git', 'rev-parse', 'HEAD'], source).strip())
                    diff, plan = patch(source, report)
                    self.assertEqual(plan, [{'target': 'main.o', 'dependency': 'config.h', 'style': style}])
                    self.assertEqual((source / 'Makefile').read_bytes(), before)
                    self.assertEqual(run(['git', 'status', '--porcelain', '--untracked-files=all'], source), status)
                    candidate = root / (style + '.patch')
                    candidate.write_text(diff, encoding='utf-8')
                    run(['git', 'apply', '--check', str(candidate)], source)
                    self.assertEqual((source / 'Makefile').read_bytes(), before)
                    self.assertEqual(run(['git', 'status', '--porcelain', '--untracked-files=all'], source), status)
                    isolated = root / (style + '-isolated')
                    shutil.copytree(source, isolated)
                    run(['git', 'apply', '--check', str(candidate)], isolated)
                    run(['git', 'apply', str(candidate)], isolated)
                    after = (isolated / 'Makefile').read_bytes()
                    self.assertIn(declaration, after.splitlines())
                    recipes = lambda data: [line for line in data.splitlines(keepends=True) if line.startswith(b'\t')]
                    self.assertEqual(recipes(before), recipes(after))
                    self.assertEqual(scan(isolated)['findings'], [
                        {'type': 'REDUNDANT', 'target': 'main.o', 'dependency': 'unused.h'}
                    ])
                    self.assertEqual((source / 'Makefile').read_bytes(), before)
                    self.assertEqual(run(['git', 'status', '--porcelain', '--untracked-files=all'], source), status)

if __name__=='__main__':unittest.main()
