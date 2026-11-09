"""Synthetic recording startup checks; never opens a physical audio device."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import secretary


class FakeStream:
    def is_active(self): return True
    def stop_stream(self): pass
    def close(self): pass


class FakeAudio:
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def get_device_info_by_index(self, index):
        return {'maxInputChannels': 1, 'defaultSampleRate': 48000}
    def open(self, *, input_device_index, **_):
        if input_device_index == 2:
            raise OSError('synthetic microphone failure')
        return FakeStream()


class StartTests(unittest.TestCase):
    def test_missing_microphone_starts_remote_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = argparse.Namespace(title='Synthetic', mic=None, speaker=None, no_mic=False,
                                      meeting_journal=None)
            available = [{'index': 1, 'name': 'Synthetic output', 'loopback': True,
                          'default_output': True, 'default_mic': False}]
            commands = []
            def fake_popen(command, **_):
                commands.append(command)
                session = Path(command[command.index('--session') + 1])
                (session / 'status.json').write_text(json.dumps({'state': 'recording',
                    'microphone': 'unavailable', 'warnings': ['Microphone unavailable']}), 'utf-8')
                return types.SimpleNamespace(pid=1234, poll=lambda: None)
            with patch.object(secretary, 'SESSIONS', root), patch.object(secretary, 'ACTIVE', root / 'active.json'), \
                 patch.object(secretary, 'devices', return_value=available), \
                 patch.object(secretary, 'live_journals', return_value=[]), \
                 patch('meeting_autostop.select_binding', return_value=(None, None)), \
                 patch.object(secretary.subprocess, 'Popen', side_effect=fake_popen), \
                 patch.object(secretary, 'output') as output:
                secretary.start(args)
            self.assertIn('--no-mic', commands[0])
            self.assertTrue(args.no_mic)
            self.assertEqual(output.call_args.args[0]['microphone'], 'unavailable')
            session = next(root.iterdir())
            if session.name == 'active.json':
                session = next(path for path in root.iterdir() if path.is_dir())
            meta = json.loads((session / 'meta.json').read_text('utf-8'))
            self.assertIsNone(meta['mic'])
            self.assertIn('Microphone unavailable', meta['microphone_warning'])

    def test_microphone_open_failure_keeps_remote_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Path(folder)
            (session / 'meta.json').write_text(json.dumps({'title': 'Synthetic'}), 'utf-8')
            pa = types.ModuleType('pyaudiowpatch')
            pa.PyAudio = FakeAudio
            pa.paInt16 = 8
            pa.paContinue = 0
            pa.paAbort = 2
            monitor = types.ModuleType('meeting_autostop')
            monitor.MeetingMonitor = lambda _: types.SimpleNamespace(poll=lambda: None)
            monitor.REASONS = {'manual_stop': 'Stopped'}
            monitor.AUTO_STOP_REASONS = set()
            reminders = types.ModuleType('recording_reminders')
            reminders.RecordingReminders = lambda *_: types.SimpleNamespace(start=lambda: None, close=lambda: None)
            args = argparse.Namespace(session=str(session), speaker=1, mic=2, no_mic=False)
            def stop_after_tick(_): (session / 'stop.flag').touch()
            with patch.dict(sys.modules, {'pyaudiowpatch': pa, 'meeting_autostop': monitor,
                                          'recording_reminders': reminders}), \
                 patch.object(secretary, 'notify_microphone_issue') as notice, \
                 patch.object(secretary.time, 'sleep', side_effect=stop_after_tick):
                secretary.record(args)
            state = json.loads((session / 'status.json').read_text('utf-8'))
            self.assertEqual(state['state'], 'stopped')
            self.assertEqual(state['microphone'], 'unavailable')
            self.assertTrue((session / 'remote.wav').is_file())
            self.assertFalse((session / 'microphone.wav').exists())
            notice.assert_called_once()

    def test_failed_start_requests_prominent_alert(self):
        args = argparse.Namespace(title='Synthetic')
        with patch.object(secretary, 'start', side_effect=RuntimeError('synthetic failure')), \
             patch.object(secretary, 'alert_start_failure') as alert:
            with self.assertRaisesRegex(RuntimeError, 'synthetic failure'):
                secretary.start_with_alert(args)
            alert.assert_called_once()

    def test_alert_uses_persistent_dialog(self):
        with patch('recording_reminders.launch_notification') as launch:
            secretary.alert_start_failure('Synthetic', RuntimeError('synthetic failure'))
        self.assertTrue(launch.call_args.kwargs['prominent'])
        self.assertIn('не началась', launch.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
