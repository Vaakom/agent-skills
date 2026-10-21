import tempfile,unittest
from pathlib import Path
from meeting_links import find_previous,link_note
class Tests(unittest.TestCase):
 def note(self,folder,date,title):
  p=folder/(date+'_'+title+'.md');p.write_text('# '+title+'\n\nBody\n','utf-8');return p
 def test_exact_uses_latest_older_and_links_once(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.note(p,'2026-10-10_10-00-00','Проект Альфа');old=self.note(p,'2026-10-12_10-00-00','Проект Альфа')
   new=self.note(p,'2026-10-13_10-00-00','Проект Альфа');self.note(p,'2026-10-14_10-00-00','Проект Альфа')
   self.assertEqual(link_note(new,'Проект Альфа')['previous']['path'],str(old))
   link_note(new,'Проект Альфа');self.assertEqual(new.read_text('utf-8').count('## Связь встреч'),1)
 def test_similar_requires_confirmation_and_does_not_write(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.note(p,'2026-10-12_10-00-00','Проект Альфа');new=self.note(p,'2026-10-13_10-00-00','Проект Альфа!')
   before=new.read_bytes();self.assertEqual(link_note(new,'Проект Альфа!')['state'],'confirmation_required')
   self.assertEqual(new.read_bytes(),before)
 def test_unrelated_title_not_linked(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.note(p,'2026-10-12_10-00-00','Бюджет');new=self.note(p,'2026-10-13_10-00-00','Проект Альфа')
   self.assertEqual(find_previous(new,'Проект Альфа')['state'],'no_previous')
 def test_transcript_is_not_a_previous_meeting(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);self.note(p,'2026-10-12_10-00-00','Проект Альфа — стенограмма');new=self.note(p,'2026-10-13_10-00-00','Проект Альфа')
   self.assertEqual(find_previous(new,'Проект Альфа')['state'],'no_previous')
if __name__=='__main__':unittest.main()
