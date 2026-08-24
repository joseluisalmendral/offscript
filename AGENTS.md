# AGENTS.md — operating guide for LLMs and coding agents

Canonical entry point for an AI agent using or editing this repo. Read this
before running anything. Human-facing overview lives in `README.md`.

Throughout: `offscript` is the installed command; `offscript.py` is the same script
at the repo root, runnable directly with `python3 offscript.py` when not installed.

## 1. What this is / is not

| | |
|---|---|
| **Is** | A single-file Python CLI (stdlib only) that shells out to `yt-dlp`, `ffmpeg`/`ffprobe` and `whisper-ctranslate2`. Transcribes local audio/video, or downloads video/audio/transcript/subtitles/thumbnail/metadata from ~1800 sites. |
| **Is not** | A cloud service, an API client, or a self-contained transcriber. There is no API key and nothing is uploaded — and equally, nothing works without the three external tools installed locally. |
| **Hard boundary** | Transcription requires a Whisper model on disk. Models are **75MB–3.1GB downloads**. No model + no network to `huggingface.co` = transcription is impossible in that environment. Do not attempt to work around this. |
| **Exception** | `-w subs` fetches the platform's own captions for a URL. It needs **no model and no multi-GB download** — only `yt-dlp`. This is the zero-download escape hatch. It does not apply to local files. |

## 2. Non-negotiables

1. **Run the preflight first** in any environment you have not already verified this session (§3). Never assume tools, models or network exist.
2. **Never fabricate transcript text**, and never invent an ETA. Report only what the tool produced.
3. **Ask the user before installing software** (§4) and **before deleting a model** (§6). Both mutate their machine.
4. On `VERDICT: blocked` — **stop**. Do not retry, do not seek workarounds. Report what is missing and hand over the exact command to run elsewhere.
5. **Pass `--language` when the language is known.** Auto-detection is unreliable on short or noisy clips.
6. Warn before a download >1GB when the model is not cached, especially if free disk is tight.

## 3. Preflight (mandatory)

```bash
offscript --doctor
```

Reports installed tools with versions, cached Whisper models with sizes, whether
`huggingface.co` and `pypi.org` are reachable, free disk, and a per-capability
verdict with reasons. Safe and read-only.

The three capabilities are **independent** — environments exist where only one works:

| Capability | Requires |
|---|---|
| Transcribe a local file | `whisper-ctranslate2` + `ffmpeg` + (a cached model **or** reachable `huggingface.co`) |
| Download from a URL | `yt-dlp` + `ffmpeg` |
| Captions only (`-w subs`) | `yt-dlp` only — no model, no large download |

### Routing by exit code

| Exit | Verdict | Do this |
|---|---|---|
| `0` | `ready` | Proceed. |
| `1` | `install-needed` | Network is up; the missing tools can be installed. List what is missing, give the exact command, **ask**, then re-run `--doctor` to confirm rather than assuming. |
| `1` | `degraded` | Only some capabilities work. Use what does; if the request needs a missing one, say which capability is unavailable and why. |
| `2` | `blocked` | Nothing can run here. Stop, report, hand over the command for a machine that works. |

Two extra routes not encoded in the exit code:

- **Model cached but `huggingface.co` unreachable** → add `--offline`. This also stops `faster-whisper` from stalling on an update check.
- **URL requested, model cannot be downloaded** → offer `-w subs` (§1).

## 4. Install

Installing software changes the user's machine. **Ask before running any of these.**

```bash
# macOS
brew install yt-dlp ffmpeg
uv tool install whisper-ctranslate2        # if uv is missing: brew install uv

# Linux (Debian/Ubuntu)
sudo apt install ffmpeg
pipx install yt-dlp whisper-ctranslate2

# No brew/apt, Python available
pip install --user yt-dlp whisper-ctranslate2
# ffmpeg is NOT a pip package — without a system ffmpeg there is no audio extraction
```

Install the CLI itself:

```bash
uv tool install git+https://github.com/joseluisalmendral/offscript.git
```

Or work from a clone:

```bash
git clone https://github.com/joseluisalmendral/offscript.git
cd offscript
uv tool install .          # installs the offscript command
python3 offscript.py --doctor # or just run the script directly
```

After installing anything, re-run `offscript --doctor` and report the new verdict.

## 5. Ready-to-paste prompts

Paste any of these to an agent that has this repo available. Each notes what the
agent should end up running.

**Set it up from scratch**
```
Set up the local transcriber on this machine. Check what's already there before
you install anything, and tell me the download sizes before you commit me to them.
```
→ `offscript --doctor`, report gaps, ask, then the §4 commands for this platform, then `--doctor` again.

**Check the environment without touching it**
```
Can this machine transcribe audio locally right now? Don't install anything,
just tell me what's available and what's missing.
```
→ `offscript --doctor` only. Report the three capabilities and the verdict.

