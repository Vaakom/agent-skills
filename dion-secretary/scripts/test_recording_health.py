"""Synthetic health checks; no physical devices or real meeting sources."""
import tempfile
from pathlib import Path
import unittest
import wave
from recording_health import AudioHealth, inspect_wavs, journal_diagnostic, sample_coverage, render_recording_summary

class HealthTests(unittest.TestCase):
    def test_silent_pcm_is_data_and_counts_multichannel_bytes(self):
        h = AudioHealth(0)
        h.register('remote', 100, 2)
        h.received('remote', 400, 1)
        s = h.snapshot(1)['remote']
        self.assertEqual(s['frames'], 100)
        self.assertEqual(s['audio_seconds'], 1)
        self.assertEqual(s['state'], 'receiving')

    def test_coverage_does_not_bridge_gaps_or_double_count_duplicates(self):
        events = [dict(monotonic=t, state='observing', speakers=['Synthetic']) for t in (0, .5, .5, 1, 10)]
        r = sample_coverage(events, 0, 10)
        self.assertEqual(r['observed_seconds'], 1)
        self.assertEqual(r['named_indicator_seconds'], 1)
        self.assertEqual(r['observed_fraction'], .1)

    def test_summary_keeps_missing_audio_and_pending_processing_explicit(self):
        report={'tracks':{'remote':{'state':'short','audio_seconds':60,'missing_seconds':30},
                          'microphone':{'state':'absent'}},'journal':{'coverage':'unknown'}}
        text=render_recording_summary(report)
        self.assertIn('60.0',text)
        self.assertIn('неполная',text)
        self.assertIn('дорожка отсутствует',text)
        self.assertIn('обработка выполняется отдельно',text)

    def test_no_callbacks_and_stale_callbacks(self):
        h = AudioHealth(0)
        h.register('remote', 100, 1)
        self.assertEqual(h.snapshot(4)['remote']['state'], 'waiting')
        self.assertEqual(h.snapshot(5)['remote']['state'], 'no_data')
        h.received('remote', 200, 6)
        self.assertEqual(h.snapshot(11)['remote']['state'], 'stalled')

    def test_fresh_callback_does_not_hide_missing_duration(self):
        h = AudioHealth(0)
        h.register('remote', 100, 1)
        h.received('remote', 200, 1)
        h.received('remote', 200, 20)
        self.assertEqual(h.snapshot(20)['remote']['state'], 'duration_gap')

    def test_slow_device_start_is_not_missing_audio(self):
        h = AudioHealth(0)
        h.register('remote', 100, 1)
        h.received('remote', 200, 20)
        self.assertEqual(h.snapshot(20)['remote']['missing_seconds'], 0)

    def test_final_headers_detect_short_empty_and_corrupt_files(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            with wave.open(str(p/'remote.wav'), 'wb') as w:
                w.setparams((1, 2, 100, 0, 'NONE', 'not compressed'))
                w.writeframes(bytes(200))
            r = inspect_wavs(p, 100)
            self.assertEqual(r['tracks']['remote']['audio_seconds'], 1)
            self.assertFalse(r['complete_remote'])
            self.assertEqual(r['tracks']['microphone']['state'], 'absent')
            with wave.open(str(p/'microphone.wav'), 'wb') as w:
                w.setparams((1, 2, 100, 0, 'NONE', 'not compressed'))
            self.assertEqual(inspect_wavs(p, 1)['tracks']['microphone']['state'], 'empty')
            (p/'remote.wav').write_bytes(b'broken')
            self.assertEqual(inspect_wavs(p, 1)['tracks']['remote']['state'], 'unreadable')

    def test_journal_binding_does_not_claim_name_coverage(self):
        self.assertEqual(journal_diagnostic(None)['coverage'], 'unknown')
        self.assertEqual(journal_diagnostic({'lifecycle_path':'nonexistent'})['state'], 'unavailable')

if __name__ == '__main__':
    unittest.main()
