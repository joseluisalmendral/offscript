# Contributing

`grab` is a single dependency-free Python script (stdlib only) that shells
out to `yt-dlp`, `ffmpeg`/`ffprobe` and `whisper-ctranslate2`. There's no
build step for development — just edit `grab.py` and run it.

## Setup

```bash
brew install yt-dlp ffmpeg
uv tool install whisper-ctranslate2
```

## Making a change

1. Fork and branch from `main`.
2. Edit `grab.py`. Keep it a single flat module — no new dependencies unless
   they're genuinely necessary (the whole point is a zero-install script).
3. Test manually against a local file and a URL:
   ```bash
   ./grab.py "/path/to/some.ogg" --transcript-format txt
   ./grab.py "https://youtu.be/xxxx" -w audio
   ```
4. If you touch packaging, sanity-check the build:
   ```bash
   uv build && uv pip install --python /tmp/venv/bin/python3 dist/*.whl && grab --help
   ```
5. Open a PR describing the change and why.

## Reporting issues

Include: the exact command you ran, your OS, and the output of
`yt-dlp --version`, `ffmpeg -version`, `whisper-ctranslate2 --version`.

## Scope

Advanced `whisper-ctranslate2` features not wired into `grab.py` (speaker
diarization, live microphone dictation, word-level timestamps, VAD tuning)
are intentionally left out to keep the CLI small — see
[`docs/models.md`](docs/models.md) for how to run them directly instead.
PRs wiring one of these in as an opt-in flag are welcome if kept minimal.
