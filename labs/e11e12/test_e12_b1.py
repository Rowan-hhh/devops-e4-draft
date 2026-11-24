"""Temporary projects and mocked DRAFT; never formal project evidence."""
import ast
import copy
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import b1
from vendor.draft import autobuild

FROM = 'FROM python:3.13-slim@sha256:' + 'a' * 64
BROKEN = FROM + '\nWORKDIR /work\nCOPY main.c helper.c *.h Makefile ./\nRUN make app\nCMD ["./app"]\n'
CANDIDATE = BROKEN.replace('RUN make app', b1.INSTALL + '\nRUN make app')


class CandidateContracts(unittest.TestCase):
    def test_deb822_rewrites_only_reviewed_hosts(self):
        argv = shlex.split(b1.INSTALL.removeprefix('RUN '))
        sed = argv[:argv.index('&&')]
        self.assertEqual(sed[:2], ['sed', '-i'])
        self.assertEqual(sed[-1], '/etc/apt/sources.list.d/debian.sources')
        self.assertEqual(sed[2:-1], [
            '-e', r's|https\{0,1\}://deb\.debian\.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g',
            '-e', r's|https\{0,1\}://security\.debian\.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g',
            '-e', r's|https\{0,1\}://deb\.debian\.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g'])
        hosts = [('deb.debian.org/debian-security', 'debian-security'),
                 ('security.debian.org/debian-security', 'debian-security'),
                 ('deb.debian.org/debian', 'debian')]
        original = ''.join('URIs: ' + scheme + '://' + host + '\n'
                           for host, _ in hosts for scheme in ('http', 'https'))
        expected = ''.join('URIs: https://mirrors.tuna.tsinghua.edu.cn/' + path + '\n'
                           for _, path in hosts for _ in ('http', 'https'))
        lookalike = 'URIs: https://debXdebianXorg/debian\n'
        # Exercise only sed on stdin: no apt, Docker, network or file writes.
        result = subprocess.run(['sed', *sed[2:-1]], input=original + lookalike,
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, expected + lookalike)

    def test_mirrored_candidate_exact(self):
        candidate = (b1.ROOT / 'reports/E12/B1/candidate.Dockerfile').read_text()
        broken_from = autobuild.instructions(candidate)[0]
        broken = BROKEN.replace(FROM, broken_from)
        b1.check_candidate(broken, candidate)
        self.assertEqual(autobuild.instructions(candidate),
                         autobuild.instructions(broken)[:3] + [b1.INSTALL]
                         + autobuild.instructions(broken)[3:])
        self.assertEqual(b1.INSTALL.count('Acquire::ForceIPv4=true'), 2)
        self.assertEqual(b1.INSTALL.count('Acquire::Retries=3'), 2)
        self.assertIn('/etc/apt/sources.list.d/debian.sources && ', b1.INSTALL)

    def test_old_official_source_candidate_rejected(self):
        old = ('RUN apt-get update && apt-get install -y --no-install-recommends '
               'gcc make libc6-dev && rm -rf /var/lib/apt/lists/*')
        with self.assertRaises(ValueError):
            b1.check_candidate(BROKEN, CANDIDATE.replace(b1.INSTALL, old))

    def test_other_mirror_and_source_file_rejected(self):
        for original, replacement in [
                ('mirrors.tuna.tsinghua.edu.cn', 'other.example.invalid'),
                ('/etc/apt/sources.list.d/debian.sources', '/etc/apt/sources.list')]:
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                b1.check_candidate(BROKEN, CANDIDATE.replace(original, replacement))

    def test_each_update_install_network_option_required(self):
        for option in ('-o Acquire::ForceIPv4=true ', '-o Acquire::Retries=3 '):
            for occurrence in (0, 1):
                parts = CANDIDATE.split(option)
                self.assertEqual(len(parts), 3)
                changed = (parts[0] + parts[1] + option + parts[2] if occurrence == 0
                           else parts[0] + option + parts[1] + parts[2])
                with self.subTest(option=option, occurrence=occurrence), self.assertRaises(ValueError):
                    b1.check_candidate(BROKEN, changed)

    def test_changed_packages_or_cleanup_rejected(self):
        for old, new in [('gcc make libc6-dev', 'gcc make'),
                         ('gcc make libc6-dev', 'gcc make libc6-dev curl'),
                         ('--no-install-recommends ', ''),
                         (' && rm -rf /var/lib/apt/lists/*', '')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                b1.check_candidate(BROKEN, CANDIDATE.replace(old, new))

    def test_extra_shell_commands_rejected(self):
        for command in ('echo 1', 'printf bad > main.c', 'touch app'):
            additions = ['RUN ' + command + ' && ' + b1.INSTALL.removeprefix('RUN '),
                         b1.INSTALL + ' && ' + command,
                         b1.INSTALL + '; ' + command]
            for addition in additions:
                with self.subTest(addition=addition), self.assertRaises(ValueError):
                    b1.check_candidate(BROKEN, CANDIDATE.replace(b1.INSTALL, addition))

    def test_same_pinned_from(self):
        self.assertEqual(autobuild.prepare_candidate(BROKEN, CANDIDATE), BROKEN)

    def test_old_unpinned_compatibility(self):
        self.assertEqual(autobuild.prepare_candidate(BROKEN.replace(FROM, FROM.split('@')[0]), CANDIDATE), BROKEN)

    def test_different_digest(self):
        with self.assertRaises(ValueError):
            autobuild.prepare_candidate(BROKEN, CANDIDATE.replace('a' * 64, 'b' * 64))

    def test_candidate_constraints(self):
        changes = [('python:3.13-slim', 'python:3.12-slim'),
                   ('a' * 64, 'b' * 64), ('COPY main.c', 'COPY other.c'),
                   ('RUN make app', 'RUN true'), ('CMD ["./app"]', 'CMD ["echo", "1"]')]
        invalid = [CANDIDATE.replace(a, z) for a, z in changes]
        invalid += [CANDIDATE + 'FROM other\n', CANDIDATE + 'RUN echo bad > main.c\n',
                    CANDIDATE.replace(b1.INSTALL, 'RUN echo 1'),
                    CANDIDATE.replace(b1.INSTALL + '\n', '') + b1.INSTALL + '\n']
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                b1.check_candidate(BROKEN, text)
        b1.check_candidate(BROKEN, CANDIDATE)


class B1Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'data/project/repo'
        fixture = self.root / 'fixtures/draft'
        shutil.copytree(b1.ROOT / 'fixtures/draft', fixture)
        self.init(self.root)
        self.commit(self.root, 'test outer fixture')
        outer = b1.git(self.root, 'rev-parse', 'HEAD').decode().strip()
        shutil.copytree(fixture, self.repo)
        self.init(self.repo)
        (self.repo / 'SOURCE.md').write_text('Test-only imported fixture\n')
        p0 = self.commit(self.repo, 'test import')
        (self.repo / 'main.c').write_text('int main(void){return 0;}\n')
        (self.repo / 'helper.c').write_text('int helper(void){return 0;}\n')
        (self.repo / 'config.h').write_text('#define VALUE 1\n')
        (self.repo / 'Dockerfile.broken').write_text(BROKEN)
        base = self.commit(self.repo, 'test base')
        (self.repo / 'output_format.h').write_text('#define OUTPUT_FORMAT "%d\\n"\n')
        target = self.commit(self.repo, 'test target')
        self.candidate = self.root / 'candidate.Dockerfile'
        self.candidate.write_text(CANDIDATE)
        bundle = self.root / 'project.bundle'
        b1.git(self.repo, 'bundle', 'create', str(bundle), '--all')
        self.source = {
            'project_type': 'e12-b-group-maintained', 'derived_from_stage': 'E7',
            'derived_from_path': 'fixtures/draft',
            'outer_repository_uri': 'https://github.com/Rowan-hhh/devops-e4-draft.git',
            'identity': b1.IDENTITY, 'a_group_report_received': False, 'server_draft_executed': False,
            'source_outer_commit': outer, 'source_e7_commit': outer,
            'source_fixture_introduced_commit': outer,
            'original_fixture_sha256': {p.name: b1.digest(p.read_bytes()) for p in fixture.iterdir()},
            'base': base, 'target': target, 'commits': {'P0': p0, 'P1': base, 'P2': target},
            'base_is_ancestor': True, 'project_files': b1.state(self.repo)['files'],
            'bundle': 'project.bundle', 'bundle_sha256': b1.digest(bundle.read_bytes()),
            'expected_stdout': '1\n', 'expected_stderr': '', 'expected_exit_code': 0}
        self.request = {'repo': 'data/project/repo', 'candidate': 'candidate.Dockerfile',
                        'source': 'source.json', 'candidate_provenance': 'candidate-provenance.json',
                        'base': base, 'target': target}
        b1.save(self.root / 'candidate-provenance.json', {
            'acquisition': 'manual', 'model_generated': False,
            'candidate_sha256': b1.digest(self.candidate.read_bytes())})
        self.write_source()

    def init(self, repo):
        b1.git(repo, 'init', '-b', 'main')
        for k, value in b1.IDENTITY.items():
            b1.git(repo, 'config', 'user.' + k, value)

    def commit(self, repo, message):
        b1.git(repo, 'add', '.')
        b1.git(repo, 'commit', '-m', message)
        return b1.git(repo, 'rev-parse', 'HEAD').decode().strip()

    def write_source(self):
        b1.save(self.root / 'source.json', self.source)

    def check(self):
        return b1.check_inputs(self.request, self.root)

    def test_valid_inputs(self):
        self.assertEqual(self.check()[3]['head'], self.request['target'])

    def test_sha_boundaries(self):
        for value in ['abc', 'A' * 40, '0' * 40, self.request['target']]:
            with self.subTest(value=value):
                self.request['base'] = value
                self.source['base'] = self.source['commits']['P1'] = value
                self.write_source()
                with self.assertRaises((ValueError, subprocess.SubprocessError)):
                    self.check()

    def test_non_ancestor(self):
        self.request['base'], self.request['target'] = self.request['target'], self.request['base']
        self.source.update(base=self.request['base'], target=self.request['target'])
        self.source['commits'].update(P1=self.request['base'], P2=self.request['target'])
        self.write_source()
        with self.assertRaises(subprocess.SubprocessError):
            self.check()

    def test_shallow(self):
        (self.repo / '.git/shallow').write_text(self.request['target'] + '\n')
        with self.assertRaisesRegex(ValueError, 'Shallow'):
            self.check()

    def test_required_source_fields(self):
        original = copy.deepcopy(self.source)
        for key in original:
            self.source = copy.deepcopy(original)
            del self.source[key]
            self.write_source()
            with self.subTest(key=key), self.assertRaises((KeyError, ValueError)):
                self.check()

    def test_wrong_provenance(self):
        for field, value in [('project_type', 'external-production-project'),
                             ('derived_from_stage', 'E11'), ('derived_from_path', 'integration-sample'),
                             ('original_fixture_sha256', {}), ('project_files', {}),
                             ('identity', {'name': 'TeachingFixture', 'email': 'fixture@localhost'}),
                             ('bundle_sha256', '0' * 64)]:
            with self.subTest(field=field):
                old = self.source[field]
                self.source[field] = value
                self.write_source()
                with self.assertRaises(ValueError):
                    self.check()
                self.source[field] = old

    def test_local_identity(self):
        b1.git(self.repo, 'config', 'user.name', 'Other')
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.check()

    def test_commit_identity(self):
        b1.git(self.repo, 'config', 'user.name', 'Other')
        (self.repo / 'test-only.txt').write_text('test\n')
        target = self.commit(self.repo, 'test wrong author')
        b1.git(self.repo, 'config', 'user.name', b1.IDENTITY['name'])
        self.request['target'] = self.source['target'] = self.source['commits']['P2'] = target
        self.write_source()
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.check()

    def test_dirty_and_wrong_head(self):
        extra = self.repo / 'untracked.txt'
        extra.write_text('test\n')
        with self.assertRaisesRegex(ValueError, 'Dirty'):
            self.check()
        extra.unlink()
        b1.git(self.repo, 'checkout', '--detach', self.request['base'])
        with self.assertRaisesRegex(ValueError, 'HEAD'):
            self.check()

    def test_existing_outputs(self):
        out = self.root / 'out'
        out.mkdir()
        for nonempty in (False, True):
            if nonempty:
                (out / 'keep').write_text('keep\n')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                b1.run(self.request, out, self.root)
        link = self.root / 'link'
        link.symlink_to(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            b1.run(self.request, link, self.root)

    def test_output_inside_source(self):
        with self.assertRaisesRegex(ValueError, 'outside project'):
            b1.run(self.request, self.repo / 'out', self.root)
        self.assertFalse((self.repo / 'out').exists())

    def fake_draft(self, project, candidate, out, expected, **kwargs):
        out.mkdir()
        (out / 'verify-stderr.log').write_text('')
        result = {'status': 'SUCCEEDED', 'attempts': [
            {'build_exit_code': 1, 'failure_class': 'MISSING_MAKE'},
            {'build_exit_code': 0, 'image_id': 'sha256:' + '1' * 64}],
            'verification': {'exit_code': 0, 'actual_output': '1\n', 'output_matches': True}}
        b1.save(out / 'result.json', result)
        return result

    def test_mock_success_and_invariance(self):
        before = b1.state(self.repo)
        out = self.root / 'out'
        with patch.object(b1, 'auto_build', side_effect=self.fake_draft):
            result = b1.run(self.request, out, self.root)
        self.assertEqual(result['status'], 'SUCCEEDED')
        self.assertTrue(result['source_unchanged'])
        self.assertEqual(before, b1.state(self.repo))
        self.assertFalse(any(p.name in b1.FORBIDDEN for p in out.rglob('*')))

    def test_mock_failures(self):
        scenarios = [{'status': 'FAILED'}, {'status': 'TIMED_OUT'},
                     TimeoutError('test timeout'), RuntimeError('test exception'),
                     {'status': 'SUCCEEDED', 'attempts': []}]
        for number, scenario in enumerate(scenarios):
            kwargs = {'side_effect': scenario} if isinstance(scenario, Exception) else {'return_value': scenario}
            with self.subTest(scenario=scenario), patch.object(b1, 'auto_build', **kwargs):
                out = self.root / ('out-' + str(number))
                result = b1.run(self.request, out, self.root)
                self.assertNotEqual(result['status'], 'SUCCEEDED')
                self.assertTrue(result['source_unchanged'])
                self.assertFalse(any(p.name in b1.FORBIDDEN for p in out.rglob('*')))

    def test_source_change_cannot_succeed(self):
        def changed(*args, **kwargs):
            (self.repo / 'main.c').write_text('changed\n')
            return self.fake_draft(*args, **kwargs)
        with patch.object(b1, 'auto_build', side_effect=changed):
            result = b1.run(self.request, self.root / 'out', self.root)
        self.assertEqual(result['status'], 'FAILED')
        self.assertFalse(result['source_unchanged'])

    def assert_setup_failure(self, phase, changed_field=None, failure=None):
        """Inject only temporary-output faults, and count both real state reads."""
        out = self.root / ('fault-' + phase + '-' + str(changed_field))
        failure = failure if failure is not None else OSError('test ' + phase + ' failure')
        real_state, real_save, real_mkdir = b1.state, b1.save, Path.mkdir
        reads = []

        def read_state(repo):
            snapshot = real_state(repo)
            reads.append(copy.deepcopy(snapshot))
            if len(reads) == 2 and changed_field is not None:
                snapshot = copy.deepcopy(snapshot)
                if changed_field == 'files':
                    snapshot['files']['main.c'] = '0' * 64
                else:
                    snapshot[changed_field] += 'test change'
            return snapshot

        def mkdir(path, *args, **kwargs):
            if phase == 'mkdir' and path == out:
                raise failure
            return real_mkdir(path, *args, **kwargs)

        def write(path, value):
            if path.name == phase + '.json':
                raise failure
            # A second evidence error must not hide the primary error or prevent
            # the already completed in-memory invariance decision.
            if path.name == 'source-after.json':
                raise OSError('test post-state evidence failure')
            return real_save(path, value)

        with patch.object(b1, 'state', side_effect=read_state) as state_mock, \
                patch.object(Path, 'mkdir', autospec=True, side_effect=mkdir), \
                patch.object(b1, 'save', side_effect=write), \
                patch.object(b1, 'auto_build') as draft:
            if changed_field is not None and isinstance(failure, Exception):
                with self.assertRaisesRegex(ValueError, 'Original project changed') as caught:
                    b1.run(self.request, out, self.root)
                self.assertIs(caught.exception.__cause__, failure)
            else:
                with self.assertRaises(type(failure)) as caught:
                    b1.run(self.request, out, self.root)
                self.assertIs(caught.exception, failure)
                if changed_field is not None:
                    self.assertIn('Original project changed', caught.exception.__notes__)
            self.assertEqual(state_mock.call_count, 2)
            self.assertEqual(reads[0], reads[1])  # The actual test project was not modified.
            self.assertEqual(draft.call_count, 0)
        records = [json.loads(p.read_text()) for p in out.rglob('*.json')] if out.exists() else []
        self.assertFalse(any(r.get('status') == 'SUCCEEDED' for r in records))
        if phase == 'mkdir':
            self.assertFalse(out.exists())
        else:
            result = json.loads((out / 'result.json').read_text())
            self.assertEqual(result['status'], 'FAILED')
            self.assertEqual(result['source_unchanged'], changed_field is None)
        return {'phase': phase, 'before_state_calls': 1, 'after_state_calls': 1,
                'draft_calls': 0, 'original_exception_preserved': changed_field is None,
                'success_records': 0}

    def test_mkdir_failure_rechecks_and_preserves_exception(self):
        self.assert_setup_failure('mkdir')

    def test_request_write_failure_rechecks_and_preserves_exception(self):
        self.assert_setup_failure('request')

    def test_source_before_write_failure_rechecks_and_preserves_exception(self):
        self.assert_setup_failure('source-before')

    def test_setup_failures_report_each_invariance_change(self):
        for phase in ('mkdir', 'request', 'source-before'):
            for field in ('files', 'head', 'refs', 'status'):
                with self.subTest(phase=phase, field=field):
                    self.assert_setup_failure(phase, field)

    def test_setup_failure_does_not_swallow_baseexceptions(self):
        for phase in ('mkdir', 'request', 'source-before'):
            for kind in (KeyboardInterrupt, SystemExit):
                for field in (None, 'head'):
                    with self.subTest(phase=phase, kind=kind, changed=field):
                        self.assert_setup_failure(phase, field, kind('test interrupt'))
                        # Each iteration needs its own previously nonexistent output.
                        # TemporaryDirectory cleanup owns these test-only files.
                        if phase != 'mkdir':
                            shutil.rmtree(self.root / ('fault-' + phase + '-' + str(field)))

    def test_post_state_write_failure_keeps_in_memory_verdict(self):
        out = self.root / 'post-write-fault'
        real_save = b1.save

        def write(path, value):
            if path.name == 'source-after.json':
                raise PermissionError('test after write failure')
            return real_save(path, value)

        with patch.object(b1, 'state', wraps=b1.state) as states, \
                patch.object(b1, 'save', side_effect=write), \
                patch.object(b1, 'auto_build', side_effect=self.fake_draft):
            with self.assertRaisesRegex(PermissionError, 'test after write failure'):
                b1.run(self.request, out, self.root)
            self.assertEqual(states.call_count, 2)
        result = json.loads((out / 'result.json').read_text())
        self.assertTrue(result['source_unchanged'])
        self.assertEqual(result['status'], 'FAILED')

    def test_final_result_write_failure_is_not_success(self):
        out = self.root / 'result-write-fault'
        real_save = b1.save

        def write(path, value):
            if path == out / 'result.json':
                raise OSError('test result write failure')
            return real_save(path, value)

        with patch.object(b1, 'state', wraps=b1.state) as states, \
                patch.object(b1, 'save', side_effect=write), \
                patch.object(b1, 'auto_build', side_effect=self.fake_draft):
            with self.assertRaisesRegex(OSError, 'test result write failure'):
                b1.run(self.request, out, self.root)
            self.assertEqual(states.call_count, 2)
        self.assertFalse((out / 'result.json').exists())
        self.assertEqual(json.loads((out / 'source-after.json').read_text()), b1.state(self.repo))

    def test_bundle_restore(self):
        restored = self.root / 'restored'
        b1.git(self.root, 'clone', str(self.root / 'project.bundle'), str(restored))
        self.assertEqual(b1.git(restored, 'rev-parse', 'HEAD').decode().strip(), self.request['target'])
        for revision in (self.request['base'], self.request['target']):
            self.assertEqual(b1.git(restored, 'show', '-s', '--format=%an <%ae>', revision).decode().strip(),
                             '241880360 <241880360@smail.nju.edu.cn>')

    def test_no_downstream_imports(self):
        tree = ast.parse(Path(b1.__file__).read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        self.assertFalse(set(imports) & {'pipeline', 'lab', 'server', 'buildchecker.fullcheck'})


if __name__ == '__main__':
    unittest.main()
