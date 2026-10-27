"""Start the existing local classifier service without downloading or loading a model."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from youtube_library import request


def status():
    try:
        tags = request('http://127.0.0.1:11435/api/tags', timeout=2)
        return dict(server=True, model_ready=any(m.get('name') == 'qwen2.5:7b-instruct' for m in tags.get('models', [])))
    except (OSError, ValueError):
        return dict(server=False, model_ready=False)


def settings():
    path = Path(__file__).resolve().parents[1] / "config.local.json"
    return json.loads(path.read_text("utf-8-sig")) if path.is_file() else {}


def start():
    current = status()
    if current['server']:
        return current
    config = settings()
    if not all(config.get(key) for key in ('ollama_executable', 'ollama_models', 'runtime')):
        raise RuntimeError('Configure ollama_executable, ollama_models and runtime in config.local.json before starting the service.')
    executable = Path(config['ollama_executable'])
    if not executable.is_file():
        raise RuntimeError('Existing local Ollama executable is missing; no automatic download attempted.')
    runtime = Path(config['runtime'])
    runtime.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11435',
               OLLAMA_MODELS=str(Path(config['ollama_models'])), OLLAMA_NO_CLOUD='1')
    with (runtime / 'classifier-server.log').open('ab') as log:
        subprocess.Popen([str(executable), 'serve'], env=env, stdin=subprocess.DEVNULL,
                         stdout=log, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for _ in range(40):
        current = status()
        if current['server']:
            return current
        time.sleep(.5)
    raise RuntimeError('Local classifier service did not start; inspect classifier-server.log.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    print(json.dumps(start() if args.start else status(), indent=2))