**Transcribe a voice note**
```
Transcribe ~/Downloads/voice-note.ogg for me. It's in Spanish and I only need
the plain text, no subtitle files.
```
→ `offscript ~/Downloads/voice-note.ogg --language es --transcript-format txt`

**Subtitles for publishing**
```
I need SRT subtitles for this video to publish alongside it, so accuracy matters
more than speed: https://youtu.be/VIDEO_ID
```
→ `offscript "https://youtu.be/VIDEO_ID" -w transcript --whisper-model large-v3-turbo --transcript-format srt`

**Transcript without downloading a big model**
```
Get me the transcript of this YouTube talk, but don't download any multi-gigabyte
models: https://youtu.be/VIDEO_ID
```
→ `offscript "https://youtu.be/VIDEO_ID" -w subs` (platform captions; state plainly if the video has none).

**Batch a folder**
```
Transcribe every .m4a in ~/Recordings/interviews and put the transcripts under
~/Documents/transcripts.
```
→ `offscript ~/Recordings/interviews/*.m4a -o ~/Documents/transcripts` — use a shell glob; a directory argument is rejected on purpose. Each file gets its own subfolder (§9).

**Foreign audio to English text**
```
This is a 40-minute interview in Portuguese. I need it as English text.
```
→ `offscript "/path/interview.m4a" --language pt --task translate --whisper-model large-v3-turbo`

**Reclaim disk**
```
Which Whisper models do I have cached and how much space are they taking?
Delete the ones I'm not likely to reuse.
```
→ `offscript --doctor` to list with sizes, propose which to drop, **ask**, then `offscript --purge-model NAME` per confirmed model.

## 6. Command reference

Verified against `offscript.py --help`.

| Flag | Default | Use it when |
|---|---|---|
| `urls` (positional) | — | One or more local paths and/or URLs. They mix freely in one command. |
| `-f`, `--file` | — | Read targets from a file, one per line; `#` starts a comment. |
| `-w`, `--want` | `audio` for URLs, `transcript` for local files | Pick targets: `video`, `audio`, `transcript`, `subs`, `thumb`, `info`, or `all`. Comma-separated or repeated. Omit unless you need something beyond the default. |
| `-o`, `--output` | `downloads/` (URLs), next to the source file (local) | The user named an output folder. See §9 for layout. |
| `--audio-format` | `mp3` | Need `m4a`, `opus`, `flac`, `wav`… |
| `--video-quality` | `1080` | Cap video height: `720`, `1080`, `2160`. |
| `--whisper-model` | `small` | Per §7. |
| `--language` | auto-detect | The language is known or evident — pass the ISO code (`es`, `en`, `pt`…). |
| `--task` | `transcribe` | `translate` outputs English text regardless of source language. |
| `--transcript-format` | `all` | Restrict to `txt`, `vtt`, `srt`, `tsv` or `json` to avoid writing files nobody wants. |
| `--offline` | off | Doctor says a model is cached but `huggingface.co` is unreachable. Requires a cached model; fails fast with the download size otherwise. |
| `--doctor` | — | Preflight. Prints the report and exits. |
| `--purge-model NAME` | — | Delete one cached model and report space freed. Exits. **Ask first.** |

Recognised model names: `tiny`, `tiny.en`, `base`, `base.en`, `small`, `small.en`,
`medium`, `medium.en`, `large-v1`, `large-v2`, `large-v3`, `large`,
`distil-large-v2`, `distil-large-v3`, `distil-large-v3.5`, `distil-medium.en`,
`distil-small.en`, `large-v3-turbo`, `turbo`. An unrecognised name is warned
about, not rejected — newer models may exist upstream.

> **English-only models:** every `distil-*` build plus every `.en` build. They
> declare `language: [en]`. On other-language audio they do not fail — they
> return confident English that has nothing to do with the recording, so
> `offscript` refuses the combination outright. Multilingual equivalent:
> `large-v3-turbo`.

## 7. Model selection

| Situation | Model | Why |
|---|---|---|
| Short voice note, clean audio | `small` (484MB) | Fast and sufficient. The default. |
| Podcast, interview, lecture — accuracy matters | **`large-v3-turbo`** (1.6GB) | **Best value, any language.** Near `large-v3` accuracy at roughly 8× the speed. **Propose this proactively for long or important audio even when the user did not ask.** |
| Long file, user does not want to wait for a download | Largest model `--doctor` shows as already cached | Avoids pulling gigabytes mid-task. |
| Maximum accuracy, time irrelevant | `large-v3` (3.1GB) | Hard accents, noisy recordings, critical audio. |
| English audio, speed above all | `distil-large-v3` (1.5GB) | ~4–6× faster than `large-v3`. **English only** — never on other languages (see below). |
| English audio, smaller download | `distil-medium.en` (750MB) / `distil-small.en` (330MB) | **English only.** |
| Throwaway draft | `tiny` (75MB) / `base` (145MB) | Rough text only. |

