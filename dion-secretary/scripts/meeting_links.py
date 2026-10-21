"""Link a new meeting note to the latest older note with the same title."""
import datetime as dt,difflib,re
from pathlib import Path
STAMP=re.compile(r'^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_')
def find_previous(note,title):
    note=Path(note);match=STAMP.match(note.name)
    if not match:return {'state':'no_date','candidates':[]}
    current=match[1];exact=[];near=[]
    for path in note.parent.glob('*.md'):
        if path==note:continue
        date=STAMP.match(path.name)
        if not date or date[1]>=current:continue
        with path.open(encoding='utf-8') as stream:first=stream.readline().strip()
        if not first.startswith('# '):continue
        candidate=first[2:].strip()
        # Derivative documents are not separate meetings.
        if any(candidate.endswith(suffix) for suffix in [' — стенограмма',' — резюме с основаниями']):continue
        item={'path':str(path),'title':candidate,'date':date[1]}
        if candidate==title:exact.append(item);continue
        a,b=title.casefold(),candidate.casefold()
        ratio=difflib.SequenceMatcher(None,a,b).ratio()
        threshold=.9 if min(len(a),len(b))<6 else .82
        if ratio>=threshold:near.append({**item,'similarity':round(ratio,3)})
    if exact:return {'state':'linked','previous':max(exact,key=lambda item:item['date'])}
    if near:return {'state':'confirmation_required','candidates':sorted(near,key=lambda item:(item['similarity'],item['date']),reverse=True)[:5]}
    return {'state':'no_previous','candidates':[]}
def link_note(note,title):
    note=Path(note);result=find_previous(note,title)
    if result['state']=='linked':
        text=note.read_text('utf-8')
        section='\n\n## Связь встреч\n\nПредыдущая встреча: [['+Path(result['previous']['path']).stem+']]\n'
        if '## Связь встреч' not in text:note.write_text(text.rstrip()+section,'utf-8')
    return result
