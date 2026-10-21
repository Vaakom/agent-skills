"""Attribute words solely from the selected DION tab journal, never from voice identity."""
import json, math
from collections import Counter, defaultdict
from pathlib import Path
UNKNOWN = 'Неизвестный спикер'

def apply_names(rows, session, turns=None):
    session = Path(session)
    report = {'schema':3,'method':'browser_only','named_words':0,'uncertain_words':0,
              'unknown_words':0,'reasons':{},'state':'complete',
              'limitation':'Hidden simultaneous speech, noise and UI lag cannot always be detected from DION.'}
    reasons = Counter()
    samples = []
    path = session/'browser-speakers.jsonl'
    try:
        if path.exists():
            for line in path.read_text('utf-8').splitlines():
                s = json.loads(line)
                if not isinstance(s,dict): raise ValueError('Invalid sample')
                t, names = s.get('seconds'),s.get('speakers')
                if (not isinstance(t,(int,float)) or not math.isfinite(t) or t<0
                    or not isinstance(names,list) or len(names)>30
                    or any(not isinstance(n,str) or not n.strip() or len(n)>160 or any(c in n for c in '\r\n\x00') for n in names)):
                    raise ValueError('Invalid sample')
                if samples and t<=samples[-1]['seconds']: raise ValueError('Non-increasing journal time')
                samples.append(s)
        else:report['state']='missing_journal'
    except (ValueError,OSError,TypeError) as exc:
        samples=[];report.update(state='invalid_journal',error=str(exc))
    intervals=[]
    transitions=[]
    for a,b in zip(samples,samples[1:]):
        start,end=a['seconds'],b['seconds']
        if b.get('speakers')!=a.get('speakers'):
            transitions.append(end)
        if end-start>1.5 or a.get('state')!='observing':continue
        intervals.append((start,end,a))
    # Do not extend the final observation beyond its actual timestamp.
    try:
        clock=json.loads((session/'recording_clock.json').read_text('utf-8'))
        mic_offset=clock['microphone_monotonic']-clock['remote_monotonic']
        if not math.isfinite(mic_offset):mic_offset=0
    except (OSError,ValueError,KeyError,TypeError):mic_offset=0
    result=[]
    for row in rows:
        offset=mic_offset if row['speaker']=='Я' else 0
        a,b=row['start']+offset,row['end']+offset
        length=b-a
        scores=defaultdict(float);flags=set();coverage=0
        midpoint_names=[]
        for c,d,s in intervals:
            value=max(0,min(b,d)-max(a,c))
            if not value:continue
            names=s['speakers']
            if not names:continue
            coverage+=value
            for name in names:scores[name]+=value
            if c<= (a+b)/2 <d:midpoint_names=names
            if len(names)>1:flags.add('multiple_active_names')
            if s.get('calibrated') is not True:flags.add('unverified_profile')
        if not scores or length<=0:
            name=UNKNOWN;flags.add('missing_browser_name');report['unknown_words']+=1
        else:
            ranked=sorted(scores,key=lambda n:(-scores[n],n))
            name=next((n for n in midpoint_names if n in scores),ranked[0])
            if len(scores)>1:flags.add('speaker_change_inside_word')
            if coverage/length < .95:flags.add('partial_browser_coverage')
            if any(a-.75<=t<=b+.75 for t in transitions):flags.add('near_indicator_change')
            if flags:
                name='? '+name;report['uncertain_words']+=1
            report['named_words']+=1
        reasons.update(flags)
        result.append({**row,'start':a,'end':b,'speaker':name,'speaker_evidence':{
            'method':'browser_only','status':'unknown' if name==UNKNOWN else 'uncertain' if flags else 'observed',
            'reasons':sorted(flags),'previous_label':row['speaker'],
            'coverage':round(min(1,coverage/length),3) if length>0 else 0}})
    result.sort(key=lambda r:r['start'])
    report['reasons']=dict(reasons)
    (session/'speaker-name-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    return result
