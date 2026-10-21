"""Run offline synthetic checks using a temporary configuration and stubbed ASR."""
import ast
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def unavailable(*args, **kwargs):
    raise AssertionError('Real speech recognition is forbidden in synthetic checks')


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    sys.dont_write_bytecode = True
    for folder in ('dion-secretary/scripts', 'youtube-library/scripts', 'mesh-homework/scripts', 'tests'):
        sys.path.insert(0, str(ROOT / folder))
    # Tests replace each inference call; the stub keeps the suite dependency-free.
    asr = types.ModuleType('faster_whisper')
    asr.WhisperModel = unavailable
    sys.modules['faster_whisper'] = asr
    for name, members in {'audio': ('decode_audio',), 'vad': ('get_speech_timestamps', 'VadOptions')}.items():
        module = types.ModuleType('faster_whisper.' + name)
        for member in members:
            setattr(module, member, unavailable)
        sys.modules[module.__name__] = module
    with tempfile.TemporaryDirectory(prefix='agent-skills-checks-') as temporary:
        work = Path(temporary)
        config = json.loads((ROOT / 'dion-secretary/config.example.json').read_text('utf-8'))
        for key in ('runtime', 'downloads', 'sessions', 'notes', 'journal_root', 'speech_model_dir', 'ollama_model_dir'):
            config[key] = str(work / key)
        config_file = work / 'config.json'
        config_file.write_text(json.dumps(config), 'utf-8')
        os.environ['DION_SECRETARY_CONFIG'] = str(config_file)
        suite = unittest.TestSuite()
        loader = unittest.TestLoader()
        for name in ('test_diarization', 'test_evidence_minutes', 'test_meeting_links',
                     'test_recording_reminders', 'test_minutes_modes', 'test_youtube_library',
                     'test_portability', 'test_homework', 'test_gigaam_bundle'):
            suite.addTests(loader.loadTestsFromModule(importlib.import_module(name)))
        # This legacy integration check exposes a callable rather than unittest cases.
        suite.addTest(unittest.FunctionTestCase(importlib.import_module('test_process_diarization').test))
        for skill in ('dion-secretary', 'mesh-homework', 'youtube-library'):
            for source in (ROOT / skill / 'scripts').glob('*.py'):
                ast.parse(source.read_text('utf-8'), filename=str(source))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
