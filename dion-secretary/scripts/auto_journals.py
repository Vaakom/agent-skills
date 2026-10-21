"""Select independent browser journals by recording time; never silently mix meetings."""
import json,datetime as dt,wave
from pathlib import Path
DEFAULT_ROOT=Path(__file__).resolve().parents[3] / 'products' / 'dion-speaker-helper' / 'runtime' / 'journals'

def prepare_journal(session,root=DEFAULT_ROOT,choice=None):
    session=Path(session);root=Path(root)
    destination=session/'browser-speakers.jsonl'
    if destination.exists() and not choice:
        return {'state':'existing_session_journal','path':str(destination)}
    report={'state':'no_matching_journal','candidates':[]}
    try:
        clock=json.loads((session/'recording_clock.json').read_text('utf-8'))
        origin=clock['remote_monotonic']
        created=dt.datetime.fromisoformat(json.loads((session/'meta.json').read_text('utf-8'))['created']).timestamp()
        boot=created-origin
        with wave.open(str(session/'remote.wav'),'rb') as wav:
            length=wav.getnframes()/wav.getframerate()
    except (OSError,KeyError,ValueError,wave.Error) as exc:
        report.update(state='missing_recording_clock',error=str(exc))
        (session/'speaker-journal-source.json').write_text(json.dumps(report,indent=2),'utf-8')
        return report
    selected=None
    if choice:
        selected=Path(choice).resolve()
        if not selected.is_relative_to(root.resolve()):raise ValueError('Journal selection outside journal root')
        if selected.name=='events.jsonl':selected=selected.parent
    groups={}
    for meta_path in sorted(root.glob('*/*/meta.json')):
        try:
            meta=json.loads(meta_path.read_text('utf-8'))
            if abs(meta['boot_epoch']-boot)>300:continue
            events=[]
            for line in (meta_path.parent/'events.jsonl').read_text('utf-8').splitlines():
                try:e=json.loads(line)
                except ValueError:continue # A concurrent final partial write is not evidence.
                if origin<=e['monotonic']<=origin+length:
                    events.append(e)
            if not events:continue
            key=(meta['client'],meta['tab'],meta['meeting_id'])
            group=groups.setdefault(key,{'meeting_id':meta['meeting_id'],'tab':meta['tab'],
                'title':meta.get('title','DION'),'paths':[],'events':[]})
            group['paths'].append(str(meta_path.parent.resolve()));group['events'].extend(events)
        except (OSError,ValueError,KeyError,TypeError):continue
    valid=[]
    for group in groups.values():
        if selected and str(selected) not in group['paths']:continue
        valid.append(group)
    report['candidates']=[{k:v for k,v in g.items() if k!='events'} for g in groups.values()]
    if len(valid)==1:
        group=valid[0]
        rows=[];seen=set()
        for event in sorted(group['events'],key=lambda e:e['monotonic']):
            seconds=round(event['monotonic']-origin,4)
            if seconds in seen:continue
            seen.add(seconds)
            rows.append({**event,'seconds':seconds})
        destination.write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in rows),'utf-8')
        report.update(state='imported',selected=group['paths'],samples=len(rows))
    elif len(valid)>1:report['state']='multiple_meetings_select_required'
    elif selected:report['state']='selected_journal_has_no_recording_overlap'
    (session/'speaker-journal-source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    return report

def live_journals(root=DEFAULT_ROOT):
    import time
    active=[]
    for path in Path(root).glob('*/*/meta.json'):
        try:
            meta=json.loads(path.read_text('utf-8'))
            if time.time()-meta.get('last_at',0)>5:continue
            if meta.get('ended_at',0)>=meta.get('last_at',0):continue
            active.append({'title':meta.get('title','DION'),'tab':meta['tab'],
                           'path':str(path.parent),'last_at':meta['last_at']})
        except (OSError,ValueError,KeyError,TypeError):continue
    return {'state':'active' if active else 'no_current_journal','count':len(active),'meetings':active}
