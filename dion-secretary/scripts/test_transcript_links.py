from pathlib import Path
import tempfile
import unittest
from transcript_links import anchor_transcript, link_timestamps
from minutes_handoff import prepare, finalize


class TranscriptLinksTests(unittest.TestCase):
    def test_unique_blocks_and_idempotence(self):
        source = '# Test\n\n[00:00:01] **A**: One\n[00:00:01] **B**: Two\n[00:01:10] **A**: Three\n'
        anchored = anchor_transcript(source)
        self.assertIn('One ^t-00-00-01\n\n', anchored)
        self.assertIn('Two ^t-00-00-01-2', anchored)
        self.assertEqual(anchor_transcript(anchored), anchored)

    def test_ranges_nearest_prior_and_existing_links(self):
        transcript = anchor_transcript('[00:00:01] A: One\n[00:01:10] A: Two')
        body = '[00:00:00–00:00:09] First. [00:01:12] Second. `code [00:01:12]` [[Other|00:01:12]]'
        linked = link_timestamps(body, transcript, 'Transcript.md')
        self.assertIn('Transcript.md#^t-00-00-01|00:00:00–00:00:09', linked)
        self.assertIn('Transcript.md#^t-00-01-10|00:01:12', linked)
        self.assertIn('`code [00:01:12]` [[Other|00:01:12]]', linked)
        self.assertEqual(link_timestamps(linked, transcript, 'Transcript.md'), linked)

    def test_table_alias_pipe_is_escaped(self):
        linked = link_timestamps('| Task | [00:00:01] |', anchor_transcript('[00:00:01] A: One'), 'Transcript.md')
        self.assertIn(r'Transcript.md#^t-00-00-01\|00:00:01', linked)

    def test_handoff_hash_protection_and_backups(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            transcript = root/'Transcript.md'; transcript.write_text('[00:00:01] A: One', 'utf-8')
            note = root/'Minutes.md'; note.write_text('Previous minutes', 'utf-8')
            draft = root/'draft.md'; draft.write_text('Decision [00:00:01]', 'utf-8')
            handoff, data = prepare(transcript, note, 'Meeting', 'Date', root)
            self.assertTrue(list(root.glob('Transcript.md.*.bak')))
            finalize(handoff, draft, lambda *args: {})
            self.assertIn('Transcript.md#^t-00-00-01|00:00:01', note.read_text('utf-8'))
            self.assertTrue(list(root.glob('Minutes.md.*.bak')))
            transcript.write_text(transcript.read_text('utf-8')+'Changed', 'utf-8')
            with self.assertRaises(RuntimeError):
                finalize(handoff, draft, lambda *args: {})


if __name__ == '__main__':
    unittest.main()
