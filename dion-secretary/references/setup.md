# Setup

Windows and Python 3.12+ are required. Keep environments and runtime outside the checkout. Install `scripts/requirements.txt` into that environment; choose a pip cache/download directory explicitly. No model weights or dependencies are included in Git.

Run `python configure.py --runtime RUNTIME --downloads DOWNLOADS --sessions SESSIONS --notes NOTES --journal-root JOURNALS`. Use absolute paths belonging to this computer. This writes `config.json` and refuses to overwrite an existing file. It creates no environment, downloads no assets and starts no recording.

The example selects Whisper large-v3 with CPU/int8 and Codex minutes. Install the chosen local speech model explicitly before processing; `setup-models` may also download the configured local summary model. Do not run it merely to validate setup. Local summaries additionally need Ollama at `http://127.0.0.1:11435` with the configured model. If auto-starting Ollama is desired, its executable is expected at RUNTIME/tools/ollama/ollama.exe; otherwise start your existing server yourself.

Install Dion Speaker Helper separately from the owner's `dion-speaker-helper` GitHub repository. Recording needs version 0.6.0 or later with fresh lifecycle-capable journals. Set `journal_root` to the journal directory reported by the extension/native host. Existing audio files can be transcribed without a live journal; absent observations remain unknown names.

Optional GigaAM-v3 requires an external offline worker and models. Set `speech_engine=gigaam-v3` and the `gigaam` object: `python`, `worker`, `model_root`, `ffmpeg`, `model`. The worker must accept `--job JSON` as used by `scripts/gigaam_adapter.py` and emit rows with start/end/speaker/text. This installation is not bundled or provisioned by this repository; retain Whisper unless that worker is already configured. The repository does not claim a standalone GigaAM installer.

Optional voice clustering needs `diarization.enabled=true`, an interpreter with sherpa-onnx, a segmentation ONNX model, embedding ONNX model, FFmpeg and `threshold`. The main requirements do not install these optional models or that environment. Choose voice mode explicitly.

Check `status` and `devices` without capturing sound. `doctor` also checks local Ollama. Verify a requested recording separately; passing synthetic tests is not a live installation check.
