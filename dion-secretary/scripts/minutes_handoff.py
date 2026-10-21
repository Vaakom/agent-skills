"""Persist summary work and finalize only against the unchanged source."""
import datetime as dt
import hashlib,json,shutil
from pathlib import Path
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def prepare(transcript,target,title,created,session,provider='codex'):
    if provider not in ('codex','local'):raise ValueError('Unknown minutes provider')
    transcript=Path(transcript).resolve();target=Path(target).resolve()
    data={'state':'awaiting_'+provider,'provider':provider,'transcript':str(transcript),
        'source_sha256':digest(transcript),'protocol':str(target),'title':title,
        'created':created,'session':str(session)}
    path=Path(session)/'minutes-handoff.json'
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    return path,data
def finalize(handoff,draft,linker):
    handoff=Path(handoff)
    data=json.loads(handoff.read_text('utf-8'))
    if digest(data['transcript'])!=data['source_sha256']:raise RuntimeError('Transcript changed; prepare a fresh summary handoff.')
    body=Path(draft).read_text('utf-8').strip()
    if not body:raise ValueError('Empty summary; existing note retained.')
    note=Path(data['protocol']);note.parent.mkdir(parents=True,exist_ok=True)
    header='# '+data['title']+'\n\nДата: '+data['created']+'\n\n'
    if data['provider'] == 'local': header += 'Резюме: local\n\n'
    content=header+body+'\n\n[['+Path(data['transcript']).stem+']]\n\nИсходные файлы: '+data['session']+'\n'
    if note.exists():
        stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        shutil.copy2(note,note.with_name(note.name+'.'+stamp+'.bak'))
    tmp=note.with_suffix('.tmp');tmp.write_text(content,'utf-8');tmp.replace(note)
    link=linker(note,data['title'])
    data.update(state='complete',meeting_link=link)
    handoff.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    return data
