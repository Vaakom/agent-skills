"""Offline speech recognition worker used by Dion Secretary."""
import argparse,json,os,socket
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--job',required=True);args=parser.parse_args()
job=json.loads(Path(args.job).read_text('utf-8'))
os.environ['PATH']=str(Path(job['ffmpeg']).parent)+os.pathsep+os.environ['PATH']
def no_network(*args,**kwargs):raise RuntimeError('Network is disabled in the GigaAM transcription worker')
socket.create_connection=no_network
socket.socket.connect=no_network
import torch
torch.set_num_threads(6)
from gigaam_loader import load
model=load(job['model_root'],offline=True)
cachepath=Path(job['cache'])
saved=json.loads(cachepath.read_text('utf-8')) if cachepath.exists() else {}
rows=[]
for track in job['tracks']:
    for i,chunk in enumerate(track['chunks']):
        key=chunk['cache_key']
        if key not in saved:
            result=model.transcribe(chunk['file'],word_timestamps=True)
            saved[key]={'text':result.text,'words':[{'start':w.start,'end':w.end,'text':w.text} for w in (result.words or [])]}
            tmp=cachepath.with_suffix('.tmp');tmp.write_text(json.dumps(saved,ensure_ascii=False,indent=2),'utf-8');tmp.replace(cachepath)
        result=saved[key]
        for w in result['words']:
            rows.append({'start':chunk['start']+w['start'],'end':chunk['start']+w['end'],'speaker':track['label'],'text':w['text']})
        if result['text'] and not result['words']:
            rows.append({'start':chunk['start'],'end':chunk['end'],'speaker':track['label'],'text':result['text']})
        print(json.dumps({'engine':'gigaam-v3','track':track['label'],'chunk':i+1,'total':len(track['chunks'])},ensure_ascii=False),flush=True)
rows.sort(key=lambda r:r['start'])
Path(job['output']).write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps({'state':'complete','engine':'gigaam-v3','words':len(rows),'offline':True}),flush=True)
