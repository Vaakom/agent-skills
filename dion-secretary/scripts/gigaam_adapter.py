"""Prepare recording tracks for the isolated, offline GigaAM worker."""
import hashlib,json,subprocess,wave
from pathlib import Path
from faster_whisper.audio import decode_audio
from faster_whisper.vad import get_speech_timestamps,VadOptions
def transcribe_tracks(tracks,session,config):
    section=config['gigaam'];session=Path(session)
    work=session/'gigaam-work';(work/'audio').mkdir(parents=True,exist_ok=True)
    manifest=[]
    for idx,(label,source) in enumerate(tracks):
        source=Path(source)
        with source.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        audio=decode_audio(str(source),sampling_rate=16000)
        spans=get_speech_timestamps(audio,VadOptions(max_speech_duration_s=22,min_silence_duration_ms=500,speech_pad_ms=300))
        chunks=[]
        for span in spans:
            for a in range(span['start'],span['end'],24*16000):
                b=min(span['end'],a+24*16000)
                p=work/'audio'/f'{idx}-{a}-{b}.wav'
                with wave.open(str(p),'wb') as w:
                    w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000)
                    w.writeframes((audio[a:b].clip(-1,1)*32767).astype('<i2').tobytes())
                chunks.append({'file':str(p),'start':a/16000,'end':b/16000,'cache_key':digest+':'+str(a)+':'+str(b)})
        manifest.append({'label':label,'source':str(source),'sha256':digest,'chunks':chunks})
    job={'tracks':manifest,'model_root':section['model_root'],'output':str(work/'words.json'),'cache':str(work/'chunks.json'),'ffmpeg':section['ffmpeg']}
    jobpath=work/'job.json';jobpath.write_text(json.dumps(job,ensure_ascii=False,indent=2),'utf-8')
    print('Transcribing locally with GigaAM-v3 (offline worker).',flush=True)
    subprocess.run([section['python'],'-X','utf8','-B',str(Path(section.get('worker') or Path(__file__).with_name('gigaam_worker.py'))),'--job',str(jobpath)],check=True)
    rows=json.loads((work/'words.json').read_text('utf-8'))
    (session/'transcript.partial.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
    (session/'speech-engine.json').write_text(json.dumps({'engine':'gigaam-v3','model':'v3_e2e_rnnt','offline':True,'tracks':[{'source':t['source'],'sha256':t['sha256'],'chunks':len(t['chunks'])} for t in manifest]},ensure_ascii=False,indent=2),'utf-8')
    return rows
