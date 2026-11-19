import json
from pathlib import Path
import tempfile
import unittest
from installation_versions import versions_report

class VersionTests(unittest.TestCase):
    def test_source_is_not_activation_and_only_fresh_evidence_counts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);ext=p/'extension';ext.mkdir()
            (ext/'manifest.json').write_text(json.dumps({'version':'0.8.0'}))
            cfg={'speaker_helper_extension_path':str(ext)}
            self.assertEqual(versions_report(cfg,p,100)['state'],'unknown')
            journal=p/'day'/'room';journal.mkdir(parents=True)
            m={'last_at':99,'tab':1,'versions':{'extension':'0.7.6','host':'0.8.0','protocol':2}}
            (journal/'meta.json').write_text(json.dumps(m))
            row=versions_report(cfg,p,100)['active_observations'][0]
            self.assertTrue(row['reload_required']);self.assertFalse(row['compatible'])
            self.assertEqual(versions_report(cfg,p,110)['state'],'unknown')
            m['versions']={};(journal/'meta.json').write_text(json.dumps(m))
            row=versions_report(cfg,p,100)['active_observations'][0]
            self.assertIsNone(row['reload_required']);self.assertIsNone(row['compatible'])

if __name__=='__main__':unittest.main()
