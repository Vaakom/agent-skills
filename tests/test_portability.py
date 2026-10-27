"""Installation and summary behavior on synthetic, external paths."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import auto_journals
import local_minutes
import secretary
import youtube_library

ROOT = Path(__file__).resolve().parents[1]


class PortabilityTests(unittest.TestCase):
    def test_configuration_requires_absolute_paths_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            for name in ('configure.py', 'config.example.json'):
                shutil.copy2(ROOT / 'dion-secretary' / name, work / name)
            spec = importlib.util.spec_from_file_location('configure_fixture', work / 'configure.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            args = SimpleNamespace(**{key: str(work / key) for key in
                                      ('runtime', 'downloads', 'sessions', 'notes', 'journal_root')})
            args.runtime = 'relative/runtime'
            with self.assertRaises(ValueError):
                module.configure(args)
            self.assertFalse((work / 'config.json').exists())
            args.runtime = str(work / 'runtime')
            target = module.configure(args)
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                module.configure(args)
            self.assertEqual(target.read_bytes(), original)
            data = json.loads(original)
            self.assertEqual(data['minutes_provider'], 'codex')
            self.assertEqual(data['speech_engine'], 'whisper')
            self.assertNotIn('minutes_product', data)

    def test_configured_journal_root_is_used_before_capture(self):
        # Inspect journal routing, then stop before any physical audio lookup.
        with tempfile.TemporaryDirectory() as folder:
            journal_root = str(Path(folder) / 'journals')
            with patch.dict(secretary.CONFIG, {'journal_root': journal_root}), \
                 patch.object(secretary, 'ACTIVE', Path(folder) / 'active.json'), \
                 patch.object(auto_journals, 'live_journals', return_value={'meetings': []}) as journals, \
                 patch.object(secretary, 'devices', side_effect=RuntimeError('synthetic capture boundary')) as devices:
                with self.assertRaisesRegex(RuntimeError, 'synthetic capture boundary'):
                    secretary.start(SimpleNamespace(meeting_journal=None))
                journals.assert_called_once_with(root=journal_root)
                devices.assert_called_once_with()

    def test_local_pipeline_runs_without_a_products_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            def call(prompt, payload, schema):
                calls.append(payload)
                return {'facts': []}
            body, report = local_minutes.build_minutes(
                '[00:00:01] **User**: Synthetic greeting.', call, 'synthetic-model', Path(folder))
            self.assertTrue(body)
            self.assertEqual(len(calls), 1)
            self.assertEqual(report['final_facts'], 0)

    def test_youtube_fresh_clone_requires_explicit_paths(self):
        # Pretend the local config is absent; no request or output folder is touched.
        with patch.object(youtube_library, 'read_json', return_value={}), \
             patch('sys.argv', ['youtube_library.py', 'sync']), \
             patch.object(youtube_library, 'access_token', side_effect=AssertionError('Account accessed')):
            with self.assertRaises(SystemExit) as error:
                youtube_library.main()
            self.assertEqual(error.exception.code, 2)
