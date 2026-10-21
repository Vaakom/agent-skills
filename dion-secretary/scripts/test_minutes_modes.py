"""Provider routing, source integrity and local fact verification regressions."""
import sys,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import secretary
import minutes_handoff as h
import local_minutes as lm
from fact_context import expand,accepted
class Modes(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='minutes-routing-')
        self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name)
        self.source=self.work/'2026-10-18_01-00-00_Тест — стенограмма.md'
        self.text='# Тест — стенограмма\n\n[00:00:01] **? Анна**: не\n[00:00:02] **Борис**: удаляем поле.\n[00:00:30] **Анна**: Проверю завтра.\n'
        self.source.write_text(self.text,'utf-8')
    def prep(self,provider='codex'):
        return h.prepare(self.source,self.work/'meeting.md','Тест','2026-10-18',self.work,provider)
    def test_codex_handoff_never_calls_local(self):
        with patch.object(secretary,'minutes',side_effect=AssertionError('Local model called')):
            result=secretary.create_minutes_handoff(self.source,self.work/'meeting.md','Тест','date',self.work,'codex')
        self.assertEqual(result['state'],'awaiting_codex')
        self.assertFalse((self.work/'meeting.md').exists())
    def test_local_route(self):
        with patch.object(secretary,'minutes',return_value='## Главное\n\nЛокальная проверка.') as run:
            data=secretary.create_minutes_handoff(self.source,self.work/'meeting.md','Тест','date',self.work,'local')
        run.assert_called_once()
        self.assertEqual(data['state'],'complete')
        self.assertIn('Резюме: local',Path(data['protocol']).read_text('utf-8'))
    def test_finalize_backup_and_bold_names(self):
        path,data=self.prep()
        note=Path(data['protocol']);note.write_text('OLD','utf-8')
        draft=self.work/'draft.md';draft.write_text('**? Анна** проверит [00:00:30].','utf-8')
        out=h.finalize(path,draft,lambda *a:{'state':'no_previous'})
        self.assertEqual(out['state'],'complete')
        self.assertIn('**? Анна**',note.read_text('utf-8'))
        self.assertEqual(next(self.work.glob('meeting.md.*.bak')).read_text('utf-8'),'OLD')
    def test_source_change_blocks_finalize(self):
        path,data=self.prep();self.source.write_text(self.text+'changed','utf-8')
        draft=self.work/'draft.md';draft.write_text('content','utf-8')
        with self.assertRaises(RuntimeError):h.finalize(path,draft,lambda *a:{})
        self.assertFalse(Path(data['protocol']).exists())
    def test_empty_draft_blocks_finalize(self):
        path,data=self.prep();draft=self.work/'draft.md';draft.write_text(' ','utf-8')
        with self.assertRaises(ValueError):h.finalize(path,draft,lambda *a:{})
    def test_parser_and_neighbor_negation(self):
        turns=lm.parse_turns(self.text)
        self.assertEqual(turns['R00001']['speaker'],'? Анна')
        self.assertIn('R00001',{t['id'] for t in expand(turns,['R00002'])})
        with self.assertRaises(ValueError):expand(turns,['R99999'])
    def test_bad_owner_and_unknown_id_rejected(self):
        turns=lm.parse_turns(self.text)
        f={'kind':'task','text':'Проверить','owner':'Анна','deadline':'','evidence':['R00003'],'owner_evidence':[],'deadline_evidence':[]}
        self.assertFalse(lm.valid_fact(f,turns))
        f.update(owner='',evidence=['R99999'])
        self.assertFalse(lm.valid_fact(f,turns))
    def test_contradiction_and_uncertainty_rejected(self):
        check={'verdict':'supported','all_parts_supported':True,'final_status_confirmed':True,
               'supporting_ids':['R00001'],'opposing_ids':['R00002'],'reason':'negative'}
        self.assertFalse(accepted(check,{'R00001','R00002'}))
        check.update(opposing_ids=[],final_status_confirmed=False)
        self.assertFalse(accepted(check,{'R00001','R00002'}))
    def test_summary_only_does_not_repeat_asr(self):
        with patch.object(secretary,'ROOT',self.work),patch.object(secretary,'output') as output,patch.object(secretary,'minutes',side_effect=AssertionError):
            secretary.summarize_existing(SimpleNamespace(transcript=str(self.source),title=None,minutes_provider='codex'))
        data=output.call_args.args[0]
        self.assertEqual(data['title'],'Тест')
        self.assertEqual(Path(data['protocol']).name,'2026-10-18_01-00-00_Тест.md')
        self.assertEqual(data['state'],'awaiting_codex')
        self.assertEqual(data['created'],'2026-10-18T01:00:00')
    def test_named_model_selects_local_cli(self):
        with patch.object(sys,'argv',['secretary.py','summarize','--transcript',str(self.source),'--minutes-model','installed-model']),patch.dict(secretary.CONFIG),patch.object(secretary,'summarize_existing') as run:
            secretary.main()
            self.assertEqual(run.call_args.args[0].minutes_provider,'local')
            self.assertEqual(secretary.CONFIG['minutes_model'],'installed-model')
    def test_defaults_cli(self):
        for command,args in [('process',['--session',str(self.work)]),('summarize',['--transcript',str(self.source)])]:
            with patch.object(sys,'argv',['secretary.py',command]+args),patch.object(secretary,'process') as process,patch.object(secretary,'summarize_existing') as summarize:
                secretary.main()
                self.assertEqual((process if command=='process' else summarize).call_args.args[0].minutes_provider,'codex')
    def process_fixture(self,provider,minutes_mock):
        import gigaam_adapter, speaker_names
        source=self.work/'audio.wav';source.write_bytes(b'fixture')
        sessions=self.work/'sessions';sessions.mkdir();notes=self.work/'notes'
        args=SimpleNamespace(file=str(source),resume=None,session=None,title='Проверка',
            speaker_mode='browser',no_diarization=False,num_speakers=None,
            meeting_journal=None,minutes_provider=provider)
        rows=[{'start':1.,'end':2.,'speaker':'? Анна','text':'Проверю документ.'}]
        with patch.dict(secretary.CONFIG,notes=str(notes),speech_engine='gigaam-v3'),patch.object(secretary,'SESSIONS',sessions),patch.object(gigaam_adapter,'transcribe_tracks',return_value=rows),patch.object(speaker_names,'apply_names',side_effect=lambda rows,session:rows),patch.object(secretary,'minutes',minutes_mock),patch.object(secretary,'output') as output:
            try:
                secretary.process(args)
            except RuntimeError:
                return sessions,notes,output,True
            return sessions,notes,output,False
    def test_process_default_exports_then_codex_finalize(self):
        from unittest.mock import Mock
        calls=Mock(side_effect=AssertionError('Unexpected local inference'))
        sessions,notes,output,failed=self.process_fixture('codex',calls)
        self.assertFalse(failed);calls.assert_not_called()
        result=output.call_args.args[0]
        self.assertEqual(result['state'],'awaiting_codex')
        transcript=Path(result['transcript']).read_text('utf-8')
        self.assertIn('\n\n[00:00:01] **? Анна**:',transcript)
        self.assertFalse(Path(result['protocol']).exists())
        draft=next(sessions.iterdir())/'draft.md'
        draft.write_text('## Действия\n\n- **? Анна** проверит документ [00:00:01].','utf-8')
        out=h.finalize(result['handoff'],draft,lambda *args:{'state':'no_previous'})
        self.assertEqual(out['state'],'complete')
        self.assertTrue(Path(result['protocol']).is_file())
    def test_process_local_failure_retains_exported_transcript(self):
        from unittest.mock import Mock
        sessions,notes,output,failed=self.process_fixture('local',Mock(side_effect=RuntimeError('model missing')))
        self.assertTrue(failed)
        transcript=next(notes.glob('*стенограмма.md'))
        self.assertIn('Проверю документ.',transcript.read_text('utf-8'))
        handoff=json.loads((next(sessions.iterdir())/'minutes-handoff.json').read_text('utf-8'))
        self.assertEqual(handoff['state'],'awaiting_local')
        self.assertFalse(Path(handoff['protocol']).exists())
    def test_local_inference_options_and_incomplete_output(self):
        with patch.object(secretary,'ensure_ollama'),patch.object(secretary,'api',return_value={'done_reason':'stop','message':{'content':'{"facts":[]}'}}) as api:
            secretary.evidence_call('draft','source',{})
            payload=api.call_args.args[1]
            self.assertEqual(payload['model'],'qwen3.5:9b')
            self.assertFalse(payload['think'])
            self.assertEqual(payload['options']['num_ctx'],32768)
            self.assertEqual(payload['options']['num_predict'],12000)
            secretary.evidence_call('РОВНО ОДИН','source',{})
            self.assertEqual(api.call_args.args[1]['options']['num_predict'],2500)
        with patch.object(secretary,'ensure_ollama'),patch.object(secretary,'api',return_value={'done_reason':'length'}):
            with self.assertRaises(RuntimeError):secretary.evidence_call('draft','source',{})

if __name__=='__main__':unittest.main(verbosity=2)
