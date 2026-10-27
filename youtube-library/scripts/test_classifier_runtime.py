import tempfile
import unittest
from unittest.mock import patch, mock_open
import classifier_runtime as runtime


class ClassifierRuntimeTests(unittest.TestCase):
    def test_existing_service_never_starts_duplicate(self):
        with patch.object(runtime, 'status', return_value={'server': True, 'model_ready': True}), patch.object(runtime.subprocess, 'Popen') as launch:
            self.assertTrue(runtime.start()['model_ready'])
            launch.assert_not_called()

    def test_missing_service_is_explicit(self):
        with patch.object(runtime, 'request', side_effect=OSError('offline')):
            self.assertEqual(runtime.status(), {'server': False, 'model_ready': False})

    def test_start_is_loopback_only_and_uses_download_model_directory(self):
        ready = {'server': True, 'model_ready': True}
        config = {key: str(runtime.Path(tempfile.gettempdir()) / ('classifier-fixture-' + key)) for key in ('ollama_executable', 'ollama_models', 'runtime')}
        with patch.object(runtime, 'settings', return_value=config), patch.object(runtime, 'status', side_effect=[{'server': False}, ready]), patch.object(runtime.Path, 'is_file', return_value=True), patch.object(runtime.Path, 'mkdir'), patch.object(runtime.Path, 'open', mock_open()), patch.object(runtime.subprocess, 'Popen') as launch:
            self.assertEqual(runtime.start(), ready)
            env = launch.call_args.kwargs['env']
            self.assertEqual(env['OLLAMA_HOST'], '127.0.0.1:11435')
            self.assertEqual(env['OLLAMA_NO_CLOUD'], '1')
            self.assertEqual(env['OLLAMA_MODELS'], config['ollama_models'])

    def test_unconfigured_start_does_not_launch(self):
        with patch.object(runtime, 'status', return_value={'server': False}), patch.object(runtime, 'settings', return_value={}), patch.object(runtime.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(RuntimeError, 'Configure'):
                runtime.start()
            launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
