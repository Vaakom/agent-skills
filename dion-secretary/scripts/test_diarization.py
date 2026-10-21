import unittest
from diarization import annotate,merge_words,UNKNOWN

class AttributionTests(unittest.TestCase):
    def test_switch_overlap_gap_and_me(self):
        turns=[{'start':0,'end':2,'speaker':7},{'start':2,'end':4,'speaker':3},
               {'start':5,'end':7,'speaker':7},{'start':5,'end':7,'speaker':3},
               {'start':8,'end':10,'speaker':7}]
        spans=[(0.2,0.7),(2.2,2.7),(5.2,5.7),(7.2,7.7),(8.2,8.7),(1.8,2.2)]
        rows=[{'start':a,'end':b,'speaker':'Участники','text':'слово'} for a,b in spans]
        result=annotate(rows,turns)
        self.assertEqual([r['speaker'] for r in result],['Спикер 1','Спикер 2',UNKNOWN,UNKNOWN,'Спикер 1',UNKNOWN])
        mine=annotate([{'start':5,'end':6,'speaker':'Я','text':'мой текст'}],turns)
        self.assertEqual(mine[0]['speaker'],'Я')
    def test_nested_overlap(self):
        turns=[{'start':0,'end':100,'speaker':0},{'start':1,'end':2,'speaker':1},{'start':50,'end':60,'speaker':1}]
        result=annotate([{'start':50.1,'end':50.5,'speaker':'Участники','text':'тест'}],turns)
        self.assertEqual(result[0]['speaker'],UNKNOWN)
    def test_merge_preserves_text_and_turns(self):
        rows=[{'start':0,'end':1,'speaker':'Спикер 1','text':'Один'},
              {'start':1,'end':2,'speaker':'Спикер 1','text':'два'},
              {'start':2,'end':3,'speaker':'Спикер 2','text':'три'}]
        merged=merge_words(rows)
        self.assertEqual(len(merged),2)
        self.assertEqual(merged[0]['text'],'Один два')
        self.assertEqual(merged[1]['speaker'],'Спикер 2')
    def test_no_speech(self):
        result=annotate([{'start':0,'end':1,'speaker':'Участники','text':'тест'}],[])
        self.assertEqual(result[0]['speaker'],UNKNOWN)
if __name__=='__main__':unittest.main()
