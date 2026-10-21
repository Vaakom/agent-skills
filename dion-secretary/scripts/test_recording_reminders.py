import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from recording_reminders import RecordingReminders, next_deadline


class ReminderTests(unittest.TestCase):
    def test_hour_and_half_hour_boundaries(self):
        for elapsed, expected in [(0, 3600), (3599, 3600), (3600, 5400),
                                  (5399, 5400), (5400, 7200), (15000, 16200)]:
            self.assertEqual(next_deadline(elapsed), expected)

    def test_repeats_with_exact_title_then_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            seen = []
            ready = threading.Event()
            def notify(message):
                seen.append(message)
                if len(seen) == 2:
                    ready.set()
            reminders = RecordingReminders(folder, 'Название "А"; $test', time.monotonic(),
                                           first=.03, interval=.05, notifier=notify)
            reminders.start()
            self.assertTrue(ready.wait(2))
            reminders.close()
            reminders.thread.join(1)
            self.assertEqual(seen, ['Встреча "Название "А"; $test" ещё записывается'] * 2)
            self.assertFalse(reminders.thread.is_alive())

    def test_stop_flag_suppresses_notifications(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'stop.flag').touch()
            seen = []
            reminders = RecordingReminders(folder, 'Тест', time.monotonic(),
                                           first=.01, notifier=seen.append)
            reminders.start()
            reminders.thread.join(1)
            self.assertEqual(seen, [])
            self.assertFalse(reminders.thread.is_alive())

    def test_backend_error_logged_without_crashing(self):
        with tempfile.TemporaryDirectory() as folder:
            def fail(message):
                raise OSError('Desktop unavailable')
            reminders = RecordingReminders(folder, 'Тест', time.monotonic(),
                                           first=.01, notifier=fail)
            reminders.start()
            log = Path(folder) / 'recording-reminders.jsonl'
            deadline = time.monotonic() + 2
            while not log.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            reminders.close()
            reminders.thread.join(1)
            event = json.loads(log.read_text('utf-8'))
            self.assertEqual(event['state'], 'error')
            self.assertIn('Desktop unavailable', event['error'])


if __name__ == '__main__':
    unittest.main()
