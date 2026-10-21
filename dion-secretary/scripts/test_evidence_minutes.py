import copy,unittest
from evidence_minutes import turns_from_text,chunks,validate_fact,classify,deduplicate,build_minutes
class Tests(unittest.TestCase):
 def setUp(self):
  self.turns=turns_from_text('[00:00:05] **? Анна**: Я подготовлю отчёт завтра.\n[00:00:12] Борис: Документ пока не готов.')
  self.source={t['id']:t for t in self.turns}
  self.fact={'kind':'task','text':'Подготовить отчёт','owner':'Анна','deadline':'завтра','status':'confirmed',
   'evidence':[{'turn_id':'R00001','quote':'Я подготовлю отчёт завтра.'}]}
  self.check={'verdict':'supported','explicit_commitment':True,'owner_supported':True,'deadline_supported':True,'reason':''}
 def test_markdown_labels_and_times(self):
  self.assertEqual(self.turns[0]['speaker'],'? Анна');self.assertEqual(self.turns[1]['time'],'00:00:12')
 def test_fake_quote_cannot_pass(self):
  f=copy.deepcopy(self.fact);f['evidence'][0]['quote']='Борис оплатит счёт завтра'
  clean,reasons=validate_fact(f,self.source);self.assertIn('quote_not_in_source',reasons)
  self.assertFalse(classify(clean,self.check,reasons)['verified'])
 def test_unknown_turn_cannot_pass(self):
  f=copy.deepcopy(self.fact);f['evidence'][0]['turn_id']='R99999'
  self.assertIn('unknown_turn',validate_fact(f,self.source)[1])
 def test_uncertain_name_never_becomes_confident_owner(self):
  f,reasons=validate_fact(self.fact,self.source);out=classify(f,self.check,reasons)
  self.assertFalse(out['verified']);self.assertEqual(out['owner'],'не указан')
 def test_proposal_is_not_a_decision(self):
  f,reasons=validate_fact(self.fact,self.source);f.update(kind='decision',status='proposed')
  self.assertFalse(classify(f,self.check,reasons)['verified'])
 def test_description_is_not_a_task(self):
  f,reasons=validate_fact(self.fact,self.source);check={**self.check,'explicit_commitment':False}
  self.assertFalse(classify(f,check,reasons)['verified'])
 def test_unverified_deadline_is_cleared(self):
  f,reasons=validate_fact(self.fact,self.source);f['owner']='не указан'
  out=classify(f,{**self.check,'deadline_supported':False},reasons)
  self.assertEqual(out['deadline'],'не указан');self.assertFalse(out['verified'])
 def test_no_check_means_review(self):
  f,reasons=validate_fact(self.fact,self.source);self.assertFalse(classify(f,None,reasons)['verified'])
 def test_long_turns_preserve_all_words_and_bound_size(self):
  original='слово '*2000;parts=chunks([{'id':'R00001','time':'00:00:00','speaker':'А','text':original}])
  unique={t['id']:t for batch in parts for t in batch}
  self.assertEqual(' '.join(t['text'] for t in unique.values()).split(),original.split())
  self.assertTrue(all(len(t['text'])<=2200 for t in unique.values()))
 def test_missing_timestamp_is_explicit_failure(self):
  with self.assertRaises(ValueError):turns_from_text('plain text')
 def test_pipeline_keeps_citations_and_conflict_out_of_confirmed(self):
  text='[00:00:05] Анна: Решили провести тест в пятницу.\n[00:00:12] Борис: Решили отменить тест в пятницу.'
  def call(prompt,payload,schema):
   if 'facts' in schema['properties']:
    return {'facts':[{'kind':'decision','text':t['text'],'owner':'не указан','deadline':'не указан','status':('confirmed' if t['id']=='R00001' else 'cancelled'),
      'evidence':[{'turn_id':t['id'],'quote':t['text']}]} for t in self_turns]}
   if 'checks' in schema['properties']:
    return {'checks':[{'fact_id':f'F001-0{i+1}',**self.check} for i in range(2)]}
   return {'overview_ids':[],'conflicts':[{'ids':['F001-01','F001-02'],'reason':'Решение отменено позже'}]}
  self_turns=turns_from_text(text)
  markdown,report=build_minutes(text,call,'synthetic')
  self.assertEqual(report['verified'],0);self.assertEqual(report['review'],2)
  self.assertIn('R00001',markdown);self.assertIn('Требует проверки',markdown)
if __name__=='__main__':unittest.main()