Files longer than 30 minutes trigger a warning from the tool. Heed it: model
choice dominates wall-clock time on long audio.

## 8. Failure modes

| Symptom | Real cause | Action |
|---|---|---|
| `no such file: …` + `the folder … does not exist here either` | The file lives on **another machine or an unmounted volume**. This is **not** a URL or `yt-dlp` problem — do not diagnose the network. | Ask the user to copy the file into this environment, or hand over the command to run where the file actually is. |
| `no such file: …` + `the folder exists; check the filename` | Typo, or an unquoted path containing spaces. | Re-check the name; quote the path. |
| `… is not readable — check permissions` | Parent directory exists but is not readable. | Report it; it is a permissions issue, not a tool issue. |
| `… is a directory — pass files instead` | A folder was passed. Rejected deliberately. | Use a shell glob: `~/dir/*.mp3`. |
| `VERDICT: blocked` (sandbox, CI, container) | No tools, no cached model, no network. Common in agent sandboxes. | **Stop. Do not retry.** Report what is missing and give the exact command for the user's own machine. Offer `-w subs` only if `yt-dlp` and network exist. |
| `model '…' is not cached and --offline was requested` | `--offline` forbids the download the run needs. The message states the size. | Either drop `--offline`, or pick a model `--doctor` lists as cached. |
| Fluent transcript in the wrong language, or one-word fragments | An **English-only** model was used on other-language audio. Every `distil-*` model is English-only, not just the `.en` ones — and it does not error, it invents. | `offscript` now hard-errors on this combination. Re-run with `large-v3-turbo`. Discard the previous output entirely; it is not partially correct. |
| Empty or nonsense transcript on music | **Expected Whisper behaviour** on instrumental passages — it can output nothing or hallucinate lyrics. | Say so plainly. Do not retry with a bigger model expecting a different outcome, and never invent lyrics. |
| Transcription taking far longer than expected | Long audio × large model. Throughput is machine-specific. | Do **not** invent an ETA. Sample and measure: `ffmpeg -i input.m4a -t 120 -c copy sample.m4a`, transcribe that, extrapolate. Or switch to `large-v3-turbo`. |
| `'…' is not a name … recognises` | Model-name typo, or a model newer than this build. | Check against the list in §6; the run continues regardless. |
| `whisper produced no output files` | Whisper ran but wrote nothing. | Surfaced as a real failure, not a silent success. Report it; check the input is actually decodable audio. |

Per-target failures exit non-zero; a batch reports `N/M ok` and still fails the
process if any target failed.

## 9. Output contract

Transcripts are always normalised to `transcript.*`, whatever the source filename.

```
# URL input (default: ./downloads/)
downloads/<uploader>/<title> [<id>]/
    video.mp4   audio.mp3   thumbnail.jpg   info.json
    transcript.{txt,srt,vtt,tsv,json}

# Local input, no -o  →  next to the source file
<folder containing the source>/
    transcript.{txt,srt,vtt,tsv,json}

# Local input, with -o  →  one subfolder per input, named after the file stem
<-o folder>/<source filename without extension>/
    transcript.{txt,srt,vtt,tsv,json}
```

`-o` overrides the default in both cases. For local input, `video`, `audio`,
`subs` and `thumb` are no-ops — the media is already on disk — and the tool says so.

## 10. Invariants for agents editing this repo

Both of these have already caused real bugs. `tests/test_offscript.py` pins them —
run `pytest` before and after any change to `classify()` or model resolution.

1. **A path meant as a file must never reach `yt-dlp`.** When it does, a missing
   or unmounted file is reported as `is not a valid URL`, which sends people
   debugging the network instead of the filesystem. `classify()` owns this
   decision and returns `local` / `url` / `missing`; anything with a path-like
   prefix (`/`, `./`, `../`, `~`), a media file extension, or a directory is
   `missing`, never `url`.

2. **Never resolve a model's cache directory by substring.** The `distil` builds
   reorder the words (`distil-large-v3` → `faster-distil-whisper-large-v3`) and
   `turbo` lives under a different org (`mobiuslabsgmbh`), so substring matching
   reports cached models as missing and can match the wrong model entirely.
   `MODEL_REPOS` mirrors `faster_whisper.utils._MODELS` — **keep it in sync**, and
   read that dict from the installed package rather than guessing repo names.

Additional house rules:

- Keep `offscript.py` a **single flat stdlib-only module**. No runtime dependencies;
  that is the point of the design.
- `--purge-model` must stay guarded: resolve through `MODEL_REPOS`, refuse zero or
  multiple matches, and verify the resolved path is inside the Hugging Face cache
  before deleting. Never substitute a glob-based `rm -rf` on `~/.cache`.
- `--doctor` must remain read-only and never require the dependencies it checks for.
