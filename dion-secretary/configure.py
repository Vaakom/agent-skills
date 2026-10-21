"""Create machine settings without installing dependencies or overwriting configuration."""
import argparse
import json
from pathlib import Path


def configure(args):
    target = Path(__file__).with_name('config.json')
    settings = json.loads(Path(__file__).with_name('config.example.json').read_text('utf-8'))
    for key in ('runtime', 'downloads', 'sessions', 'notes', 'journal_root'):
        path = Path(getattr(args, key)).expanduser()
        if not path.is_absolute():
            raise ValueError(key + ' must be absolute')
        settings[key] = str(path)
    settings['speech_model_dir'] = str(Path(settings['downloads']) / 'Models' / 'whisper-large-v3')
    settings['ollama_model_dir'] = str(Path(settings['downloads']) / 'Models' / 'ollama')
    settings['gigaam']['model_root'] = str(Path(settings['downloads']) / 'Models' / 'GigaAM-v3')
    settings['gigaam']['python'] = str(Path(settings['runtime']) / 'gigaam-venv' / 'Scripts' / 'python.exe')
    settings['gigaam']['ffmpeg'] = str(Path(settings['runtime']) / 'tools' / 'ffmpeg' / 'ffmpeg.exe')
    with target.open('x', encoding='utf-8') as stream:
        json.dump(settings, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('runtime', 'downloads', 'sessions', 'notes', 'journal_root'):
        parser.add_argument('--' + key.replace('_', '-'), required=True)
    print(configure(parser.parse_args()))
