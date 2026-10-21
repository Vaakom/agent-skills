# Setup

Windows and Python 3.12+ are required. Keep environments and runtime outside the checkout. Install `scripts/requirements.txt` into that environment; choose a pip cache/download directory explicitly. No model weights or dependencies are included in Git.

Run `python configure.py --runtime RUNTIME --downloads DOWNLOADS --sessions SESSIONS --notes NOTES --journal-root JOURNALS`. Use absolute paths belonging to this computer. This writes `config.json` and refuses to overwrite an existing file. It creates no environment, downloads no assets and starts no recording.

The example selects Whisper large-v3 with CPU/int8 and Codex minutes. Install the chosen local speech model explicitly before processing; `setup-models` may also download the configured local summary model. Do not run it merely to validate setup. Local summaries additionally need Ollama at `http://127.0.0.1:11435` with the configured model. If auto-starting Ollama is desired, its executable is expected at RUNTIME/tools/ollama/ollama.exe; otherwise start your existing server yourself.

Install Dion Speaker Helper separately from the owner's `dion-speaker-helper` GitHub repository. Recording needs version 0.6.0 or later with fresh lifecycle-capable journals. Set `journal_root` to the journal directory reported by the extension/native host. Existing audio files can be transcribed without a live journal; absent observations remain unknown names.

## Optional GigaAM-v3

The worker, Hugging Face loader, model-setup command and offline check are included in `scripts/`. No code from a separate `products` folder is needed. Third-party packages and model weights remain external dependencies.

Create an isolated Python 3.12 environment outside the repository. Install `scripts/requirements-gigaam.txt` there, with a separately chosen pip cache directory. This pins the upstream GigaAM source revision; it does not copy the third-party library into the skill. Keep FFmpeg outside the repository too. Existing installations do not need to reinstall packages just because the worker moved.

Set `speech_engine=gigaam-v3`. In `gigaam`, set absolute `python`, `model_root`, `ffmpeg` paths and `model=v3_e2e_rnnt`. `configure.py` provides editable external-path defaults. Omit `worker` to use the bundled `scripts/gigaam_worker.py`; an explicit custom `worker` remains supported for compatibility.

Only when model installation is explicitly requested, run the following with the GigaAM environment's interpreter:

```text
GIGAAM_PYTHON -X utf8 -B scripts/setup_gigaam.py --model-root ABSOLUTE_EXTERNAL_MODELS_DIRECTORY
```

This command downloads official model assets into that directory and verifies hashes and strict state loading. It does not read meeting data. Existing model folders with `huggingface-e2e-rnnt/config.json`, `tokenizer.model`, `pytorch_model.bin` and `provenance.json` can be reused without downloading.

Verify the selected installation with the same interpreter:

```text
GIGAAM_PYTHON -X utf8 -B scripts/verify_gigaam.py --config ABSOLUTE_CONFIG_JSON
```

This uses generated silence, blocks network access, decodes the WAV and invokes the worker with actual local weights. It does not record audio or open an existing meeting. Processing remains offline and never provisions missing assets automatically.


Optional voice clustering needs `diarization.enabled=true`, an interpreter with sherpa-onnx, a segmentation ONNX model, embedding ONNX model, FFmpeg and `threshold`. The main requirements do not install these optional models or that environment. Choose voice mode explicitly.

Check `status` and `devices` without capturing sound. `doctor` also checks local Ollama. Verify a requested recording separately; passing synthetic tests is not a live installation check.
