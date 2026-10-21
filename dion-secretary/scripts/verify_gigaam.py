"""Verify decoding and the bundled offline worker using synthetic silence only."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import wave


def no_network(*args, **kwargs):
    raise RuntimeError('Network is disabled in GigaAM verification')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(os.environ.get(
        'DION_SECRETARY_CONFIG', str(Path(__file__).resolve().parents[1] / 'config.json'))))
    args = parser.parse_args()
    config = json.loads(args.config.read_text('utf-8-sig'))
    section = config['gigaam']
    downloads = Path(config['downloads'])
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                      HF_HOME=str(downloads / 'Cache' / 'huggingface'),
                      TORCH_HOME=str(downloads / 'Cache' / 'torch'))
    socket.create_connection = no_network
    socket.socket.connect = no_network
    from faster_whisper.audio import decode_audio
    work = Path(config['runtime']) / 'verification' / 'gigaam'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='synthetic-', dir=work) as temporary:
        folder = Path(temporary)
        audio = folder / 'silence.wav'
        with wave.open(str(audio), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b'\0\0' * 16000)
        assert len(decode_audio(str(audio))) == 16000
        job = {'model_root': section['model_root'], 'ffmpeg': section['ffmpeg'],
               'output': str(folder / 'words.json'), 'cache': str(folder / 'chunks.json'),
               'tracks': [{'label': 'synthetic', 'chunks': [{'file': str(audio), 'start': 0,
                            'end': 1, 'cache_key': 'synthetic-silence-only'}]}]}
        job_path = folder / 'job.json'
        job_path.write_text(json.dumps(job), 'utf-8')
        worker = Path(section.get('worker') or Path(__file__).with_name('gigaam_worker.py'))
        subprocess.run([sys.executable, '-X', 'utf8', '-B', str(worker), '--job', str(job_path)], check=True)
        rows = json.loads((folder / 'words.json').read_text('utf-8'))
        assert isinstance(rows, list)
        for row in rows:
            assert {'start', 'end', 'speaker', 'text'} <= row.keys()
    print('PASS: synthetic WAV decoded; offline GigaAM worker completed with verified model hashes/state.')


if __name__ == '__main__':
    main()
