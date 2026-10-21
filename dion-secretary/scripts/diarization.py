"""Local speaker diarization worker and conservative word attribution."""
import argparse
from bisect import bisect_left, bisect_right
import json
from pathlib import Path
import subprocess
import tempfile

UNKNOWN = 'Неопределённый спикер'


def annotate(rows, turns):
    ordered = sorted(turns, key=lambda t: (t['start'], t['end']))
    labels = {}
    for turn in ordered:
        if turn['speaker'] not in labels:
            labels[turn['speaker']] = 'Спикер ' + str(len(labels)+1)
    starts = [t['start'] for t in ordered]
    prefix_ends = []
    for turn in ordered:
        prefix_ends.append(max(turn['end'], prefix_ends[-1] if prefix_ends else 0))
    result = []
    for row in rows:
        if row['speaker'] == 'Я':
            result.append(dict(row))
            continue
        scores = {}
        # Include earlier overlapping turns, including simultaneous speech.
        right = bisect_left(starts, row['end'])
        left = bisect_right(prefix_ends, row['start'])
        for turn in ordered[left:right]:
            overlap = max(0, min(row['end'],turn['end'])-max(row['start'],turn['start']))
            if overlap:
                speaker=turn['speaker'];scores[speaker]=scores.get(speaker,0)+overlap
        duration=row['end']-row['start']
        ranking=sorted(scores,key=scores.get,reverse=True)
        best=ranking[0] if ranking else None
        coverage=min(1,scores.get(best,0)/duration) if duration>0 else 0
        competing=scores.get(ranking[1],0)/duration if len(ranking)>1 and duration>0 else 0
        confirmed=best is not None and coverage>=0.60 and competing<0.20
        result.append({**row,'speaker':labels[best] if confirmed else UNKNOWN,
                       'speaker_evidence':{'method':'local_voice_clustering','coverage':round(coverage,3),
                                           'overlap':round(competing,3),'status':'assigned' if confirmed else 'uncertain'}})
    return result


def merge_words(rows):
    merged=[]
    for row in rows:
        if merged and merged[-1]['speaker']==row['speaker'] and row['start']-merged[-1]['end']<=0.8 and row['end']-merged[-1]['start']<=20:
            merged[-1]['text']+=' '+row['text']
            merged[-1]['end']=max(merged[-1]['end'],row['end'])
        else:
            merged.append({k:row[k] for k in ('start','end','speaker','text')})
    return merged


def run_worker(source, session, config, num_speakers=-1):
    settings=config['diarization']
    if num_speakers not in (-1,) and num_speakers<1:
        raise ValueError('Number of speakers must be positive.')
    for key in ('python','segmentation_model','embedding_model','ffmpeg'):
        if not Path(settings[key]).is_file():
            raise RuntimeError('Missing local diarization dependency: '+key)
    source=Path(source).resolve()
    destination=Path(session)/'diarization.json'
    identity={'source':str(source),'size':source.stat().st_size,'mtime_ns':source.stat().st_mtime_ns,
              'worker_version':2,'window_shift_ratio':0.1,'num_speakers':num_speakers,'threshold':settings['threshold'],
              'segmentation_model':settings['segmentation_model'],'embedding_model':settings['embedding_model']}
    if destination.exists():
        saved=json.loads(destination.read_text('utf-8'))
        if saved.get('identity')==identity:
            return saved['turns']
    args=[settings['python'],str(Path(__file__).resolve()),'--source',str(source),
          '--output',str(destination),'--segmentation-model',settings['segmentation_model'],
          '--embedding-model',settings['embedding_model'],'--ffmpeg',settings['ffmpeg'],
          '--num-speakers',str(num_speakers),'--threshold',str(settings['threshold'])]
    subprocess.run(args,check=True)
    data=json.loads(destination.read_text('utf-8'))
    data['identity']=identity
    destination.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    return data['turns']


def worker(args):
    import numpy as np
    import sherpa_onnx
    import soundfile as sf
    config=sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=args.segmentation_model,window_shift_ratio=0.1),
            num_threads=4,provider='cpu'),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=args.embedding_model,num_threads=4,provider='cpu'),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=args.num_speakers,threshold=args.threshold),
        min_duration_on=0.3,min_duration_off=0.5)
    if not config.validate(): raise RuntimeError('Invalid local diarization configuration.')
    diarizer=sherpa_onnx.OfflineSpeakerDiarization(config)
    with tempfile.TemporaryDirectory(prefix='diarization-',dir=Path(args.output).parent) as folder:
        audio=Path(folder)/'mono.wav'
        subprocess.run([args.ffmpeg,'-hide_banner','-loglevel','error','-i',args.source,
                        '-vn','-ac','1','-ar',str(diarizer.sample_rate),'-c:a','pcm_s16le',str(audio)],check=True)
        samples,rate=sf.read(str(audio),dtype='float32')
        if rate!=diarizer.sample_rate: raise RuntimeError('Wrong audio sample rate.')
        last=[-10]
        def progress(done,total):
            percent=int(done*100/max(1,total))
            if percent>=last[0]+10:
                print(f'Local diarization: {percent}%',flush=True);last[0]=percent
            return 0
        if len(samples)==0 or float(np.max(np.abs(samples)))<0.0001:
            turns=[]
        else:
            turns=[{'start':float(t.start),'end':float(t.end),'speaker':int(t.speaker)}
                   for t in diarizer.process(samples,callback=progress).sort_by_start_time()]
    Path(args.output).write_text(json.dumps({'turns':turns},ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'local_diarization':'complete','speakers':len({t['speaker'] for t in turns}),
                      'turns':len(turns),'file':args.output}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('source','output','segmentation-model','embedding-model','ffmpeg'):
        parser.add_argument('--'+key,required=True)
    parser.add_argument('--num-speakers',type=int,default=-1)
    parser.add_argument('--threshold',type=float,default=0.4)
    worker(parser.parse_args())
