"""Explicitly download and verify GigaAM-v3 model assets in the chosen directory."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-root', required=True, type=Path)
    args = parser.parse_args()
    if not args.model_root.is_absolute():
        parser.error('--model-root must be an absolute external downloads directory')
    repository = Path(__file__).resolve().parents[2]
    if args.model_root.resolve().is_relative_to(repository):
        parser.error('Models must be stored outside the skill repository')
    cache = args.model_root / 'Cache'
    for name, suffix in (('HF_HOME', 'huggingface'), ('TORCH_HOME', 'torch')):
        os.environ[name] = str(cache / suffix)
    from gigaam_loader import load
    load(args.model_root, offline=False)
    print('GigaAM-v3 assets downloaded, hash-checked and strictly loaded.')


if __name__ == '__main__':
    main()
