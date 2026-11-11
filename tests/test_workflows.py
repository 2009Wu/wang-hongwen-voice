"""Durable results, cache migration and transactional update regression checks."""
import hashlib,io,json,os,sys,tempfile,time,unittest,wave,zipfile
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import studio_paths as paths,studio_library as library,studio_update as updater,runner

class Workflows(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.stack=ExitStack()
        for module in (paths,library):
            for key,relative in [('STATE','state'),('EXPORTS','exports'),('HISTORY','state/history'),('WORKSPACES','state/workspaces'),('VOICES','state/voices')]:
                if hasattr(module,key):self.stack.enter_context(patch.object(module,key,self.root/relative))
    def tearDown(self):self.stack.close();self.temporary.cleanup()
    def wav(self,path):
        path.parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(path),'wb') as out:out.setparams((1,2,16000,0,'NONE','none'));out.writeframes(b'\x01\x10'*16000*5)
        return path
    def test_archive_survives_temporary_cleanup_and_reload(self):
        job=self.root/('a'*32);job.mkdir();public=job/'results';public.mkdir()
        source=self.wav(self.root/'external.wav');original=source.read_bytes()
        request=library.stash_request({'mode':'speak','text':'private prompt','reference_input':str(source)},job)
        result={key:None for key in ('audio','wav','flac','video','details','reference')}
        result.update(audio=str(self.wav(public/'voice.wav')),elapsed_seconds=1)
        saved=library.archive(request,result,job)
        import shutil;shutil.rmtree(job)
        self.assertEqual(Path(saved['audio']).read_bytes(),original)
        self.assertEqual(library.get_record(saved['history_id'])['status'],'completed')
        retried=library.retry_request(saved['history_id']);self.assertTrue(Path(retried['reference_input']).exists())
        self.assertEqual(source.read_bytes(),original)
        with patch.dict(os.environ,{'VOICE_WORKSPACE_LIMIT_MB':'0'}):library.prune_workspaces()
        self.assertTrue(Path(saved['audio']).exists())
        with self.assertRaises((ValueError,FileNotFoundError)):library.retry_request(saved['history_id'])
    def test_voice_favorite_is_independent_and_deletion_preserves_original(self):
        source=self.wav(self.root/'voice.wav');identifier=library.save_voice('测试声音',source,'准确原话','Chinese')
        source.unlink();path,item=library.load_voice(identifier)
        self.assertEqual(item['text'],'准确原话');self.assertTrue(Path(path).exists())
        library.delete_voice(identifier);self.assertEqual(library.voice_choices(),[])
        for bad in ('../outside','a'*31,'A'*32):
            with self.assertRaises(ValueError):library.load_voice(bad)
    def test_shared_cache_deduplicates_without_copying_credentials(self):
        shared=self.root/'shared';legacy=self.root/'legacy'
        for parent in [shared,legacy]:
            (parent/'torch').mkdir(parents=True);(parent/'torch/model.pt').write_bytes(b'model bytes')
        (legacy/'huggingface').mkdir();(legacy/'huggingface/token').write_text('private')
        (legacy/'torch/partial.incomplete').write_bytes(b'incomplete')
        with patch.dict(os.environ,{'MODEL_CACHE':str(shared)}):report=paths.migrate_cache(legacy)
        self.assertEqual(report['deduplicated_bytes'],11)
        self.assertTrue(os.path.samefile(shared/'torch/model.pt',legacy/'torch/model.pt'))
        self.assertFalse((shared/'huggingface/token').exists());self.assertFalse((shared/'torch/partial.incomplete').exists())
        second=self.root/'second';(second/'torch').mkdir(parents=True);(second/'torch/model.pt').write_bytes(b'model bytes')
        with patch.dict(os.environ,{'MODEL_CACHE':str(shared)}):paths.migrate_cache(second)
        self.assertTrue(os.path.samefile(second/'torch/model.pt',shared/'torch/model.pt'))
    def bundle(self,path,files=None,extra=None):
        files=files or {'app.py':b'new application',paths.PRODUCT['launcher']:b'MZnew'}
        meta={'product':paths.PRODUCT['id'],'version':'9.0.0','files':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
        with zipfile.ZipFile(path,'w') as out:
            for name,data in files.items():out.writestr(name,data)
            out.writestr('release-manifest.json',json.dumps(meta))
            if extra:out.writestr(*extra)
        return path
    def staged(self):
        stage=self.root/'.runtime/updates/staged/test';stage.mkdir(parents=True)
        updater.unpack_bundle(self.bundle(stage/'update.zip'),stage/'bundle');return stage
    def test_update_and_rollback_preserve_user_data(self):
        (self.root/'app.py').write_bytes(b'old app');(self.root/paths.PRODUCT['launcher']).write_bytes(b'MZold')
        user=self.root/'.runtime/private-recording';user.parent.mkdir();user.write_bytes(b'private')
        stage=self.staged();backup=updater.apply_stage(stage,self.root)
        self.assertEqual((self.root/'app.py').read_bytes(),b'new application');self.assertEqual(user.read_bytes(),b'private')
        updater.restore_backup(backup,self.root)
        self.assertEqual((self.root/'app.py').read_bytes(),b'old app');self.assertEqual(user.read_bytes(),b'private')
        self.assertFalse((self.root/'release-manifest.json').exists())
    def test_failed_update_rolls_back_already_written_files(self):
        (self.root/'app.py').write_bytes(b'old');stage=self.staged();real=updater.atomic_copy;count=[0]
        def fail_once(source,target):
            count[0]+=1
            if count[0]==2:raise OSError('simulated write failure')
            return real(source,target)
        with patch.object(updater,'atomic_copy',fail_once):
            with self.assertRaises(OSError):updater.apply_stage(stage,self.root)
        self.assertEqual((self.root/'app.py').read_bytes(),b'old')
        self.assertFalse((self.root/'.runtime/update-transaction.json').exists())
    def test_interrupted_update_recovers_and_relaunches(self):
        (self.root/'app.py').write_bytes(b'old app');stage=self.staged()
        backup=updater.apply_stage(stage,self.root)
        paths.atomic_json(self.root/'.runtime/update-transaction.json',{'backup':str(backup)})
        with patch.object(updater.subprocess,'Popen') as launch:
            updater.run_request(self.root,0,recover=True)
        self.assertEqual((self.root/'app.py').read_bytes(),b'old app')
        self.assertTrue(paths.read_json(self.root/'.runtime/update-result.json')['ok'])
        self.assertFalse((self.root/'.runtime/update-transaction.json').exists())
    def test_diagnostics_omits_recordings_and_prompts(self):
        import studio_diagnostics as diagnostic
        state=self.root/'state';state.mkdir(parents=True,exist_ok=True)
        (state/'secret-prompt.txt').write_text('private prompt')
        self.wav(state/'private-voice.wav')
        with patch.object(diagnostic,'STATE',state):report=diagnostic.export_report()
        with zipfile.ZipFile(report) as result:
            self.assertEqual(set(result.namelist()),{'diagnostics.json','说明.txt'})
            self.assertNotIn('private prompt',result.read('diagnostics.json').decode())
    def test_tamper_and_unsafe_names_rejected(self):
        for index,name in enumerate(['../outside','.runtime/ready.json','A/../bad','NUL.txt','x\\y','a:b','x.']):
            package=self.bundle(self.root/f'bad{index}.zip',{'app.py':b'x',paths.PRODUCT['launcher']:b'MZ',name:b'evil'})
            with self.assertRaises(ValueError):updater.unpack_bundle(package,self.root/f'bad{index}')
        package=self.bundle(self.root/'extra.zip',extra=('not-in-manifest',b'evil'))
        with self.assertRaises(ValueError):updater.unpack_bundle(package,self.root/'extra')
        stage=self.staged();(stage/'bundle/app.py').write_bytes(b'tampered')
        with self.assertRaises(ValueError):updater.apply_stage(stage,self.root)
        self.assertFalse((self.root/'app.py').exists())
    def test_generator_close_after_success_does_not_mark_failure(self):
        fake=self.root/'fake';fake.mkdir()
        (fake/'worker.py').write_text("import sys,json;from pathlib import Path;p=Path(sys.argv[1]).parent;r=p/'results';r.mkdir();a=r/'voice.mp3';a.write_bytes(b'audio');(p/'result.json').write_text(json.dumps(dict(audio=str(a),wav=None,flac=None,video=None,details=None,reference=None,elapsed_seconds=1)))")
        with patch.multiple(runner,ROOT=fake,JOBS=self.root/'jobs',SING_PYTHON=sys.executable,TTS_PYTHON=sys.executable):
            generator=runner.run_job({'mode':'speak','text':'test'})
            for _,_,result in generator:
                if result:generator.close();break
        self.assertEqual(library.get_record(result['history_id'])['status'],'completed')
    def test_update_refuses_active_generation(self):
        runner.GPU_LOCK.acquire()
        try:
            with self.assertRaisesRegex(ValueError,'当前生成'):updater.request_update(rollback=True)
        finally:runner.GPU_LOCK.release()

if __name__=='__main__':unittest.main()
