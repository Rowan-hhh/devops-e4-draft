import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('e14_b1', Path(__file__).resolve().parents[1] / 'e14_b1.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL).decode().strip()


class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(); self.repo = self.root / 'data/sample/repo'; self.repo.mkdir(parents=True)
        git(self.repo, 'init', '-q'); git(self.repo, 'config', 'user.name', 'test'); git(self.repo, 'config', 'user.email', 'test@example.invalid')
        (self.repo / 'file').write_text('a'); git(self.repo, 'add', '.'); git(self.repo, 'commit', '-qm', 'base'); self.base = git(self.repo, 'rev-parse', 'HEAD')
        (self.repo / 'file').write_text('b'); git(self.repo, 'commit', '-qam', 'target'); self.target = git(self.repo, 'rev-parse', 'HEAD')
        self.candidate = self.root / 'data/sample/Dockerfile'; self.candidate.write_text('FROM python:3.13@sha256:' + 'a'*64 + '\n')
        (self.root / 'data/sample/fixed.json').write_text('{}')
        self.req = {'mode':'e12', 'repo':'/course/data/sample/repo', 'base':self.base, 'target':self.target, 'candidate':'/course/data/sample/Dockerfile', 'fixed_report':'/course/data/sample/fixed.json', 'expected_output':'1', 'build_timeout':600}
        self.request = self.root / 'data/sample/request.json'; dump(self.request, self.req)
        self.info = m.inspect_request(self.request, self.root); self.out = self.root / 'work/evidence'; self.run = self.out / 'run'

    def test_request_and_git_contract(self):
        self.assertEqual(self.info['repo'], str(self.repo))
        for changes in ({'base':'abcd'}, {'base':'0'*40}, {'base':self.target,'target':self.base}, {'repo':'/course/data/../escape'}, {'candidate':'/course/data/sample/nope'}, {'mode':'e11-b'}):
            with self.subTest(changes=changes):
                dump(self.request, self.req | changes)
                with self.assertRaises((ValueError, subprocess.SubprocessError)): m.inspect_request(self.request, self.root)
        dump(self.request, {k:v for k,v in self.req.items() if k != 'candidate'})
        with self.assertRaises(ValueError): m.inspect_request(self.request, self.root)

    def test_symlink_and_floating_dockerfile(self):
        link = self.root / 'data/link'; link.symlink_to(self.repo, target_is_directory=True)
        dump(self.request, self.req | {'repo':'/course/data/link'})
        with self.assertRaises(ValueError): m.inspect_request(self.request, self.root)
        dump(self.request, self.req)
        for value in ('FROM python:latest\n', 'FROM python:latest@sha256:' + 'a'*64 + '\n'):
            self.candidate.write_text(value)
            with self.assertRaises(ValueError): m.inspect_request(self.request, self.root)

    def test_snapshot_boundaries(self):
        a = m.snapshot(self.info, self.out, self.run, True); b = copy.deepcopy(a)
        m.compare_snapshots(a, b, self.info, self.out, self.run)
        for key, value in [('head', 'f'*40), ('status_base64', 'eA=='), ('canonical_repo_path', '/wrong'), ('request_sha256','f'*64), ('candidate_sha256','f'*64)]:
            c = copy.deepcopy(b); c[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): m.compare_snapshots(a, c, self.info, self.out, self.run)
        for key, value in [('git_mode','100755'), ('bytes',42), ('sha256','f'*64), ('path','../escape')]:
            c = copy.deepcopy(b); c['tracked_files'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): m.compare_snapshots(a, c, self.info, self.out, self.run)
        c = copy.deepcopy(b); c['tracked_files'].append(c['tracked_files'][0])
        with self.assertRaises(ValueError): m.compare_snapshots(a, c, self.info, self.out, self.run)
        (self.repo / 'file').write_text('changed')
        with self.assertRaises(ValueError): m.snapshot(self.info, self.out, self.run, True)

    def test_tracked_symlink_rejected(self):
        (self.repo / 'link').symlink_to('file'); git(self.repo, 'add', 'link'); git(self.repo, 'commit', '-qm', 'link')
        with self.assertRaises(ValueError): m.snapshot(self.info, self.out, self.run, True)

    def test_exception_records_after(self):
        def fail(*args, **kwargs): raise RuntimeError('synthetic')
        with self.assertRaises(RuntimeError): m.single_run(self.request, self.out, self.root, fail)
        self.assertTrue((self.out / 'source-after.json').is_file()); self.assertTrue((self.out / 'failure.json').is_file())
        with self.assertRaises(ValueError): m.single_run(self.request, self.out, self.root, fail)

    def make_run(self):
        self.run.mkdir(parents=True); (self.out / 'request.json').write_bytes(self.request.read_bytes()); dump(self.run / 'request.json', self.req)
        snap = m.snapshot(self.info, self.out, self.run, True); dump(self.out / 'source-before.json', snap); dump(self.out / 'source-after.json', snap)
        (self.out / 'console.log').write_text('ok'); (self.out / 'exit-code.txt').write_text('0\n')
        job='job-test'; trace='trace-test'
        def art(path):
            data=(self.run/path).read_bytes(); return {'uri':'artifact://'+job+'/'+path, 'bytes':len(data), 'sha256':m.digest(data)}
        (self.run/'candidate.patch').write_text('patch')
        (self.run/'draft-build').mkdir(exist_ok=True); (self.run/'draft-build/verify.log').write_bytes(b'1\n')
        val={'accepted':True, 'checks':dict.fromkeys(('patch_applies','build','test','header_change','no_missing'), True), 'source_unchanged':False}; dump(self.run/'validation/validation.json', val)
        entries=[]
        for name in m.STAGES:
            data={}
            if name == 'draft':
                data={'candidate_sha256':self.info['candidate_sha256'], 'verification':{'exit_code':0, 'expected_output':'1', 'actual_output':'1\n', 'output_matches':True}}
                dump(self.run/'draft-build/result.json',data)
            if name == 'incremental-check': data={'commit':self.target}
            if name == 'repair': data={'input_report':art('incremental-check.json')}
            if name == 'recheck': data={'validation':val, 'findings':[]}
            stage={'schema_version':'e11e12-1','kind':name,'status':'SUCCEEDED','job_id':job,'trace_id':trace,'commit':self.base if name == 'full-check' else self.target,'data':data,'artifacts':([art('candidate.patch')] if name == 'repair' else [art('validation/validation.json')] if name == 'recheck' else [])}
            dump(self.run/(name+'.json'),stage); entries.append({'name':name,'artifact':art(name+'.json')})
        names=[x.name for x in self.run.glob('*.json') if x.name != 'result.json']+['candidate.patch','validation/validation.json','draft-build/verify.log','draft-build/result.json']
        result={'schema_version':'e11e12-1','status':'SUCCEEDED','job_id':job,'trace_id':trace,'base_commit':self.base,'target_commit':self.target,'stages':entries,'artifacts':[art(n) for n in names]}
        dump(self.run/'result.json',result)
        return result

    def seal(self):
        if not (self.out/'sealed-inputs').exists():
            m.seal_inputs(self.out, self.info, json.loads((self.out/'source-before.json').read_text()), self.root)
        dump(self.out/'execution.json', {'run_return_code':0})
        manifest = m.seal_run(self.out); m.finish_manifest(self.out, manifest)

    def test_success_and_missing_snapshots(self):
        self.make_run(); self.seal(); self.assertEqual(m.verify_run(self.out,self.root)['status'], 'VERIFIED')
        (self.out/'source-after.json').unlink()
        with self.assertRaises(OSError): m.verify_run(self.out,self.root)

    def test_stage_and_artifact_failures(self):
        original=self.make_run()
        for mutate in (lambda r:r['stages'].pop(), lambda r:r['stages'].reverse(), lambda r:r['stages'].append(r['stages'][0]), lambda r:r['artifacts'].append(r['artifacts'][0]), lambda r:r['artifacts'][0].update(bytes=999), lambda r:r['artifacts'][0].update(sha256='0'*64), lambda r:r['artifacts'][0].update(uri='artifact://job-test/../escape')):
            r=copy.deepcopy(original); mutate(r); dump(self.run/'result.json',r)
            with self.subTest(result=r), self.assertRaises((ValueError, OSError)):
                self.seal(); m.verify_run(self.out, self.root)
            import shutil
            shutil.rmtree(self.out/'sealed-run', ignore_errors=True)
            (self.out/'execution.json').unlink(missing_ok=True)

    def test_stage_content_tampering(self):
        original = self.make_run()
        def refresh(name):
            data = (self.run / (name + '.json')).read_bytes()
            for ref in [next(x['artifact'] for x in original['stages'] if x['name'] == name), next(x for x in original['artifacts'] if x['uri'].endswith('/' + name + '.json'))]:
                ref.update(bytes=len(data), sha256=m.digest(data))
            dump(self.run / 'result.json', original)
        for name, change in [
            ('draft', lambda x: x.update(trace_id='wrong')),
            ('draft', lambda x: x['data']['verification'].update(actual_output='wrong')),
            ('draft', lambda x: x['data']['verification'].update(exit_code=1)),
            ('incremental-check', lambda x: x['data'].update(commit='f'*40)),
            ('repair', lambda x: x['data']['input_report'].update(sha256='f'*64)),
            ('recheck', lambda x: x['data'].update(findings=[{'type':'MISSING'}])),
            ('recheck', lambda x: x['data']['validation'].update(accepted=False))]:
            path = self.run / (name + '.json'); saved = path.read_bytes(); old = copy.deepcopy(original)
            stage = json.loads(saved); change(stage); dump(path, stage); refresh(name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.seal(); m.verify_run(self.out, self.root)
            import shutil
            shutil.rmtree(self.out/'sealed-run', ignore_errors=True)
            (self.out/'execution.json').unlink(missing_ok=True)
            path.write_bytes(saved); original = old; dump(self.run/'result.json', original)

    def test_baseline_validation(self):
        from unittest.mock import patch
        base = self.base; delivery = self.target
        folder = self.repo / 'reports/E13/B4'; folder.mkdir(parents=True)
        cases = {f'C{i}':'PASS' for i in range(1,9)}
        projects = dict.fromkeys(('H1-jsmn','H2-inih','H3-tiny-AES'),'PASS')
        h = {'status':'PASS','gate':'E13_PASS','c1_c8':cases,'teacher_projects':projects,'a_group_receipt':{'status':'ACCEPTED','scope':['C4','C7']}}
        result = {'status':'PASS','cases':cases,'teacher_projects':projects,'a_group_receipt':'ACCEPTED'}
        dump(folder/'handoff.json', h); dump(folder/'result.json', result); (folder/'README.md').write_text('签收')
        git(self.repo, 'add', '.'); git(self.repo, 'commit', '-qm', 'gate'); head = git(self.repo,'rev-parse','HEAD')
        with patch.object(m,'BASELINE',head), patch.object(m,'B4',delivery):
            self.assertEqual(m.preflight(self.repo)['status'], 'E13_GATE_BASELINE')
        with patch.object(m,'BASELINE',base), patch.object(m,'B4',delivery), self.assertRaises(ValueError): m.preflight(self.repo)
        with patch.object(m,'BASELINE','bad'), patch.object(m,'B4',delivery), self.assertRaises(ValueError): m.preflight(self.repo)
        (folder/'handoff.json').unlink()
        with patch.object(m,'BASELINE',head), patch.object(m,'B4',delivery), self.assertRaises(ValueError): m.preflight(self.repo)

    def test_gate_and_receipt_rejections(self):
        from unittest.mock import patch
        folder = self.repo / 'reports/E13/B4'; folder.mkdir(parents=True)
        projects = dict.fromkeys(('H1-jsmn','H2-inih','H3-tiny-AES'), 'PASS')
        cases = {f'C{i}':'PASS' for i in range(1,9)}
        h = {'status':'PASS','gate':'E13_PASS','c1_c8':cases,'teacher_projects':projects,'a_group_receipt':{'status':'ACCEPTED','scope':['C4','C7']}}
        result = {'status':'PASS','cases':cases,'teacher_projects':projects,'a_group_receipt':'ACCEPTED'}
        for n, change in enumerate((lambda x:x['c1_c8'].pop('C1'), lambda x:x['teacher_projects'].update({'H1-jsmn':'FAIL'}), lambda x:x['a_group_receipt'].update(scope=['C4']))):
            item = copy.deepcopy(h); change(item)
            dump(folder/'handoff.json', item); dump(folder/'result.json', result); (folder/'README.md').write_text('签收')
            git(self.repo,'add','.'); git(self.repo,'commit','-qm',f'gate {n}'); head = git(self.repo,'rev-parse','HEAD')
            with patch.object(m,'BASELINE',head), patch.object(m,'B4',self.base), self.assertRaises(ValueError): m.preflight(self.repo)

    def test_source_membership_and_bindings(self):
        before = m.snapshot(self.info, self.out, self.run, True)
        for transform in (lambda a:a['tracked_files'].clear(), lambda a:a['tracked_files'].append(dict(a['tracked_files'][0], path='new')), lambda a:a.update(status_base64='eA==')):
            after = copy.deepcopy(before); transform(after)
            with self.assertRaises(ValueError): m.compare_snapshots(before, after, self.info, self.out, self.run)
        self.candidate.write_text(self.candidate.read_text() + '# changed\n')
        after = m.snapshot(self.info, self.out, self.run)
        with self.assertRaises(ValueError): m.compare_snapshots(before, after, self.info, self.out, self.run)

    def test_validation_and_missing_artifacts(self):
        result = self.make_run()
        (self.run/'candidate.patch').unlink()
        with self.assertRaises(ValueError): m.seal_run(self.out)
        import shutil
        shutil.rmtree(self.out/'sealed-run', ignore_errors=True)
        (self.run/'candidate.patch').write_text('patch')
        (self.run/'draft-build').mkdir(exist_ok=True); (self.run/'draft-build/verify.log').write_bytes(b'1\n')
        (self.run/'validation/validation.json').unlink()
        with self.assertRaises(ValueError): m.seal_run(self.out)
        shutil.rmtree(self.out/'sealed-run', ignore_errors=True)
        result['artifacts'][0]['uri'] = 'artifact://job-test/nonexistent'
        dump(self.run/'result.json', result)
        with self.assertRaises(ValueError): m.seal_run(self.out)

    def test_sealed_evidence_isolated(self):
        self.make_run(); self.seal()
        self.assertTrue((self.out/'sealed-run/result.json').is_file())
        (self.run/'draft-build/verify.log').write_text('later')
        self.assertEqual(m.verify_run(self.out,self.root)['status'], 'VERIFIED')
        (self.out/'sealed-run/files/draft-build/verify.log').write_text('tampered')
        with self.assertRaises(ValueError): m.verify_run(self.out,self.root)

    def test_seal_rejects_changed_or_linked_artifact(self):
        self.make_run(); (self.run/'candidate.patch').write_text('changed')
        with self.assertRaises(ValueError): m.seal_run(self.out)
        import shutil
        shutil.rmtree(self.out/'sealed-run')
        (self.run/'candidate.patch').unlink(); (self.run/'candidate.patch').symlink_to(self.repo/'file')
        with self.assertRaises(ValueError): m.seal_run(self.out)

    def test_snapshot_special_names_and_deleted_files(self):
        name = '空 格\nname'; (self.repo/name).write_text('bytes')
        git(self.repo,'add',name); git(self.repo,'commit','-qm','special')
        snap=m.snapshot(self.info,self.out,self.run,True)
        self.assertIn(name,[x['path'] for x in snap['tracked_files']])
        (self.repo/name).unlink()
        with self.assertRaises((ValueError,OSError)): m.snapshot(self.info,self.out,self.run,True)

    def test_input_symlinks_and_output_escape(self):
        link=self.root/'data/sample/link.json'; link.symlink_to(self.request)
        with self.assertRaises(ValueError): m.inspect_request(link,self.root)
        with self.assertRaises(ValueError): m.single_run(self.request,self.root/'outside',self.root)
        (self.root/'work').mkdir(exist_ok=True); (self.root/'work/link').symlink_to(self.root/'data',target_is_directory=True)
        with self.assertRaises(ValueError): m.single_run(self.request,self.root/'work/link/new',self.root)

    def test_double_failure_preserves_original(self):
        from unittest.mock import patch
        original_snapshot=m.snapshot
        count=[0]
        def snap(*args, **kwargs):
            count[0]+=1
            if count[0] > 1: raise RuntimeError('after failed')
            return original_snapshot(*args, **kwargs)
        def fail(*args, **kwargs): raise RuntimeError('run failed')
        with patch.object(m,'snapshot',side_effect=snap), self.assertRaisesRegex(RuntimeError,'run failed'):
            m.single_run(self.request,self.out,self.root,fail)
        failure=json.loads((self.out/'failure.json').read_text())
        self.assertEqual(failure['run_exception']['message'],'run failed')
        self.assertEqual(failure['source_after_exception']['message'],'after failed')
        self.assertIsNotNone(failure['sealing_exception'])
        self.assertIn('Traceback',failure['run_exception']['traceback'])

    def test_nonzero_and_saved_request(self):
        class Response:
            returncode=7
            stdout=b'failed'
        def runner(argv, **kwargs):
            self.assertEqual(Path(argv[argv.index('--request')+1]), (self.out/'request.json').relative_to(self.root))
            self.request.write_text('changed after copy')
            return Response()
        with self.assertRaisesRegex(RuntimeError,'exited 7'):
            m.single_run(self.request,self.out,self.root,runner)
        failure=json.loads((self.out/'failure.json').read_text())
        self.assertEqual(failure['run_return_code'],7)
        self.assertEqual(json.loads((self.out/'request.json').read_text()),self.req)

    def test_both_snapshots_forged_rejected(self):
        snap=m.snapshot(self.info,self.out,self.run,True)
        forged=copy.deepcopy(snap); forged['tracked_files'][0]['sha256']='f'*64
        with self.assertRaises(ValueError): m.compare_snapshots(forged,forged,self.info,self.out,self.run)

    def test_submodule_rejected(self):
        git(self.repo, 'update-index', '--add', '--cacheinfo', '160000,' + self.base + ',nested')
        with self.assertRaises(ValueError): m.snapshot(self.info,self.out,self.run)

    def test_missing_before_and_evidence_symlink(self):
        self.make_run(); self.seal()
        link=self.root/'work/link'; link.symlink_to(self.out,target_is_directory=True)
        with self.assertRaises(ValueError): m.verify_run(link,self.root)
        (self.out/'source-before.json').unlink()
        with self.assertRaises(OSError): m.verify_run(self.out,self.root)

    def test_stdout_in_seal_must_match_stage(self):
        self.make_run()
        log=self.run/'draft-build/verify.log'; log.write_text('different\n')
        result=json.loads((self.run/'result.json').read_text())
        entry=next(x for x in result['artifacts'] if x['uri'].endswith('/draft-build/verify.log'))
        entry.update(m.file_info(log)); dump(self.run/'result.json',result)
        self.seal()
        with self.assertRaises(ValueError): m.verify_run(self.out,self.root)

    def test_failure_record_error_does_not_replace_primary(self):
        from unittest.mock import patch
        original=m.write_new
        def write(path, value):
            if Path(path).name == 'failure.json': raise OSError('record failed')
            return original(path,value)
        def fail(*args,**kwargs): raise RuntimeError('primary failure')
        with patch.object(m,'write_new',side_effect=write), self.assertRaisesRegex(RuntimeError,'primary failure'):
            m.single_run(self.request,self.out,self.root,fail)
        self.assertTrue((self.out/'source-after.json').exists())

    def test_seal_failure_becomes_primary(self):
        class Result: returncode=0; stdout=b'ok'
        with self.assertRaises((ValueError,OSError)):
            m.single_run(self.request,self.out,self.root,lambda *a,**k:Result())
        result=json.loads((self.out/'failure.json').read_text())
        self.assertIsNone(result['run_exception']); self.assertIsNotNone(result['sealing_exception'])
        self.assertTrue((self.out/'source-after.json').exists())

    def test_baseexception_propagates_and_after_is_saved(self):
        def fail(*args, **kwargs): raise KeyboardInterrupt('interrupt')
        with self.assertRaises(KeyboardInterrupt): m.single_run(self.request,self.out,self.root,fail)
        self.assertTrue((self.out/'source-after.json').exists())
        failure=json.loads((self.out/'failure.json').read_text())
        self.assertEqual(failure['run_exception']['type'],'KeyboardInterrupt')

    def test_non_utf8_verification_output(self):
        self.make_run()
        log=self.run/'draft-build/verify.log'; log.write_bytes(b'\xff')
        result=json.loads((self.run/'result.json').read_text())
        item=next(x for x in result['artifacts'] if x['uri'].endswith('/draft-build/verify.log'))
        item.update(m.file_info(log)); dump(self.run/'result.json',result); self.seal()
        with self.assertRaises(UnicodeDecodeError): m.verify_run(self.out,self.root)

    def test_source_snapshot_after_only_failure(self):
        from unittest.mock import patch
        original=m.snapshot; count=[0]
        def snapshot(*args,**kwargs):
            count[0]+=1
            if count[0] > 1: raise RuntimeError('after-only failure')
            return original(*args,**kwargs)
        class Response: returncode=0; stdout=b'ok'
        with patch.object(m,'snapshot',side_effect=snapshot), self.assertRaises((RuntimeError,OSError,ValueError)):
            m.single_run(self.request,self.out,self.root,lambda *a,**k:Response())
        data=json.loads((self.out/'failure.json').read_text())
        self.assertEqual(data['source_after_exception']['message'],'after-only failure')

    def test_job_identity_mismatch(self):
        self.make_run()
        stage_path=self.run/'draft.json'; stage=json.loads(stage_path.read_text()); stage['job_id']='job-other'; dump(stage_path,stage)
        result=json.loads((self.run/'result.json').read_text())
        for item in [result['stages'][0]['artifact'],next(x for x in result['artifacts'] if x['uri'].endswith('/draft.json'))]: item.update(m.file_info(stage_path))
        dump(self.run/'result.json',result); self.seal()
        with self.assertRaises(ValueError): m.verify_run(self.out,self.root)

    def test_parent_request_and_handoff_symlinks(self):
        parent=self.root/'data/linked'; parent.symlink_to(self.root/'data/sample',target_is_directory=True)
        with self.assertRaises(ValueError): m.inspect_request(parent/'request.json',self.root)
        (self.root/'work').mkdir(exist_ok=True)
        link=self.root/'work/handoff.json'; link.symlink_to(self.request)
        with self.assertRaises(ValueError): m.handoff(link,self.root)

    def test_offline_migration_and_input_tampering(self):
        import shutil
        self.make_run(); self.seal()
        moved=self.root/'relocated'; shutil.move(str(self.out), moved)
        shutil.rmtree(self.repo); self.candidate.unlink()
        self.assertEqual(m.verify_run(moved,self.root)['status'],'VERIFIED')
        for name in ('source.bundle','candidate.Dockerfile','request.json','fixed-report.json'):
            file=moved/'sealed-inputs'/name; original=file.read_bytes(); file.write_bytes(original+b'X')
            with self.subTest(file=name), self.assertRaises((ValueError,OSError,subprocess.SubprocessError)): m.verify_run(moved,self.root)
            file.write_bytes(original)

    def test_optional_fixed_report_manifest(self):
        self.req.pop('fixed_report'); dump(self.request,self.req); self.info=m.inspect_request(self.request,self.root)
        self.make_run(); self.seal()
        manifest=json.loads((self.out/'sealed-inputs/manifest.json').read_text())
        self.assertIsNone(manifest['files']['fixed-report.json'])
        self.assertEqual(m.verify_run(self.out,self.root)['status'],'VERIFIED')

    def test_after_failure_after_successful_sealing(self):
        from unittest.mock import patch
        self.make_run()
        import shutil
        saved=self.root/'saved-run'; shutil.move(str(self.run),saved)
        shutil.rmtree(self.out)
        real_snapshot=m.snapshot; n=[0]
        def take(*args,**kwargs):
            n[0]+=1
            if n[0] == 2: raise RuntimeError('after-only')
            return real_snapshot(*args,**kwargs)
        class Done: returncode=0; stdout=b'ok'
        def runner(*args,**kwargs): shutil.copytree(saved,self.run); return Done()
        with patch.object(m,'snapshot',side_effect=take), self.assertRaisesRegex(RuntimeError,'after-only'):
            m.single_run(self.request,self.out,self.root,runner)
        data=json.loads((self.out/'failure.json').read_text())
        self.assertIsNone(data['run_exception']); self.assertIsNone(data['sealing_exception'])
        self.assertEqual(data['source_after_exception']['message'],'after-only')
        self.assertEqual(data['primary_failure'],'source_after_exception')
        self.assertTrue((self.out/'sealed-run/result.json').is_file())

    def test_finish_manifest_only_failure_is_recorded(self):
        from unittest.mock import patch
        import shutil
        self.make_run(); saved=self.root/'saved-run'; shutil.move(str(self.run), saved); shutil.rmtree(self.out)
        class Done: returncode=0; stdout=b'ok'
        def runner(*args,**kwargs): shutil.copytree(saved,self.run); return Done()
        failure=RuntimeError('manifest-only')
        with patch.object(m,'finish_manifest',side_effect=failure), self.assertRaises(RuntimeError) as caught:
            m.single_run(self.request,self.out,self.root,runner)
        self.assertIs(caught.exception,failure)
        record=json.loads((self.out/'failure.json').read_text())
        execution=json.loads((self.out/'execution.json').read_text())
        self.assertEqual(record['primary_failure_kind'],'finish_manifest')
        self.assertEqual(record['finish_manifest_exception']['message'],'manifest-only')
        self.assertIn('Traceback',record['finish_manifest_exception']['traceback'])
        self.assertEqual(record['run_return_code'],0)
        self.assertEqual(execution['status'],'FAILED')
        self.assertTrue((self.out/'sealed-inputs/manifest.json').is_file())
        self.assertTrue((self.out/'sealed-run/result.json').is_file())
        self.assertTrue((self.out/'source-after.json').is_file())

    def test_run_and_finish_manifest_failures_keep_original_primary(self):
        from unittest.mock import patch
        import shutil
        self.make_run(); saved=self.root/'saved-run'; shutil.move(str(self.run), saved); shutil.rmtree(self.out)
        original=RuntimeError('run-primary'); secondary=RuntimeError('manifest-secondary')
        def runner(*args,**kwargs): shutil.copytree(saved,self.run); raise original
        with patch.object(m,'finish_manifest',side_effect=secondary), self.assertRaises(RuntimeError) as caught:
            m.single_run(self.request,self.out,self.root,runner)
        self.assertIs(caught.exception,original)
        record=json.loads((self.out/'failure.json').read_text())
        self.assertEqual(record['primary_failure_kind'],'run')
        self.assertEqual(record['run_exception']['message'],'run-primary')
        self.assertEqual(record['finish_manifest_exception']['message'],'manifest-secondary')
        self.assertIn('Traceback',record['run_exception']['traceback'])
        self.assertIn('Traceback',record['finish_manifest_exception']['traceback'])

    def test_stdout_normalization_matrix(self):
        import shutil
        self.make_run()
        for raw, actual, accepted in [(b'1','1',True),(b'1\n','1\n',True),(b'1\r\n','1\r\n',True),(b'1\n\n','1\n\n',True),(b'1\n2','1\n2',False),(b'1\n','1',False),(b'\xff','1',False)]:
            log=self.run/'draft-build/verify.log'; log.write_bytes(raw)
            draft=self.run/'draft.json'; stage=json.loads(draft.read_text()); stage['data']['verification']['actual_output']=actual; dump(draft,stage)
            draft_result=self.run/'draft-build/result.json'; dump(draft_result,stage['data'])
            result=json.loads((self.run/'result.json').read_text())
            for name in ('draft-build/verify.log','draft-build/result.json','draft.json'):
                item=next(x for x in result['artifacts'] if x['uri'].endswith('/'+name)); item.update(m.file_info(self.run/name))
            result['stages'][0]['artifact'].update(m.file_info(draft)); dump(self.run/'result.json',result)
            self.seal()
            with self.subTest(raw=raw, actual=actual):
                if accepted: self.assertEqual(m.verify_run(self.out,self.root)['status'],'VERIFIED')
                else:
                    with self.assertRaises((ValueError,UnicodeDecodeError)): m.verify_run(self.out,self.root)
            shutil.rmtree(self.out/'sealed-run'); (self.out/'execution.json').unlink()

    def test_draft_exit_code_nonzero_independent(self):
        self.make_run(); draft=self.run/'draft.json'
        stage=json.loads(draft.read_text()); stage['data']['verification']['exit_code']=9; dump(draft,stage)
        inner=self.run/'draft-build/result.json'; dump(inner,stage['data'])
        result=json.loads((self.run/'result.json').read_text())
        for name in ('draft.json','draft-build/result.json'):
            next(x for x in result['artifacts'] if x['uri'].endswith('/'+name)).update(m.file_info(self.run/name))
        result['stages'][0]['artifact'].update(m.file_info(draft)); dump(self.run/'result.json',result); self.seal()
        with self.assertRaisesRegex(ValueError,'output mismatch'): m.verify_run(self.out,self.root)

    def test_handoff(self):
        package = self.root/'work/b2'; package.mkdir(parents=True)
        def save_file(name, data):
            path=package/name; path.write_text(data)
            return {'path':name, **m.file_info(path)}
        logs={r:save_file(r+'.log','log') for r in m.ROLES}
        stage_names=['draft','full-check','incremental-check','repair','recheck']
        e2e_result={
            'job_id':'job-test',
            'trace_id':'trace-test',
            'status':'SUCCEEDED',
            'base_commit':'b'*40,
            'target_commit':'c'*40,
            'stages':[{'name':name} for name in stage_names],
        }
        e2e_ref=save_file('e2e.json',json.dumps(e2e_result))
        e2e={
            'result_path':e2e_ref['path'],
            'result_bytes':e2e_ref['bytes'],
            'result_sha256':e2e_ref['sha256'],
            'job_id':e2e_result['job_id'],
            'trace_id':e2e_result['trace_id'],
            'status':'SUCCEEDED',
            'exit_code':0,
            'stages':stage_names,
            'base_commit':e2e_result['base_commit'],
            'target_commit':e2e_result['target_commit'],
        }
        image={'tag':'course:test','image_id':'sha256:'+'a'*64,'repo_digest':None,'repo_digest_absent_reason':'local image'}
        services={r:{'image':image['tag'], 'ports':[{'host_ip':'127.0.0.1','published':str(p),'target':8080}], 'volumes':([{'source':'/var/run/docker.sock','target':'/var/run/docker.sock'}] if r=='draft' else [])} for r,p in m.ROLES.items()}
        h={'candidate_commit':'a'*40,'compose':save_file('compose.yaml','compose'),'rendered_config':save_file('rendered.json',json.dumps({'services':services})),'image':image,'health':dict.fromkeys(m.ROLES,'healthy'),'logs':logs,'e2e':e2e}
        path=package/'handoff.json'; dump(path,h)
        self.assertEqual(m.handoff(path,self.root)['status'],'HANDOFF_VERIFIED')
        for field,value in (
            ('result_bytes',0),
            ('result_sha256','0'*64),
            ('job_id','job-other'),
        ):
            y=copy.deepcopy(h); y['e2e'][field]=value; dump(path,y)
            with self.subTest(e2e_field=field), self.assertRaises(ValueError):
                m.handoff(path,self.root)
        e2e_path=package/'e2e.json'
        original_e2e=e2e_path.read_text()
        e2e_path.write_text('{"status":"FAILED"}\n')
        dump(path,h)
        with self.assertRaises(ValueError):
            m.handoff(path,self.root)
        e2e_path.write_text(original_e2e)
        for mutate in (lambda x:x.update(candidate_commit='abcd'), lambda x:x['image'].pop('image_id'), lambda x:x['image'].pop('repo_digest_absent_reason'), lambda x:x['health'].update(draft='unhealthy'), lambda x:x['logs'].pop('draft'), lambda x:x['compose'].update(sha256='0'*64), lambda x:x['image'].update(tag='course')):
            y=copy.deepcopy(h); mutate(y); dump(path,y)
            with self.assertRaises((ValueError,KeyError)): m.handoff(path,self.root)
        for mutate in (lambda x:x['draft']['ports'][0].update(host_ip='0.0.0.0'), lambda x:x['draft'].update(volumes=[]), lambda x:x['mdfixer'].update(volumes=[{'source':'/var/run/docker.sock'}])):
            altered=copy.deepcopy(services); mutate(altered)
            metadata=save_file('rendered.json',json.dumps({'services':altered})); y=copy.deepcopy(h); y['rendered_config']=metadata; dump(path,y)
            with self.subTest(config=altered), self.assertRaises(ValueError): m.handoff(path,self.root)
        save_file('rendered.json',json.dumps({'services':services})); dump(path,h)
        (package/'rendered.json').write_text('tampered')
        with self.assertRaises(ValueError): m.handoff(path,self.root)
        save_file('rendered.json',json.dumps({'services':services}))
        (package/'compose.yaml').write_text('tampered')
        with self.assertRaises(ValueError): m.handoff(path,self.root)
        save_file('compose.yaml','compose')
        dump(path,h)
        log=package/'draft.log'; log.unlink(); log.symlink_to(package/'buildchecker.log')
        with self.assertRaises(ValueError): m.handoff(path,self.root)
        log.unlink(); log.write_text('log')
        folder=package/'logs'; folder.mkdir(); (folder/'draft.log').write_text('log')
        (package/'linked').symlink_to(folder,target_is_directory=True)
        y=copy.deepcopy(h); y['logs']['draft']['path']='linked/draft.log'; dump(path,y)
        with self.assertRaises(ValueError): m.handoff(path,self.root)
        for field,value in (('bytes',4),('sha256','0'*64)):
            y=copy.deepcopy(h); y['logs']['draft'][field]=value; dump(path,y)
            with self.subTest(field=field), self.assertRaises(ValueError): m.handoff(path,self.root)
        dump(path,h); (package/'draft.log').write_text('changed')
        with self.assertRaises(ValueError): m.handoff(path,self.root)
        updated=m.file_info(package/'draft.log')
        for field in ('bytes','sha256'):
            y=copy.deepcopy(h); y['logs']['draft'][field]=updated[field]; dump(path,y)
            with self.subTest(updated=field), self.assertRaises(ValueError): m.handoff(path,self.root)
        self.assertEqual(m.handoff(package/'missing',self.root)['status'],'BLOCKED_ON_B2_HANDOFF')


if __name__ == '__main__': unittest.main()
