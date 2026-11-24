import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

import e13_b3 as b


class B3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_process_timeout_kills_group(self):
        r = b.run_process([sys.executable, '-c', 'import time; time.sleep(30)'], .15, self.root/'log')
        self.assertTrue(r['timed_out'])
        self.assertTrue(r['cleanup'][0]['ok'])
        with self.assertRaises(ProcessLookupError):
            os.killpg(r['owned']['pgids'][0], 0)

    def test_only_owned_resources(self):
        with self.assertRaises(ValueError):
            b.stop_owned('containers', 'a'*64, {'containers': []})
        with patch('e13_b3.subprocess.run') as run:
            run.return_value.returncode = 1
            run.return_value.stdout = run.return_value.stderr = ''
            self.assertFalse(b.stop_owned('containers', 'a'*64, {'containers':['a'*64]}, runner=run)['ok'])
            self.assertEqual(run.call_args.args[0], ['docker','rm','-f','a'*64])

    def c4_fixture(self):
        root = self.root/'case'
        (root/'draft-build/iter-01').mkdir(parents=True)
        (root/'processes-and-containers').mkdir()
        def put(name, value):
            path = root/name
            path.write_text(json.dumps(value) if isinstance(value,dict) else value)
        state={'head':'a'*40,'status':'','files':{'Makefile':'b'*64}}
        attempt={'iteration':1,'tag':'e6-draft-replay:fixture-1',
                 'command':['docker','build','--progress=plain','-f','/course/work/task/draft-build/iter-01/Dockerfile',
                            '-t','e6-draft-replay:fixture-1','/course/work/task/draft-build/project']}
        put('request.json',{'build_timeout':0.01})
        put('console.log','timeout occurred\n'); put('exit-code.txt','1\n')
        put('source-before.json',state); put('source-after.json',state)
        put('result.json',{'status':'FAILED','error':{'code':'DRAFT_FAILED'},'stages':[]})
        put('draft-build/result.json',{'status':'TIMED_OUT','attempts':[attempt]})
        put('draft-build/iter-01/build-stdout.log','')
        put('draft-build/iter-01/build-stderr.log','build started')
        put('processes-and-containers/process-scan.json',{'checked_at':1,'command':b.C4_PS,'exit_code':0,
            'stdout':'100 1 100 /usr/bin/python worker\n','stderr':'','observer_pid':100,'observer_ppid':1,
            'task_markers':b.c4_markers(root,[attempt])})
        put('processes-and-containers/docker-ps.json',{'checked_at':1,'command':b.C4_DOCKER_PS,
            'exit_code':0,'stdout':'unrelated container\n','stderr':''})
        put('processes-and-containers/no-verify-container.txt','NO_VERIFY_CONTAINER_STARTED\n')
        return root

    def test_c4_complete_raw_evidence(self):
        root=self.c4_fixture()
        result=b.verify_c4_directory(root)
        self.assertEqual(result['status'],'PASS',result['errors'])
        self.assertTrue(all(result[k] for k in ('timeout_confirmed','source_unchanged','build_client_absent',
                                                 'verify_container_stopped','candidate_not_successful')))
        self.assertIn('BuildKit',result['observation_scope'])
        self.assertEqual(result['checked_files']['request.json']['sha256'],b.digest(root/'request.json'))

    def test_c4_required_files_and_invalid_results(self):
        root=self.c4_fixture()
        cases=[('source-before.json',None),('source-after.json',None),('exit-code.txt',None),
               ('exit-code.txt','0'),('exit-code.txt','nonsense'),('console.log',''),
               ('draft-build/iter-01/build-stderr.log',None)]
        for name,value in cases:
            with self.subTest(name=name,value=value):
                path=root/name; original=path.read_bytes()
                if value is None: path.unlink()
                else: path.write_text(value)
                self.assertNotEqual(b.verify_c4_directory(root)['status'],'PASS')
                path.write_bytes(original)
        cases=[('source-after.json',{'head':'a'*40,'status':'','files':{}}),
               ('source-after.json',{'head':'a'*40,'status':'','files':{'Makefile':'c'*64}}),
               ('result.json',{'status':'SUCCEEDED','error':{'code':'DRAFT_FAILED'}}),
               ('result.json',{'status':'FAILED','error':{'code':'DRAFT_FAILED'},'stages':[{'status':'PASS'}]}),
               ('draft-build/result.json',{'status':'SUCCEEDED','attempts':[{'iteration':1}]}),
               ('draft-build/result.json',{'status':'TIMED_OUT','attempts':[]}),
               ('draft-build/result.json',{'status':'TIMED_OUT','attempts':[{'iteration':1}],'verification':{'output_matches':True}}),
               ('draft-build/result.json',{'status':'TIMED_OUT','attempts':[{'iteration':2,'image_id':'sha256:abc'}]})]
        for name,value in cases:
            with self.subTest(name=name,value=value):
                path=root/name; original=path.read_bytes(); path.write_text(json.dumps(value))
                self.assertNotEqual(b.verify_c4_directory(root)['status'],'PASS')
                path.write_bytes(original)

    def test_c4_process_snapshot(self):
        root=self.c4_fixture(); path=root/'processes-and-containers/process-scan.json'
        original=json.loads(path.read_text()); tag='e6-draft-replay:fixture-1'
        for line,expected in [
            (f'200 1 200 docker build -t {tag} /tmp/p\n','FAILED'),
            (f'200 1 200 docker buildx build -t {tag} /tmp/p\n','FAILED'),
            ('200 1 200 docker build -t unrelated /tmp/p\n','PASS'),
            (f'100 1 100 docker build -t {tag} /tmp/p\n','PASS'),
            (f'200 1 200 grep docker build {tag}\n','PASS'),
            (f'200 1 200 ps -eo pid args docker build {tag}\n','PASS')]:
            with self.subTest(line=line):
                path.write_text(json.dumps({**original,'stdout':line}))
                self.assertEqual(b.verify_c4_directory(root)['status'],expected)
        path.write_text(json.dumps({**original,'task_markers':[]}))
        self.assertEqual(b.verify_c4_directory(root)['status'],'BLOCKED')
        path.write_text(json.dumps({**original,'stdout':'broken'}))
        self.assertEqual(b.verify_c4_directory(root)['status'],'BLOCKED')
        path.write_text(json.dumps({**original,'exit_code':1}))
        self.assertEqual(b.verify_c4_directory(root)['status'],'BLOCKED')

    def test_c4_container_snapshot(self):
        root=self.c4_fixture(); folder=root/'processes-and-containers'; cid='a'*64
        cidfile=root/'draft-build/verify-container-id.txt'; cidfile.write_text('invalid')
        self.assertEqual(b.verify_c4_directory(root)['status'],'FAILED')
        cidfile.write_text(cid)
        path=folder/'verify-container-inspect.json'
        common={'cid':cid,'command':['docker','inspect','--type','container',cid]}
        for running,expected in ((True,'FAILED'),(False,'PASS')):
            with self.subTest(running=running):
                path.write_text(json.dumps({**common,'exit_code':0,'stdout':json.dumps([{'Id':cid,'State':{'Running':running}}]),'stderr':''}))
                self.assertEqual(b.verify_c4_directory(root)['status'],expected)
        snapshot=folder/'docker-ps.json'; baseline=json.loads(snapshot.read_text())
        snapshot.write_text(json.dumps({**baseline,'stdout':cid+' Up 2 seconds\n'}))
        self.assertEqual(b.verify_c4_directory(root)['status'],'FAILED')
        snapshot.write_text(json.dumps(baseline))
        path.write_text(json.dumps({**common,'exit_code':1,'stdout':'','stderr':'Error: No such object'}))
        self.assertEqual(b.verify_c4_directory(root)['status'],'PASS')
        path.write_text(json.dumps({**common,'exit_code':1,'stdout':'','stderr':'permission denied'}))
        self.assertEqual(b.verify_c4_directory(root)['status'],'BLOCKED')
        path.write_text('{broken')
        self.assertEqual(b.verify_c4_directory(root)['status'],'BLOCKED')

    def pair(self):
        a, c = self.root/'bad', self.root/'good'
        a.mkdir(); c.mkdir()
        def result(folder, job, trace, status):
            (folder/'log').write_text(job)
            return {'job_id':job, 'trace_id':trace, 'status':status, 'artifacts':[{'uri':'artifact://'+job+'/log', 'sha256':b.digest(folder/'log')}]}
        return a, c, result(a,'job-a','trace-a','FAILED'), result(c,'job-b','trace-b','SUCCEEDED')

    def test_c7_success_and_rejections(self):
        a,c,bad,good = self.pair()
        state={'head':'a'*40,'status':'','sha256':{'file':'b'*64}}
        def verify(x=bad,y=good,after=bad,source=state,end=state,dirs=(a,c),clear=True):
            return b.verify_c7(x,y,*dirs,source,end,after,clear)
        self.assertEqual(verify(), 'PASS')
        for key in ('job_id','trace_id'):
            for value in ('',bad[key]):
                with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                    verify(y={**good,key:value})
        for kwargs in ({'after':{**bad,'status':'SUCCEEDED'}}, {'y':{**good,'status':'FAILED'}},
                       {'end':{'changed':True}}, {'clear':False}, {'dirs':(a,a/'nested')}):
            with self.assertRaises(ValueError): verify(**kwargs)
        wrong = json.loads(json.dumps(good)); wrong['artifacts'][0]['uri'] = 'artifact://job-a/log'
        with self.assertRaises(ValueError): verify(y=wrong)
        (c/'log').write_text('changed')
        with self.assertRaises(ValueError): verify()

    def c7_artifact_fixture(self):
        folder = self.root/'manifest'
        folder.mkdir()
        payloads = {'nested/data.json':b'{"ok":true}\n','nested/deep/log.txt':b'hello\n',
                    'binary/data.bin':b'\xff\x00\x80','root.txt':b'four\n'}
        items=[]
        for name, data in payloads.items():
            path=folder/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
            items.append({'uri':'artifact://job-good/'+name,'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()})
        return folder, {'job_id':'job-good','artifacts':items}

    def test_c7_artifact_contract_multiple_nested_and_binary(self):
        folder,result=self.c7_artifact_fixture()
        self.assertEqual(len(b.c7_artifacts(result,folder)),4)
        import copy
        mutations=[]
        x=copy.deepcopy(result); x['artifacts'][0]['uri']='artifact://other/nested/data.json'; mutations.append(x)
        x=copy.deepcopy(result); x['artifacts'][0]['uri']='artifact://job-good/../escape'; mutations.append(x)
        x=copy.deepcopy(result); x['artifacts'].append(copy.deepcopy(x['artifacts'][0])); mutations.append(x)
        x=copy.deepcopy(result); item=copy.deepcopy(x['artifacts'][0]); item['uri']='artifact://job-good/./nested/data.json'; x['artifacts'].append(item); mutations.append(x)
        x=copy.deepcopy(result); x['artifacts'][0]['bytes']+=1; mutations.append(x)
        x=copy.deepcopy(result); x['artifacts'][0]['sha256']='0'*64; mutations.append(x)
        x=copy.deepcopy(result); x['artifacts'][0]['uri']='artifact://job-good/missing'; mutations.append(x)
        for value in mutations:
            with self.subTest(value=value), self.assertRaises(ValueError): b.c7_artifacts(value,folder)
        outside=self.root/'outside'; outside.write_text('outside')
        (folder/'link').symlink_to(outside)
        x=copy.deepcopy(result); x['artifacts'][0]['uri']='artifact://job-good/link'
        with self.assertRaises(ValueError): b.c7_artifacts(x,folder)

    def test_c7_paths_are_validated_before_creation(self):
        work=self.root/'work'; project=self.root/'project'; project.mkdir()
        with self.assertRaises(ValueError): b.c7_validate_paths(work,project,work/'same',work/'same')
        with self.assertRaises(ValueError): b.c7_validate_paths(work,project,work/'a',work/'a'/'b')
        with self.assertRaises(ValueError): b.c7_validate_paths(work,project,self.root/'outside',work/'b')
        self.assertFalse(work.exists())

    def test_c7_preflight_blocks_missing_or_invalid_identity(self):
        for variant in ('missing','broken','job','trace','status','stage','docker_started'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve(); project=root/'project'; project.mkdir()
                entry=root/'entry'; entry.write_text('entry')
                good={'mode':'e12','base':'valid','target':'target','repo':str(project)}
                good_input=root/'good.json'; good_input.write_text(json.dumps(good))
                bad_input=root/'bad.json'; bad_input.write_text(json.dumps({**good,'base':'0'*40}))
                out=root/'work/case'; out.mkdir(parents=True)
                state={'head':'a'*40,'status':'','sha256':{'file':'b'*64}}
                calls=[]
                def launch(entry, request, dest, log, timeout):
                    calls.append((request,dest)); dest.mkdir(); log.write_text('failure')
                    (dest/'artifact').write_text('error')
                    result={'job_id':'job-bad','trace_id':'trace-bad','status':'FAILED',
                            'error':{'code':'COMMAND_FAILED'},'artifacts':[{'uri':'artifact://job-bad/artifact','sha256':b.digest(dest/'artifact')}]}
                    if variant in ('job','trace'): result.pop(variant+'_id')
                    if variant=='status': result['status']='SUCCEEDED'
                    if variant=='broken': (dest/'result.json').write_text('{broken')
                    elif variant!='missing': (dest/'result.json').write_text(json.dumps(result))
                    if variant!='stage':
                        (dest/'logs').mkdir(); (dest/'logs/base-project-resolve.log').write_text('bad revision')
                    return {'exit_code':1,'timed_out':variant=='docker_started','owned':{'pids':[],'pgids':[]}}
                snapshot={'containers':{'exit_code':0,'stdout':'same'}}
                with patch.object(b,'__file__',str(root/'labs/e13/e13_b3.py')), patch.object(b,'launch',side_effect=launch), \
                     patch.object(b,'source_state',return_value=state), patch.object(b,'c7_observe',return_value=snapshot):
                    code=b.run_c7(entry,project,bad_input,good_input,out,30,state,snapshot)
                self.assertEqual(code,1); self.assertEqual(len(calls),1)
                self.assertEqual(calls[0][0],out/'failed/request.json')
                self.assertTrue((out/'failed/exit-code.txt').is_file())
                self.assertTrue((out/'failure.json').is_file())
                self.assertTrue((out/'isolation-check.json').is_file())

    def test_c7_detects_cross_job_and_trace_in_both_artifacts(self):
        a,c,bad,good=self.pair()
        state={'head':'a'*40,'status':'','sha256':{'f':'b'*64}}
        for folder,result,identifier in ((a,bad,good['job_id']), (a,bad,good['trace_id']),
                                         (c,good,bad['job_id']), (c,good,bad['trace_id'])):
            path=folder/'log'; original=path.read_text(); old_hash=result['artifacts'][0]['sha256']
            path.write_text(identifier); result['artifacts'][0]['sha256']=b.digest(path)
            with self.assertRaisesRegex(ValueError,'CROSS_JOB'): b.verify_c7(bad,good,a,c,state,state,bad,True)
            path.write_text(original); result['artifacts'][0]['sha256']=old_hash

    def test_c7_launch_exception_preserves_failure_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); project=root/'project'; project.mkdir()
            entry=root/'entry'; entry.write_text('entry')
            request={'mode':'e12','base':'valid','target':'target','repo':str(project)}
            good=root/'good.json'; bad=root/'bad.json'
            good.write_text(json.dumps(request)); bad.write_text(json.dumps({**request,'base':'0'*40}))
            out=root/'work/case'; out.mkdir(parents=True)
            state={'head':'a'*40,'status':'','sha256':{'f':'b'*64}}
            snap={'containers':{'exit_code':0,'stdout':''}}
            with patch.object(b,'__file__',str(root/'labs/e13/e13_b3.py')), patch.object(b,'launch',side_effect=OSError('launch failed')):
                self.assertEqual(b.run_c7(entry,project,bad,good,out,30,state,snap),1)
            for name in ('failed/request.json','failed/console.log','failed/exit-code.txt',
                         'failed/failure.json','failure.json','isolation-check.json'):
                self.assertTrue((out/name).is_file(),name)
            self.assertEqual(json.loads((out/'failure.json').read_text())['failure_stage'],'failed_launch')

    def test_c7_process_identity_and_permissions(self):
        with patch.object(b.os,'kill',side_effect=ProcessLookupError):
            self.assertTrue(b.c7_pid_gone(999999))
        with patch.object(b.os,'kill',side_effect=PermissionError):
            self.assertFalse(b.c7_pid_gone(999999))
        observation={'containers':{'command':['docker','ps','-a','--no-trunc','--format','{{.ID}} {{.Names}} {{.Status}}'],
                                   'exit_code':0,'stdout':'','stderr':'','checked_at':1},
                     'processes':{'command':['ps','-eo','pid,ppid,pgid,args'],
                                  'exit_code':0,'stdout':'123 1 123 worker\n','stderr':'','checked_at':1}}
        with self.assertRaisesRegex(ValueError,'C7_TASK_PROCESS_IDENTITY_MISSING'):
            b.c7_snapshot_residual(observation,observation,self.root,{'timed_out':False,'owned':{'pids':[],'pgids':[]}})

    def test_c7_preflight_rejects_started_docker(self):
        folder=self.root/'failed'; (folder/'run').mkdir(parents=True)
        (folder/'request.json').write_text(json.dumps({'base':'0'*40}))
        (folder/'console.log').write_text('bad'); (folder/'exit-code.txt').write_text('1')
        (folder/'run/a').write_text('bad')
        (folder/'run/result.json').write_text(json.dumps({'status':'FAILED','job_id':'job-x','trace_id':'trace-x',
            'artifacts':[{'uri':'artifact://job-x/a','sha256':b.digest(folder/'run/a')}]}))
        state={'head':'a'*40,'status':'','sha256':{'f':'b'*64}}
        stage={'failure_stage':'revision_validation','docker_started':True,'build_resource_check':'NOT_APPLICABLE'}
        with self.assertRaises(ValueError): b.c7_preflight(folder,state,state,stage,True)

    def test_zip_rejects_unsafe(self):
        for n, name in enumerate(('../escape', '/absolute', 'C:/absolute', 'a/../../bad')):
            path = self.root/f'{n}.zip'
            with zipfile.ZipFile(path,'w') as z: z.writestr(name,'x')
            with self.assertRaises(ValueError): b.safe_extract(path,self.root,self.root/f'out{n}')
        path = self.root/'link.zip'
        with zipfile.ZipFile(path,'w') as z:
            item=zipfile.ZipInfo('link'); item.create_system=3; item.external_attr=(0o120777 << 16); z.writestr(item,'target')
        with self.assertRaises(ValueError): b.safe_extract(path,self.root,self.root/'outlink')

    def repo(self):
        repo=self.root/'repo'; repo.mkdir()
        def g(*args): return subprocess.run(['git','-C',str(repo),*args], check=True, capture_output=True, text=True).stdout.strip()
        g('init','-b','main'); g('config','user.name','test'); g('config','user.email','test@example.invalid')
        (repo/'UPSTREAM.md').write_text('https://github.com/kokke/tiny-AES-c\nPinned upstream commit: ' + '23856752fbd139da0b8ca6e471a13d5bcc99a08d')
        (repo/'LICENSE.upstream').write_text('This is free and unencumbered software released into the public domain.')
        (repo/'x').write_text('one'); g('add','.'); g('commit','-m','base'); base=g('rev-parse','HEAD')
        (repo/'x').write_text('two'); g('commit','-am','target'); target=g('rev-parse','HEAD')
        candidate=self.root/'candidate'; candidate.write_text('candidate')
        return repo,candidate,base,target,g

    def h3_real_structure_zip(self):
        repo,candidate,base,target,g=self.repo()
        archive=self.root/'teacher.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for path in repo.rglob('*'):
                if path.is_file():
                    z.write(path,b.H3_PREFIX+'repo/'+path.relative_to(repo).as_posix())
            z.write(candidate,b.H3_PREFIX+'candidate.Dockerfile')
            z.writestr(b.H3_PREFIX+'upstream-original/unlicense.txt','Unlicense')
        return archive,base,target

    def test_h3_temporary_plan_and_zip_binding(self):
        archive,base,target=self.h3_real_structure_zip()
        out=self.root/'work/h3'; out.mkdir(parents=True)
        extracted=[]; original_extract=b.h3_extract_checked
        def capture_zip(path,dest):
            extracted.append(Path(dest)); return original_extract(path,dest)
        with patch.object(b,'__file__',str(self.root/'labs/e13/e13_b3.py')), \
             patch.object(b,'H3_BASE',base), patch.object(b,'H3_TARGET',target), \
             patch.object(b,'h3_extract_checked',side_effect=capture_zip):
            plan=b.h3_create_plan(archive,out)
            self.assertEqual(plan['status'],'NOT_RUN')
            self.assertEqual(b.h3_verify_new_plan(plan,out)['status'],'PASS')
            self.assertEqual(plan['identity']['target'],target)
            self.assertEqual(len(extracted),2)
            self.assertTrue(all(path.resolve().parent.parent == Path(tempfile.gettempdir()).resolve() for path in extracted))
            self.assertTrue(all(not path.exists() for path in extracted))
            self.assertFalse((out/'input').exists())
            self.assertFalse(any(p.name == '.git' for p in (self.root/'work').rglob('*')))
            self.assertFalse((self.root/'reports').exists())
            request=out/'request.json'; request.write_text('{}')
            with self.assertRaises(ValueError): b.h3_verify_new_plan(plan,out)

    def test_h3_preflight_unsafe_entries_and_missing_root(self):
        cases=(('../escape','UNSAFE_ZIP_ENTRY'),('/absolute','UNSAFE_ZIP_ENTRY'),
               ('a\\..\\escape','UNSAFE_ZIP_ENTRY'),('a/./b','DUPLICATE_OR_ABNORMAL_ZIP_PATH'))
        for index,(name,error) in enumerate(cases):
            with self.subTest(name=name):
                archive=self.root/f'bad-{index}.zip'
                with zipfile.ZipFile(archive,'w') as z: z.writestr(name,'x')
                with self.assertRaisesRegex(ValueError,error): b.h3_preflight(archive)
        archive=self.root/'missing.zip'
        with zipfile.ZipFile(archive,'w') as z: z.writestr('unrelated','x')
        with self.assertRaisesRegex(ValueError,'H3_ROOT_NOT_UNIQUE'): b.h3_preflight(archive)

    def test_h3_preflight_symlink_special_and_path_conflict(self):
        archive=self.root/'symlink.zip'
        with zipfile.ZipFile(archive,'w') as z:
            info=zipfile.ZipInfo('link'); info.create_system=3; info.external_attr=0o120777<<16; z.writestr(info,'target')
        with self.assertRaisesRegex(ValueError,'UNSAFE'): b.h3_preflight(archive)
        archive=self.root/'special.zip'
        with zipfile.ZipFile(archive,'w') as z:
            info=zipfile.ZipInfo('device'); info.create_system=3; info.external_attr=0o020600<<16; z.writestr(info,'')
        with self.assertRaisesRegex(ValueError,'UNSAFE'): b.h3_preflight(archive)
        archive=self.root/'conflict.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('a','x'); z.writestr('a/b','y')
        with self.assertRaisesRegex(ValueError,'CONFLICT'): b.h3_preflight(archive)
        archive=self.root/'double.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('same','x')
            with self.assertWarns(UserWarning): z.writestr('same','y')
        with self.assertRaisesRegex(ValueError,'DUPLICATE'): b.h3_preflight(archive)

    def test_h3_new_manifest_real_stage_bindings(self):
        archive,base,target=self.h3_real_structure_zip()
        out=self.root/'work/h3'; out.mkdir(parents=True)
        with patch.object(b,'__file__',str(self.root/'labs/e13/e13_b3.py')), \
             patch.object(b,'H3_BASE',base), patch.object(b,'H3_TARGET',target):
            plan=b.h3_create_plan(archive,out)
            root=out/'run'; root.mkdir(); job='job-'+'a'*32; trace='trace-'+'b'*32
            request=json.loads((out/'request.json').read_text())
            def write(name,value):
                path=root/name; path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(value)+'\n' if isinstance(value,dict) else value)
            def item(name):
                path=root/name
                return {'uri':'artifact://'+job+'/'+name,'sha256':b.digest(path),'bytes':path.stat().st_size}
            write('request.json',request); write('draft-build/verify.log','1\n'); write('draft-build/verify-stderr.log','')
            write('draft-build/result.json',{'status':'SUCCEEDED','verification':{'exit_code':0,'actual_output':'1\n',
                  'expected_output':'1','output_matches':True}})
            write('candidate.patch','patch'); write('repair-plan.json','[]')
            write('baseline-cache.json',{}); write('incremental-report.json',{})
            (root/'nested').mkdir(); (root/'nested/binary.bin').write_bytes(b'\xff\x00\x80')
            validation={'accepted':True}; write('validation/validation.json',validation)
            findings=[{'type':'REDUNDANT','target':'main.o','dependency':'unused.h'}]
            stages=[]
            for name in ('draft','full-check','incremental-check','repair','recheck'):
                data={'validation':validation,'findings':findings} if name=='recheck' else {}
                referenced={'draft':['draft-build/result.json'],'full-check':['baseline-cache.json'],
                            'incremental-check':['incremental-report.json'],'repair':['candidate.patch','repair-plan.json'],
                            'recheck':['validation/validation.json']}[name]
                write(name+'.json',{'schema_version':'e11e12-1','kind':name,'job_id':job,'trace_id':trace,
                      'status':'SUCCEEDED','commit':base if name=='full-check' else target,'data':data,
                      'artifacts':[item(path) for path in referenced]})
                stages.append({'name':name,'artifact':item(name+'.json')})
            all_files=[p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()]
            result={'job_id':job,'trace_id':trace,'status':'SUCCEEDED','base_commit':base,'target_commit':target,
                    'stages':stages,'artifacts':[item(x) for x in all_files]}
            write('result.json',result)
            state={'head':target,'status':'','sha256':plan['identity']['files']}
            for name,val in [('source-before.json',state),('source-after.json',state)]:
                (out/name).write_text(json.dumps(val))
            (out/'console.log').write_text('finished'); (out/'exit-code.txt').write_text('0\n')
            manifest=b.h3_manifest_file(out,result); (out/'evidence-manifest.json').write_text(json.dumps(manifest))
            self.assertEqual(b.h3_verify_new_run(plan,out)['findings'],findings)
            import copy
            snapshots={p:p.read_bytes() for p in out.rglob('*') if p.is_file()}
            def restore():
                for path,data in snapshots.items(): path.write_bytes(data)
            def manifest_edit(fn):
                current=json.loads((out/'evidence-manifest.json').read_text())
                fn(current)
                (out/'evidence-manifest.json').write_text(json.dumps(current))
            for label, edit, code in (
                ('missing',lambda m:m['files'].pop(),'MANIFEST_REQUIRED_FILE_MISSING'),
                ('size',lambda m:m['files'][0].update(bytes=m['files'][0]['bytes']+1),'MANIFEST_CONTENT_MISMATCH'),
                ('sha',lambda m:m['files'][0].update(sha256='0'*64),'MANIFEST_CONTENT_MISMATCH'),
                ('trace',lambda m:m.update(trace_id='wrong'),'MANIFEST_CONTENT_MISMATCH'),
                ('teacher',lambda m:m.update(teacher_project=False),'INVALID_MANIFEST'),
                ('teacher_missing',lambda m:m.pop('teacher_project'),'INVALID_MANIFEST'),
                ('name',lambda m:m.update(project_name='other'),'INVALID_MANIFEST'),
                ('ab',lambda m:m.update(ab_real_project=True),'INVALID_MANIFEST'),
                ('job_empty',lambda m:m.update(job_id=''),'INVALID_MANIFEST'),
                ('trace_empty',lambda m:m.update(trace_id=''),'INVALID_MANIFEST'),
                ('path_escape',lambda m:m['files'][0].update(path='../escape'),'UNSAFE_MANIFEST_PATH'),
                ('wrong_job_uri',lambda m:next(x for x in m['files'] if 'uri' in x).update(uri='artifact://job-other/a'),'MANIFEST_URI_MISMATCH'),
                ('missing_file',lambda m:m['files'].append({'path':'missing','bytes':0,'sha256':'0'*64,'job_id':job,'trace_id':trace}),'MANIFEST_CONTENT_MISMATCH'),
                ('duplicate',lambda m:m['files'].append(copy.deepcopy(m['files'][0])),'UNSAFE_MANIFEST_PATH'),
                ('duplicate_uri',lambda m:next(x for x in m['files'] if x.get('uri') and x['path'].endswith('draft.json')).update(uri=next(x['uri'] for x in m['files'] if x.get('uri') and x['path'].endswith('repair.json'))),'MANIFEST_URI_MISMATCH'),
            ):
                with self.subTest(case=label):
                    restore(); manifest_edit(edit)
                    with self.assertRaisesRegex(ValueError,code): b.h3_verify_new_run(plan,out)
            def refresh(keep_stages=False):
                current=json.loads((root/'result.json').read_text())
                for stage in current['stages']:
                    path=root/(stage['name']+'.json'); envelope=json.loads(path.read_text())
                    envelope['artifacts']=[item(x['uri'].split('artifact://'+job+'/',1)[1]) for x in envelope['artifacts']]
                    write(stage['name']+'.json',envelope)
                current['artifacts']=[item(x['uri'].split('artifact://'+job+'/',1)[1]) for x in current['artifacts']]
                if not keep_stages:
                    for stage in current['stages']:
                        stage['artifact']=item(stage['name']+'.json')
                write('result.json',current)
                (out/'evidence-manifest.json').write_text(json.dumps(b.h3_manifest_file(out,current)))
            def mutate_json(path, fn):
                current=json.loads(path.read_text()); fn(current); path.write_text(json.dumps(current)+'\n')
            mutations=(
                ('phase_missing',lambda:mutate_json(root/'result.json',lambda r:r['stages'].pop()),'PHASE_ORDER'),
                ('phase_reversed',lambda:mutate_json(root/'result.json',lambda r:r['stages'].reverse()),'PHASE_ORDER'),
                ('phase_duplicate',lambda:mutate_json(root/'result.json',lambda r:r['stages'].append(r['stages'][0])),'PHASE_ORDER'),
                ('stage_job',lambda:mutate_json(root/'draft.json',lambda r:r.update(job_id='job-other')),'STAGE_IDENTITY_MISMATCH'),
                ('stage_trace',lambda:mutate_json(root/'draft.json',lambda r:r.update(trace_id='trace-other')),'STAGE_IDENTITY_MISMATCH'),
                ('missing',lambda:mutate_json(root/'recheck.json',lambda r:r['data']['findings'].append({'type':'MISSING'})),'MISSING_REMAINS'),
                ('validation',lambda:mutate_json(root/'validation/validation.json',lambda r:r.update(accepted=False)),'VALIDATION_FAILED'),
                ('source_head',lambda:mutate_json(out/'source-after.json',lambda r:r.update(head='0'*40)),'SOURCE_CHANGED'),
                ('source_status',lambda:mutate_json(out/'source-after.json',lambda r:r.update(status=' M file')),'SOURCE_CHANGED'),
                ('both_dirty',lambda:(mutate_json(out/'source-before.json',lambda r:r.update(status=' M file')),mutate_json(out/'source-after.json',lambda r:r.update(status=' M file'))),'SOURCE_CHANGED'),
                ('source_hash',lambda:mutate_json(out/'source-after.json',lambda r:r['sha256'].update(x='0'*64)),'SOURCE_CHANGED'),
                ('draft_exit',lambda:mutate_json(root/'draft-build/result.json',lambda r:r['verification'].update(exit_code=1)),'PROGRAM_OUTPUT_MISMATCH'),
                ('stderr',lambda:(root/'draft-build/verify-stderr.log').write_text('error'),'PROGRAM_OUTPUT_MISMATCH'),
                ('outer_exit',lambda:(out/'exit-code.txt').write_text('1'),'INVALID_EXECUTION'),
                ('target',lambda:mutate_json(root/'result.json',lambda r:r.update(target_commit='0'*40)),'COMMIT_MISMATCH'),
            )
            for label,mutate,code in mutations:
                with self.subTest(case=label):
                    restore(); mutate(); refresh()
                    with self.assertRaisesRegex(ValueError,code): b.h3_verify_new_run(plan,out)
            for key in ('job_id','trace_id'):
                with self.subTest(case='result_empty_'+key):
                    restore(); mutate_json(root/'result.json',lambda r:r.update({key:''}))
                    manifest_edit(lambda m:next(x for x in m['files'] if x['path']=='run/result.json').update(
                        sha256=b.digest(root/'result.json'),bytes=(root/'result.json').stat().st_size))
                    with self.assertRaisesRegex(ValueError,'INVALID_EXECUTION'): b.h3_verify_new_run(plan,out)
            restore()
            symlink=root/'nested/link'; symlink.symlink_to(root/'nested/binary.bin')
            manifest_edit(lambda m:m['files'].append({'path':'run/nested/link','bytes':3,'sha256':b.digest(symlink),
                         'uri':'artifact://'+job+'/nested/link','job_id':job,'trace_id':trace}))
            with self.assertRaisesRegex(ValueError,'MANIFEST_CONTENT_MISMATCH'): b.h3_verify_new_run(plan,out)
            symlink.unlink()
            restore()
            (root/'draft-build/verify.log').write_text('wrong\n')
            mutate_json(root/'draft-build/result.json',lambda r:r['verification'].update(actual_output='wrong\n'))
            refresh()
            with self.assertRaisesRegex(ValueError,'PROGRAM_OUTPUT_MISMATCH'): b.h3_verify_new_run(plan,out)
            restore()
            mutate_json(root/'result.json',lambda r:r['stages'][0]['artifact'].update(uri='artifact://'+job+'/repair.json'))
            refresh(keep_stages=True)
            with self.assertRaisesRegex(ValueError,'STAGE_ARTIFACT_MISMATCH'): b.h3_verify_new_run(plan,out)
            restore(); (root/'candidate.patch').write_text('tamper')
            with self.assertRaisesRegex(ValueError,'MANIFEST_CONTENT_MISMATCH'): b.h3_verify_new_run(plan,out)
            restore(); (root/'draft-build/verify.log').write_text('wrong\n')
            with self.assertRaises(ValueError): b.h3_verify_new_run(plan,out)
            restore(); (root/'draft-build/verify-stderr.log').write_text('error')
            with self.assertRaises(ValueError): b.h3_verify_new_run(plan,out)
            restore(); (out/'exit-code.txt').write_text('1')
            with self.assertRaises(ValueError): b.h3_verify_new_run(plan,out)
            restore(); (out/'source-after.json').write_text('{}')
            with self.assertRaises(ValueError): b.h3_verify_new_run(plan,out)

    def test_h3_plan_integrity_matrix(self):
        import copy
        archive,base,target=self.h3_real_structure_zip()
        out=self.root/'work/h3'; out.mkdir(parents=True)
        with patch.object(b,'__file__',str(self.root/'labs/e13/e13_b3.py')), \
             patch.object(b,'H3_BASE',base), patch.object(b,'H3_TARGET',target):
            plan=b.h3_create_plan(archive,out)
            original_request=(out/'request.json').read_bytes()
            self.assertEqual(b.h3_verify_new_plan(plan,out)['status'],'PASS')
            for label, change, expected in (
                ('zip_sha',lambda p:p.update(zip_sha256='0'*64),'ZIP_HASH_MISMATCH'),
                ('member_sha',lambda p:p['members'][next(iter(p['members']))].update(sha256='0'*64),'H3_IDENTITY_MISMATCH'),
                ('license_sha',lambda p:p['identity'].update(license_sha256='0'*64),'H3_IDENTITY_MISMATCH'),
                ('candidate_sha',lambda p:p['identity'].update(candidate_sha256='0'*64),'H3_IDENTITY_MISMATCH'),
                ('job',lambda p:p.update(job_id='job-fake'),'PREPOPULATED_RESULT'),
                ('trace',lambda p:p.update(trace_id='trace-fake'),'PREPOPULATED_RESULT'),
                ('server',lambda p:p.update(result={'status':'SUCCEEDED'}),'PREPOPULATED_RESULT'),
                ('pass',lambda p:p.update(success='PASS'),'PREPOPULATED_RESULT'),
                ('status_pass',lambda p:p.update(status='PASS'),'INVALID_PLAN'),
                ('status_succeeded',lambda p:p.update(status='SUCCEEDED'),'INVALID_PLAN'),
            ):
                with self.subTest(case=label):
                    altered=copy.deepcopy(plan); change(altered)
                    with self.assertRaisesRegex(ValueError,expected): b.h3_verify_new_plan(altered,out)
            (out/'request.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'REQUEST_MISMATCH'): b.h3_verify_new_plan(plan,out)
            (out/'request.json').write_bytes(original_request)
            external=self.root/'external'; external.mkdir()
            request=json.loads(original_request); request['repo']=str(external)
            (out/'request.json').write_text(json.dumps(request))
            altered=copy.deepcopy(plan); altered.update(request_sha256=b.digest(out/'request.json'), request_bytes=(out/'request.json').stat().st_size)
            with self.assertRaisesRegex(ValueError,'REQUEST_IDENTITY_MISMATCH'): b.h3_verify_new_plan(altered,out)
            (out/'request.json').write_bytes(original_request)
            original_zip=archive.read_bytes()
            archive.write_bytes(original_zip+b'tamper')
            with self.assertRaisesRegex(ValueError,'ZIP_HASH_MISMATCH'): b.h3_verify_new_plan(plan,out)
            archive.write_bytes(original_zip)
            replacement=self.root/'rewritten.zip'
            with zipfile.ZipFile(archive) as src, zipfile.ZipFile(replacement,'w') as dst:
                for member in src.infolist():
                    data=src.read(member)
                    if member.filename == b.H3_PREFIX+'upstream-original/unlicense.txt': data=b'altered'
                    dst.writestr(member,data)
            archive.write_bytes(replacement.read_bytes())
            altered=copy.deepcopy(plan); altered['zip_sha256']=b.digest(archive)
            with self.assertRaisesRegex(ValueError,'H3_IDENTITY_MISMATCH'): b.h3_verify_new_plan(altered,out)
            archive.write_bytes(original_zip)
            altered=copy.deepcopy(plan); altered['identity']['head']='f'*40
            with self.assertRaisesRegex(ValueError,'H3_IDENTITY_MISMATCH'): b.h3_verify_new_plan(altered,out)

    def test_h3_duplicate_project_root_rejected(self):
        archive,base,target=self.h3_real_structure_zip()
        with zipfile.ZipFile(archive,'a') as z:
            z.writestr('another/H3-tiny-aes/repo/UPSTREAM.md','other')
        with self.assertRaisesRegex(ValueError,'H3_ROOT_NOT_UNIQUE'):
            b.h3_preflight(archive)

    def test_h3_source_git_identity_matrix(self):
        archive,base,target=self.h3_real_structure_zip()
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)/'input'; b.h3_extract_checked(archive,root)
            folder=root/b.H3_PREFIX; repo=folder/'repo'
            def check(): return b.h3_source_identity(folder)
            with patch.object(b,'H3_BASE',base),patch.object(b,'H3_TARGET',target):
                self.assertEqual(check()['head'],target)
                with patch.object(b,'H3_BASE','0'*40):
                    with self.assertRaises(subprocess.CalledProcessError) as cm: check()
                    self.assertIn('rev-parse',cm.exception.cmd)
                    self.assertIn('0'*40+'^{commit}',cm.exception.cmd)
                with patch.object(b,'H3_TARGET','0'*40):
                    with self.assertRaises(subprocess.CalledProcessError) as cm: check()
                    self.assertIn('rev-parse',cm.exception.cmd)
                with patch.object(b,'H3_BASE',target):
                    with self.assertRaisesRegex(ValueError,'H3_IDENTICAL_COMMITS'): check()
                with patch.object(b,'H3_TARGET',base):
                    with self.assertRaisesRegex(ValueError,'H3_HEAD_MISMATCH'): check()
                def run_git(*args):
                    return subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True,text=True).stdout.strip()
                run_git('config','user.name','fixture'); run_git('config','user.email','fixture@example.invalid')
                run_git('checkout','--detach',base)
                (repo/'x').write_text('sibling')
                run_git('commit','-am','sibling')
                sibling=run_git('rev-parse','HEAD')
                run_git('checkout','--detach',target)
                with patch.object(b,'H3_BASE',sibling):
                    with self.assertRaisesRegex(ValueError,'H3_NON_ANCESTOR'): check()
                with patch.object(b,'H3_TARGET',sibling):
                    with self.assertRaisesRegex(ValueError,'H3_HEAD_MISMATCH'): check()
                (repo/'.git/shallow').write_text(target+'\n')
                with self.assertRaisesRegex(ValueError,'SHALLOW_REPOSITORY'): check()
                (repo/'.git/shallow').unlink()
                upstream=repo/'UPSTREAM.md'; original=upstream.read_text()
                upstream.unlink()
                with self.assertRaises(FileNotFoundError) as cm: check()
                self.assertEqual(Path(cm.exception.filename).name,'UPSTREAM.md')
                upstream.write_text(original.replace('kokke/tiny-AES-c','other/project'))
                with self.assertRaisesRegex(ValueError,'H3_SOURCE_IDENTITY_MISMATCH'): check()
                upstream.write_text(original.replace(b.H3_UPSTREAM,'0'*40))
                with self.assertRaisesRegex(ValueError,'H3_SOURCE_IDENTITY_MISMATCH'): check()
                upstream.write_text(original)
                license_file=repo/'LICENSE.upstream'; license_bytes=license_file.read_bytes(); license_file.unlink()
                with self.assertRaises(FileNotFoundError) as cm: check()
                self.assertEqual(Path(cm.exception.filename).name,'LICENSE.upstream')
                license_file.write_bytes(license_bytes)
                candidate=folder/'candidate.Dockerfile'; original_candidate=candidate.read_bytes(); candidate.unlink()
                with self.assertRaises(FileNotFoundError) as cm: check()
                self.assertEqual(Path(cm.exception.filename).name,'candidate.Dockerfile')
                candidate.write_bytes(original_candidate)
                obj=repo/'.git/objects'/target[:2]/target[2:]; obj.unlink()
                with self.assertRaises(subprocess.CalledProcessError) as cm: check()
                self.assertIn('fsck',cm.exception.cmd)

    def test_h3_formal_execution_fails_closed_without_manifest(self):
        archive,base,target=self.h3_real_structure_zip()
        out=self.root/'work/h3'; out.mkdir(parents=True)
        with patch.object(b,'__file__',str(self.root/'labs/e13/e13_b3.py')), \
             patch.object(b,'H3_BASE',base), patch.object(b,'H3_TARGET',target):
            plan=b.h3_create_plan(archive,out)
            with self.assertRaises(FileNotFoundError): b.h3_verify_new_run(plan,out)

    def test_h3_plan_and_invalid_history(self):
        repo,candidate,base,target,g=self.repo()
        plan=b.h3_plan(repo,candidate,self.root/'plan.json')
        self.assertEqual(plan['status'],'NOT_RUN'); self.assertEqual(plan['request']['base'],base)
        self.assertFalse((self.root/'result.json').exists())
        with self.assertRaises(ValueError): b.h3_plan(repo,candidate,self.root/'p',target,target)
        with self.assertRaises(ValueError): b.h3_plan(repo,candidate,self.root/'p',target,base)
        (repo/'LICENSE.upstream').unlink()
        with self.assertRaises(ValueError): b.h3_plan(repo,candidate,self.root/'p')

    def test_shallow_and_missing_objects(self):
        repo,candidate,base,target,g=self.repo()
        (repo/'.git/shallow').write_text(target+'\n')
        with self.assertRaises(ValueError): b.h3_plan(repo,candidate,self.root/'p')
        (repo/'.git/shallow').unlink()
        obj=repo/'.git/objects'/target[:2]/target[2:]; obj.unlink()
        with self.assertRaises(subprocess.CalledProcessError): b.h3_plan(repo,candidate,self.root/'p')



    def test_nonancestor_commit_rejected(self):
        repo,candidate,base,target,g=self.repo()
        g('checkout','--detach',base)
        (repo/'x').write_text('sibling')
        g('commit','-am','sibling')
        sibling=g('rev-parse','HEAD')
        with self.assertRaisesRegex(ValueError, 'NOT_ANCESTOR'):
            b.h3_plan(repo,candidate,self.root/'p',target,sibling)

    def test_duplicate_zip_rejected(self):
        path=self.root/'duplicate.zip'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('same','a')
            with self.assertWarns(UserWarning): z.writestr('same','b')
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):
            b.safe_extract(path,self.root,self.root/'extract')

    def test_invalid_base_keeps_real_job_and_trace(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e11e12'))
        import pipeline
        repo, candidate, base, target, g = self.repo()
        result = pipeline.execute({'mode':'e12', 'repo':str(repo), 'base':'0'*40,
                                   'target':target, 'candidate':str(candidate)}, self.root/'failed-run')
        self.assertEqual(result['status'], 'FAILED')
        self.assertTrue(result['job_id'].startswith('job-'))
        self.assertTrue(result['trace_id'].startswith('trace-'))
        self.assertEqual(result['error']['code'], 'COMMAND_FAILED')

    def test_failure_stage(self):
        record={'status':'FAILED','error':{'code':'COMMAND_FAILED'}}
        (self.root/'run/logs').mkdir(parents=True)
        (self.root/'run/logs/base-project-resolve.log').write_text('invalid revision')
        result=b.failure_stage(record,self.root/'run',{'timed_out':False})
        self.assertFalse(result['docker_started'])
        self.assertEqual(result['build_resource_check'],'NOT_APPLICABLE')
        (self.root/'run/draft-build').mkdir(parents=True)
        self.assertEqual(b.failure_stage(record,self.root/'run',{'timed_out':False})['build_resource_check'],'BLOCKED')

    def test_h3_plan_verify_rejects_prefilled(self):
        repo,candidate,base,target,g=self.repo()
        archive=self.root/'data.zip'
        with zipfile.ZipFile(archive,'w') as z:
            prefix='e13-upstream-student/H3-tiny-aes/'
            for f in repo.rglob('*'):
                if f.is_file(): z.write(f,prefix+'repo/'+f.relative_to(repo).as_posix())
            z.writestr(prefix+'upstream-original/README','fixture')
            z.write(candidate,prefix+'candidate.Dockerfile')
        plan=b.h3_plan(repo,candidate,self.root/'plan.json')
        plan.update(zip_path=str(archive),zip_sha256=b.digest(archive),zip_safety='PASSED',project_kind='teacher_project',zip_members=b.h3_zip_members(archive))
        self.assertEqual(b.verify_h3_plan(plan)['status'],'PASS')
        for key in ('job_id','trace_id','success'):
            with self.assertRaises(ValueError): b.verify_h3_plan({**plan,key:'x'})

    def test_c7_main_runs_failure_before_success(self):
        base={'mode':'e12','base':'valid','target':'target','repo':str(self.root/'project')}
        good=self.root/'good.json'; bad=self.root/'bad.json'
        good.write_text(json.dumps(base)); bad.write_text(json.dumps({**base,'base':'0'*40}))
        out=self.root/'work/output'; calls=[]; request_paths=[]
        (self.root/'project').mkdir()
        (self.root/'entry').write_text('entry')
        def launch(entry, request, dest, log, timeout):
            calls.append(dest.parent.name)
            request_paths.append(request)
            dest.mkdir()
            failed=dest.parent.name=='failed'
            job='job-bad' if failed else 'job-good'
            trace='trace-bad' if failed else 'trace-good'
            paths={'nested/data.json':b'{"ok":true}', 'deep/log.txt':b'log',
                   'bin/raw.bin':b'\xff\x00\x80', 'other.txt':b'other'}
            items=[]
            for name,data in paths.items():
                artifact=dest/name; artifact.parent.mkdir(parents=True,exist_ok=True); artifact.write_bytes(data)
                items.append({'uri':'artifact://'+job+'/'+name,'bytes':len(data),'sha256':b.digest(artifact)})
            request_data=json.loads(request.read_text())
            (dest/'request.json').write_text(json.dumps(request_data))
            result={'job_id':job,'trace_id':trace,'status':'FAILED' if failed else 'SUCCEEDED',
                    'error':{'code':'COMMAND_FAILED'} if failed else None,'artifacts':items}
            if not failed:
                result.update(base_commit=request_data['base'],target_commit=request_data['target'])
            (dest/'result.json').write_text(json.dumps(result))
            if failed:
                (dest/'logs').mkdir(); (dest/'logs/base-project-resolve.log').write_text('invalid')
            log.write_text(job)
            return {'exit_code':1 if failed else 0,'timed_out':False,'owned':{'pids':[999999],'pgids':[999999]},'started_at':len(calls)*2,'finished_at':len(calls)*2}
        snapshot={'containers':{'command':['docker','ps','-a','--no-trunc','--format','{{.ID}} {{.Names}} {{.Status}}'],
                                'exit_code':0,'stdout':'','stderr':'','checked_at':1},
                  'processes':{'command':['ps','-eo','pid,ppid,pgid,args'],
                               'exit_code':0,'stdout':'123 1 123 /usr/bin/worker\n','stderr':'','checked_at':1}}
        snapshots=[{key:{**value,'checked_at':stamp} for key,value in snapshot.items()} for stamp in (1,3,5)]
        args=['e13_b3.py','c7','--entry',str(self.root/'entry'),'--project',str(self.root/'project'),'--request',str(good),
              '--failed-request',str(bad),'--out',str(out)]
        with patch.object(sys,'argv',args), patch.object(b,'__file__',str(self.root/'labs/e13/e13_b3.py')), patch.object(b,'launch',side_effect=launch), \
             patch.object(b,'source_state',return_value={'head':'a'*40,'status':'','sha256':{'file':'b'*64}}), patch.object(b,'observe',return_value=snapshot), patch.object(b,'c7_pid_gone',return_value=True), patch.object(b,'c7_observe',side_effect=snapshots):
            self.assertEqual(b.main(),0)
        self.assertEqual(calls,['failed','succeeded'])
        self.assertEqual(request_paths,[(out/'failed/request.json').resolve(),(out/'succeeded/request.json').resolve()])
        self.assertTrue((out/'failed/request.json').is_file())
        self.assertTrue((out/'succeeded/request.json').is_file())
        evidence=json.loads((out/'isolation-check.json').read_text())
        self.assertEqual(evidence['stage']['build_resource_check'],'NOT_APPLICABLE')
        self.assertEqual(evidence['status'],'PASS')
        self.assertEqual(b.verify_c7_evidence(out)['status'],'PASS')
        summary_path=out/'isolation-check.json'
        for name in ('failed/request.json','failed/result.json','failed/console.log','failed/exit-code.txt',
                     'failed/source-before.json','failed/source-after.json','failed/observation-after.json',
                     'succeeded/request.json','succeeded/result.json','succeeded/console.log','succeeded/exit-code.txt',
                     'succeeded/source-before.json','succeeded/source-after.json','succeeded/observation-after.json'):
            with self.subTest(raw_file=name):
                path=out/name; old=path.read_bytes(); path.write_bytes(old+b' ')
                with self.assertRaisesRegex(ValueError,'C7_RAW_INDEX_MISMATCH'): b.verify_c7_evidence(out)
                path.write_bytes(old)
        original_summary=summary_path.read_bytes()
        for key,value in (('residual_clear',False),('bad_dir','/tmp/escape'),('bad',{**evidence['bad'],'status':'SUCCEEDED'})):
            with self.subTest(summary=key):
                summary_path.write_text(json.dumps({**evidence,key:value}))
                with self.assertRaisesRegex(ValueError,'C7_SUMMARY_MISMATCH'): b.verify_c7_evidence(out)
                summary_path.write_bytes(original_summary)
        artifact=out/'succeeded/run/nested/data.json'; artifact_bytes=artifact.read_bytes(); artifact.write_text('tampered')
        with self.assertRaisesRegex(ValueError,'ARTIFACT_HASH'): b.verify_c7_evidence(out)
        artifact.write_bytes(artifact_bytes)
        path=out/'succeeded/console.log'; old=path.read_bytes(); path.write_text(evidence['bad']['trace_id'])
        updated=json.loads(original_summary); updated['raw_index']=b.c7_raw_index(out); summary_path.write_text(json.dumps(updated))
        with self.assertRaisesRegex(ValueError,'C7_CONSOLE_CROSS_JOB'): b.verify_c7_evidence(out)
        path.write_bytes(old); summary_path.write_bytes(original_summary)
        path=out/'failed/observation-after.json'; old=path.read_bytes(); observation=json.loads(old)
        observation['containers']['stdout']='a'*64+' task running\n'; path.write_text(json.dumps(observation))
        updated=json.loads(original_summary); updated['raw_index']=b.c7_raw_index(out); summary_path.write_text(json.dumps(updated))
        with self.assertRaisesRegex(ValueError,'C7_CONTAINER_RESIDUAL_UNPROVEN'): b.verify_c7_evidence(out)
        path.write_bytes(old); summary_path.write_bytes(original_summary)
        # Rewrite both copies and the index to ensure the verifier rejects semantic
        # contradictions rather than relying only on summary hashes.
        for side,key,value,code in (
            ('failed','job_id',None,'INVALID_JOB_ID'),
            ('failed','trace_id',None,'INVALID_TRACE_ID'),
            ('succeeded','job_id',evidence['bad']['job_id'],'INVALID_JOB_ID'),
            ('succeeded','trace_id',evidence['bad']['trace_id'],'INVALID_TRACE_ID'),
        ):
            with self.subTest(side=side,key=key,value=value):
                one=out/side/'result.json'; two=out/side/'run/result.json'
                one_old=one.read_bytes(); two_old=two.read_bytes()
                changed=json.loads(one_old)
                if value is None: changed.pop(key)
                else: changed[key]=value
                one.write_text(json.dumps(changed)); two.write_text(json.dumps(changed))
                summary=json.loads(original_summary)
                summary['bad' if side=='failed' else 'good']=changed
                if side=='failed': summary['bad_after']=changed
                summary['raw_index']=b.c7_raw_index(out); summary_path.write_text(json.dumps(summary))
                with self.assertRaisesRegex(ValueError,code): b.verify_c7_evidence(out)
                one.write_bytes(one_old); two.write_bytes(two_old); summary_path.write_bytes(original_summary)
        for key,value,code in (('uri','artifact://job-other/nested/data.json','WRONG_JOB_URI'),
                               ('bytes',999,'ARTIFACT_SIZE'), ('sha256','0'*64,'ARTIFACT_HASH'),
                               ('uri','artifact://job-good/../escape','UNSAFE_ARTIFACT_PATH')):
            with self.subTest(artifact_field=key,value=value):
                one=out/'succeeded/result.json'; two=out/'succeeded/run/result.json'
                one_old=one.read_bytes(); two_old=two.read_bytes()
                changed=json.loads(one_old); changed['artifacts'][0][key]=value
                one.write_text(json.dumps(changed)); two.write_text(json.dumps(changed))
                summary=json.loads(original_summary); summary['good']=changed
                summary['raw_index']=b.c7_raw_index(out); summary_path.write_text(json.dumps(summary))
                with self.assertRaisesRegex(ValueError,code): b.verify_c7_evidence(out)
                one.write_bytes(one_old); two.write_bytes(two_old); summary_path.write_bytes(original_summary)
        path=out/'succeeded/source-after.json'; old=path.read_bytes(); changed=json.loads(old)
        changed['sha256']['file']='c'*64; path.write_text(json.dumps(changed))
        summary=json.loads(original_summary); summary['source_after']=changed
        summary['raw_index']=b.c7_raw_index(out); summary_path.write_text(json.dumps(summary))
        with self.assertRaisesRegex(ValueError,'C7_SOURCE_CHANGED'): b.verify_c7_evidence(out)
        path.write_bytes(old); summary_path.write_bytes(original_summary)
        for side in ('failed','succeeded'):
            with self.subTest(case='request_mismatch_'+side):
                one=out/side/'request.json'; two=out/side/'run/request.json'
                old_one=one.read_bytes(); old_two=two.read_bytes()
                changed=json.loads(old_one); changed['target']='different-target'
                one.write_text(json.dumps(changed)); two.write_text(json.dumps(changed))
                updated=json.loads(original_summary); updated['raw_index']=b.c7_raw_index(out)
                summary_path.write_text(json.dumps(updated))
                with self.assertRaisesRegex(ValueError,'C7_REQUEST_MISMATCH'): b.verify_c7_evidence(out)
                one.write_bytes(old_one); two.write_bytes(old_two); summary_path.write_bytes(original_summary)
        path=out/'failed/observation-after.json'; old=path.read_bytes(); observation=json.loads(old)
        observation['processes']['stdout'] += '999 1 999 docker build '+str((out/'failed').resolve())+'/run\n'
        path.write_text(json.dumps(observation))
        updated=json.loads(original_summary); updated['raw_index']=b.c7_raw_index(out); summary_path.write_text(json.dumps(updated))
        with self.assertRaisesRegex(ValueError,'C7_PROCESS_RESIDUAL'): b.verify_c7_evidence(out)
        path.write_bytes(old); summary_path.write_bytes(original_summary)
        stray=out/'failed/other.json'; stray.write_text(json.dumps({'foreign':evidence['good']['trace_id']}))
        with self.assertRaisesRegex(ValueError,'C7_JSON_CROSS_JOB'): b.verify_c7_evidence(out)
        stray.unlink()
        request=out/'failed/request.json'; old=request.read_bytes(); request.unlink()
        request.symlink_to(out/'succeeded/request.json')
        with self.assertRaisesRegex(ValueError,'C7_SYMLINK_PATH'): b.verify_c7_evidence(out)
        request.unlink(); request.write_bytes(old)
        meta=out/'failed/run-meta.json'; old=meta.read_bytes(); changed=json.loads(old)
        changed['owned']['pids']=[]; meta.write_text(json.dumps(changed))
        updated=json.loads(original_summary); updated['raw_index']=b.c7_raw_index(out); summary_path.write_text(json.dumps(updated))
        with self.assertRaisesRegex(ValueError,'C7_TASK_PROCESS_IDENTITY_MISSING'): b.verify_c7_evidence(out)
        verify_out=self.root/'verify-output'
        args=['e13_b3.py','verify','--evidence',str(summary_path),'--out',str(verify_out)]
        with patch.object(sys,'argv',args): self.assertEqual(b.main(),1)
        failure=json.loads((verify_out/'failure.json').read_text())
        self.assertIn('C7_TASK_PROCESS_IDENTITY_MISSING',failure['error'])
        saved=(verify_out/'failure.json').read_bytes()
        with patch.object(sys,'argv',args): self.assertEqual(b.main(),1)
        self.assertEqual((verify_out/'failure.json').read_bytes(),saved)
        meta.write_bytes(old); summary_path.write_bytes(original_summary)

    def test_h3_formal_verify_and_tamper(self):
        repo,candidate,base,target,g=self.repo()
        archive=self.root/'data.zip'
        with zipfile.ZipFile(archive,'w') as z:
            prefix='e13-upstream-student/H3-tiny-aes/'
            for f in repo.rglob('*'):
                if f.is_file(): z.write(f,prefix+'repo/'+f.relative_to(repo).as_posix())
            z.writestr(prefix+'upstream-original/README','fixture')
            z.write(candidate,prefix+'candidate.Dockerfile')
        plan=b.h3_plan(repo,candidate,self.root/'plan.json')
        plan.update(zip_path=str(archive),zip_sha256=b.digest(archive),zip_safety='PASSED',project_kind='teacher_project',zip_members=b.h3_zip_members(archive))
        root=self.root/'evidence'; run=root/'run'; run.mkdir(parents=True)
        job, trace='job-a','trace-a'
        findings=[{'type':'REDUNDANT','target':'main.o','dependency':'unused.h'}]
        validation={'accepted':True}
        def write(name,value):
            path=run/name; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(value)+'\n' if isinstance(value,dict) else value)
        def item(name): return {'uri':'artifact://'+job+'/'+name,'sha256':b.digest(run/name)}
        write('candidate.patch','patch')
        write('validation/validation.json',validation)
        write('draft-build/verify.log','1\n'); write('draft-build/verify-stderr.log','')
        write('draft-build/result.json',{'verification':{'exit_code':0,'actual_output':'1\n','output_matches':True}})
        stages=[]
        for name in ('draft','full-check','incremental-check','repair','recheck'):
            data={'validation':validation,'findings':findings} if name=='recheck' else {}
            refs=[item('candidate.patch')]
            write(name+'.json',{'kind':name,'job_id':job,'trace_id':trace,'status':'SUCCEEDED',
                                'commit':base if name=='full-check' else target,'data':data,'artifacts':refs})
            stages.append({'name':name,'artifact':item(name+'.json')})
        write('request.json',{'base':base,'target':target})
        names=['candidate.patch','validation/validation.json','draft-build/verify.log',
               'draft-build/verify-stderr.log','draft-build/result.json','request.json','recheck.json']
        result={'job_id':job,'trace_id':trace,'status':'SUCCEEDED','base_commit':base,'target_commit':target,
                'stages':stages,'artifacts':[item(x) for x in names]}
        write('result.json',result)
        (root/'source-before.json').write_text('{}'); (root/'source-after.json').write_text('{}')
        (root/'execution.json').write_text('{"exit_code":0}')
        (root/'request.json').write_text('{}')
        manifest={name:b.digest(root/name) for name in ('execution.json','source-before.json','source-after.json','request.json','run/result.json')}
        (root/'evidence-manifest.json').write_text(json.dumps(manifest))
        self.assertEqual(b.verify_h3_run(plan,root)['findings'],findings)
        altered=dict(result,stages=stages[:-1]); write('result.json',altered)
        with self.assertRaises(ValueError): b.verify_h3_run(plan,root)
        write('result.json',{**result,'trace_id':'wrong'})
        with self.assertRaises(ValueError): b.verify_h3_run(plan,root)
        write('result.json',result); (run/'candidate.patch').write_text('tampered')
        with self.assertRaises(ValueError): b.verify_h3_run(plan,root)
        (run/'candidate.patch').write_text('patch'); (run/'draft-build/verify-stderr.log').unlink()
        with self.assertRaises(ValueError): b.verify_h3_run(plan,root)

    def test_b2_archived_real_manifest(self):
        root = Path(__file__).resolve().parents[2]/'reports/E13/B2/H2-inih/run'
        result = json.loads((root/'result.json').read_text())
        prefix = 'artifact://' + result['job_id'] + '/'
        available = [item for item in result['artifacts'] if (root/item['uri'][len(prefix):]).is_file()]
        self.assertGreater(len(available), 1)
        b.c7_artifacts({'job_id':result['job_id'], 'artifacts':available}, root)
        with self.assertRaises(ValueError):
            b.c7_artifacts(result, root)

    def test_fresh_refuses_existing(self):
        with self.assertRaises(FileExistsError): b.fresh(self.root)

if __name__ == '__main__': unittest.main()
