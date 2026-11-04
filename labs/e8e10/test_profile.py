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

if __name__=='__main__':unittest.main()
