# Whisper models

`offscript` runs models through `whisper-ctranslate2` (a CLI over `faster-whisper`,
which runs OpenAI's Whisper weights on the CTranslate2 inference engine).
Sizes below are approximate (int8 quantization, the default). Any model
downloads automatically on first use and is cached in
`~/.cache/huggingface/hub/` for later runs — no manual setup needed.

| Model | Download | Speed | Languages | Best for |
|---|---|---|---|---|
| `tiny` / `tiny.en` | ~75MB | fastest | 99 / **EN only** | throwaway drafts |
| `base` / `base.en` | ~145MB | very fast | 99 / **EN only** | quick drafts, a bit more accurate |
| `small` | ~484MB | fast | 99 | short/clean audio, good general default |
| `medium` | ~1.5GB | medium | 99 | podcasts/interviews, solid accuracy/speed balance |
| `large-v3-turbo` / `turbo` | ~1.6GB | ~8x faster than large-v3 | 99 | **best value for any language** — near `large-v3` accuracy at a fraction of the time |
| `large-v1` / `v2` / `v3` | ~2.9-3.1GB | slow | 99 | maximum accuracy — tough accents, noisy audio |
| `distil-large-v2` / `v3` / `v3.5` | ~1.5GB | ~4-6x faster than large-v3 | **EN only** | best value **for English** |
| `distil-medium.en` | ~750MB | fast | **EN only** | fast English-only transcription |
| `distil-small.en` | ~330MB | fastest | **EN only** | fastest English-only drafts |

### The one that bites people

**Every `distil-*` model is English-only**, not just the ones ending in `.en`.
Their Hugging Face cards declare `language: [en]`. This is easy to miss because
`distil-large-v3` looks like a variant of the multilingual `large-v3`, and
because it *does not fail* on other languages — it returns confident English
fragments that have nothing to do with the audio. A 50-minute Spanish recording
comes back as fluent-looking garbage.

`offscript` refuses this combination rather than documenting it: pairing an
English-only model with a non-English `--language` is a hard error, and using
one with no `--language` at all prints a warning.

For non-English audio the equivalent pick is **`large-v3-turbo`** — multilingual,
similar size, similar speed.

Other rules of thumb:
- Undecided between `medium` (smaller, often already cached) and
  `large-v3-turbo` (better, bigger download): `medium` for short clips,
  `large-v3-turbo` when accuracy matters or the file is long.
- Instrumental passages in music can transcribe to empty text, or hallucinate
  lyrics — expected Whisper behavior, not a bug.

## Advanced flags (not wired into `offscript.py`)

`offscript.py` exposes the flags people actually need day to day. Everything else
in `whisper-ctranslate2` is one command away — run it directly on the audio
`offscript` already extracted:

- **Speaker diarization**: `--speaker_name`, `--speaker_num N`, `--hf_token <token>` (requires a Hugging Face token and accepting the gated pyannote model terms). Useful for meetings/interviews with multiple voices.
- **Live microphone dictation**: `--live_transcribe True [--live_input_device N] [--live_volume_threshold X]`.
- **Word-level timestamps for cleaner subtitles**: `--word_timestamps True --max_line_width N --max_line_count N` (or `--max_words_per_line`), plus `--highlight_words True`.
- **Domain vocabulary** (names, jargon): `--hotwords "word1 word2 …"`.
- **Voice activity detection (VAD)**: `--vad_filter True` with `--vad_threshold`, `--vad_min_speech_duration_ms`, etc. — helps with long silences or background noise.
- **English translation**: already wired via `offscript.py --task translate`.
- **Throughput**: `--batched True --batch_size N` for large batches; `--device cuda` if a CUDA GPU is available (Apple Silicon runs CPU-only).

## Pipeline

```mermaid
flowchart LR
    A[Local file or URL] -->|URL| B[yt-dlp<br/>download + metadata]
    A -->|local path| D
    B --> C[ffmpeg / ffprobe<br/>extract audio, probe duration]
    C --> D[whisper-ctranslate2<br/>faster-whisper / CTranslate2]
    D --> E[transcript.txt / .srt / .vtt / .tsv / .json]
```

Everything runs locally — nothing is uploaded to a third-party service.
