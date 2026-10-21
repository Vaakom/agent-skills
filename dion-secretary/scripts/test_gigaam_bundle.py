"""Prove that GigaAM processing uses bundled code without a products checkout."""
import json
from pathlib import Path
import runpy
import socket
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import gigaam_adapter
import secretary


class BundleTests(unittest.TestCase):
    def test_adapter_defaults_to_adjacent_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = work / 'synthetic.wav'
            source.write_bytes(b'synthetic-placeholder')
            config = {'gigaam': {'python': sys.executable, 'model_root': str(work / 'models'),
                                 'ffmpeg': str(work / 'ffmpeg.exe')}}
            commands = []
            def worker(command, **kwargs):
                commands.append(command)
                job = json.loads(Path(command[-1]).read_text('utf-8'))
                Path(job['output']).write_text('[]', 'utf-8')
            with patch.object(gigaam_adapter, 'decode_audio', return_value=object()), \
                 patch.object(gigaam_adapter, 'VadOptions', return_value=object()), \
                 patch.object(gigaam_adapter, 'get_speech_timestamps', return_value=[]), \
                 patch.object(gigaam_adapter.subprocess, 'run', side_effect=worker):
                result = gigaam_adapter.transcribe_tracks([('synthetic', source)], work, config)
            self.assertEqual(result, [])
            selected = Path(commands[0][4])
            self.assertEqual(selected, Path(gigaam_adapter.__file__).with_name('gigaam_worker.py'))
            self.assertTrue(selected.is_file())
            self.assertTrue((work / 'transcript.partial.json').is_file())

    def test_readiness_uses_bundled_worker_and_preserves_custom_override(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            python = work / 'python.exe'
            python.touch()
            model = work / 'huggingface-e2e-rnnt'
            model.mkdir()
            for name in ('config.json', 'tokenizer.model', 'pytorch_model.bin', 'provenance.json'):
                (model / name).touch()
            config = {'speech_engine': 'gigaam-v3', 'gigaam': {'python': str(python), 'model_root': str(work)}}
            with patch.object(secretary, 'CONFIG', config):
                self.assertTrue(secretary.speech_ready())
                config['gigaam']['worker'] = str(work / 'missing-custom-worker.py')
                self.assertFalse(secretary.speech_ready())

    def test_worker_uses_bundled_loader_offline_and_retains_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            job = {'model_root': str(work / 'models'), 'ffmpeg': str(work / 'ffmpeg.exe'),
                   'cache': str(work / 'cache.json'), 'output': str(work / 'words.json'),
                   'tracks': [{'label': 'speaker', 'chunks': [{'file': 'synthetic.wav',
                        'start': 10, 'end': 11, 'cache_key': 'synthetic'}]}]}
            job_path = work / 'job.json'
            job_path.write_text(json.dumps(job), 'utf-8')
            model = Mock()
            model.transcribe.return_value = SimpleNamespace(text='Synthetic', words=[
                SimpleNamespace(start=.1, end=.2, text='Synthetic')])
            loader = ModuleType('gigaam_loader')
            loader.load = Mock(return_value=model)
            torch = ModuleType('torch')
            torch.set_num_threads = Mock()
            with patch.dict(sys.modules, {'torch': torch, 'gigaam_loader': loader}), \
                 patch.object(sys, 'argv', ['gigaam_worker.py', '--job', str(job_path)]), \
                 patch.object(socket, 'create_connection'), patch.object(socket.socket, 'connect'):
                runpy.run_path(str(Path(gigaam_adapter.__file__).with_name('gigaam_worker.py')), run_name='__main__')
            loader.load.assert_called_once_with(job['model_root'], offline=True)
            model.transcribe.assert_called_once_with('synthetic.wav', word_timestamps=True)
            rows = json.loads((work / 'words.json').read_text('utf-8'))
            self.assertEqual(rows, [{'start': 10.1, 'end': 10.2, 'speaker': 'speaker', 'text': 'Synthetic'}])
