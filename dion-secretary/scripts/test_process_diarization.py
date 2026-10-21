"""Exercise process output with controlled ASR and local-minute stubs."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import patch
import secretary
import diarization

def test():
    with tempfile.TemporaryDirectory(prefix='secretary-integration-') as tmp:
        root=Path(tmp); source=root/'fixture.wav';source.write_bytes(b'fixture')
        model=root/'model';model.mkdir();(model/'model.bin').write_bytes(b'fixture')
        notes=root/'notes';sessions=root/'sessions';sessions.mkdir()
        words=[SimpleNamespace(start=.2,end=.8,word='Первый'),SimpleNamespace(start=2.2,end=2.8,word='Второй')]
        segment=SimpleNamespace(words=words)
        class Model:
            def __init__(self,*a,**kw):pass
            def transcribe(self,*a,**kw):
                assert kw['word_timestamps'] is True
                return iter([segment]),None
        turns=[{'start':0,'end':1,'speaker':8},{'start':2,'end':3,'speaker':9}]
        args=SimpleNamespace(file=str(source),resume=None,session=None,title='Synthetic test',no_diarization=False,num_speakers=2,speaker_mode='voice',meeting_journal=None,minutes_provider='local')
        cfg={**secretary.CONFIG,'notes':str(notes),'speech_engine':'whisper','diarization':{'enabled':True}}
        with patch.object(secretary,'CONFIG',cfg),patch.object(secretary,'SESSIONS',sessions),patch.object(secretary,'model_path',return_value=model),patch.object(secretary,'minutes',return_value='Synthetic protocol'),patch.object(diarization,'run_worker',return_value=turns),patch('faster_whisper.WhisperModel',Model),patch.object(secretary,'output'):
            secretary.process(args)
        session=next(sessions.iterdir())
        rows=json.loads((session/'transcript.json').read_text('utf-8'))
        assert [r['speaker'] for r in rows]==['Спикер 1','Спикер 2']
        transcript=next(notes.glob('*стенограмма.md')).read_text('utf-8')
        assert '**Спикер 1**: Первый' in transcript and '**Спикер 2**: Второй' in transcript
        assert (session/'transcript.words.named.json').exists()
        print('Process integration passed: numbered speakers exported to Markdown.')
if __name__=='__main__':test()
