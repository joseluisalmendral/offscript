#!/usr/bin/env python3
"""
offscript — mini CLI to transcribe/download video / audio / transcript from a
local file, or from YouTube, Vimeo and ~1800 other sites (anything yt-dlp
supports).

Examples:
    ./offscript.py --doctor                                  # check what this machine can do
    ./offscript.py "/path/note.ogg"                          # transcribe a local file
    ./offscript.py "https://youtu.be/xxxx"                   # audio only (default)
    ./offscript.py URL -w video,audio,transcript             # several at once
    ./offscript.py URL -w all                                # everything
    ./offscript.py URL1 "note.ogg" -w transcript             # batch (URLs + local files mix freely)
    ./offscript.py -f targets.txt -w transcript              # targets from a file
    ./offscript.py "note.ogg" --language es --task translate # foreign audio -> English text
    ./offscript.py "note.ogg" --offline                      # never touch the network

Outputs for URLs go to ./downloads/<uploader>/<title> [<id>]/; for local
files, next to the source file (or under -o/--output if given), with
consistent names: video.<ext>, audio.<fmt>, transcript.{txt,srt,vtt,tsv,json},
thumbnail.<ext>, info.json, subtitles (original captions if present).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# ---- pretty printing -------------------------------------------------------
BOLD, DIM, GREEN, YELLOW, RED, CYAN, RESET = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[0m",
)


def say(msg: str, color: str = "") -> None:
    print(f"{color}{msg}{RESET}", flush=True)


def die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    say(f"✗ {msg}", RED)
    sys.exit(1)


# ---- dependencies ----------------------------------------------------------
# Install hints cover macOS (brew/uv) and Linux (apt/pipx) so the message is
# useful wherever this runs.
HINTS = {
    "yt-dlp": "brew install yt-dlp   ·   or: pipx install yt-dlp",
    "ffmpeg": "brew install ffmpeg   ·   or: sudo apt install ffmpeg",
    "ffprobe": "ships with ffmpeg — brew install ffmpeg / sudo apt install ffmpeg",
    "whisper-ctranslate2": "uv tool install whisper-ctranslate2   ·   or: pipx install whisper-ctranslate2",
}


def need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        die(f"'{tool}' not found. Install it with: {HINTS.get(tool, tool)}")
    return path


def tool_version(tool: str) -> str | None:
    """Short version string for a tool, or None if it isn't installed."""
    path = shutil.which(tool)
    if not path:
        return None
    for flag in ("--version", "-version"):
        try:
            out = subprocess.run([path, flag], capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            continue
        text = (out.stdout or out.stderr).strip()
        if text:
            first = text.splitlines()[0]
            # "ffmpeg version 8.0.1 Copyright…" -> "8.0.1"
            parts = first.split()
            if len(parts) >= 3 and parts[1] == "version":
                return parts[2]
            return first[:40]
    return "present"


# ---- whisper model cache ---------------------------------------------------
HUB = Path.home() / ".cache" / "huggingface" / "hub"

# Model name -> Hugging Face repo, mirroring faster_whisper.utils._MODELS.
# Needed because the repo name is NOT a substring of the model name for the
# distil builds ("distil-large-v3" lives in "faster-distil-whisper-large-v3"),
# so guessing the cache directory by substring silently reports a cached model
# as missing.
MODEL_REPOS = {
    "tiny": "Systran/faster-whisper-tiny",
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base": "Systran/faster-whisper-base",
    "base.en": "Systran/faster-whisper-base.en",
    "small": "Systran/faster-whisper-small",
    "small.en": "Systran/faster-whisper-small.en",
    "medium": "Systran/faster-whisper-medium",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v1": "Systran/faster-whisper-large-v1",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
    "large": "Systran/faster-whisper-large-v3",
    "distil-large-v2": "Systran/faster-distil-whisper-large-v2",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    "distil-large-v3.5": "distil-whisper/distil-large-v3.5-ct2",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}

# Every Distil-Whisper build is English-only, as is every ".en" build — the
# Hugging Face cards declare `language: [en]`. This matters more than it looks:
# forcing a non-English language on one of them does NOT error, it emits
# confident English fragments, so a 50-minute Spanish recording comes back as
# fluent-looking garbage. Checked rather than documented.
ENGLISH_ONLY = {
    "tiny.en", "base.en", "small.en", "medium.en",
    "distil-large-v2", "distil-large-v3", "distil-large-v3.5",
    "distil-medium.en", "distil-small.en",
}

# Approximate int8 download sizes, only used to warn before a big download.
MODEL_SIZE_MB = {
    "tiny": 75, "tiny.en": 75, "base": 145, "base.en": 145,
    "small": 484, "small.en": 484, "medium": 1500, "medium.en": 1500,
    "large-v1": 2900, "large-v2": 3100, "large-v3": 3100, "large": 3100,
    "large-v3-turbo": 1600, "turbo": 1600,
    "distil-large-v2": 1500, "distil-large-v3": 1500, "distil-large-v3.5": 1500,
    "distil-medium.en": 750, "distil-small.en": 330,
}


def cache_dir_name(repo: str) -> str:
    """Hugging Face stores 'Org/Repo' as 'models--Org--Repo'."""
    return "models--" + repo.replace("/", "--")


def human(n_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n_bytes < 1024 or unit == "TB":
            return f"{n_bytes:.0f} {unit}" if unit != "GB" else f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024
    return f"{n_bytes:.0f} TB"


def dir_size(path: Path) -> int:
    """Bytes on disk. Symlinks are not followed, so HF blobs count once."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += (Path(root) / name).lstat().st_size
            except OSError:
                pass
    return total


def cached_models() -> list[tuple[str, int]]:
    """Whisper models present in the Hugging Face hub cache, as (dir name, bytes).

    Discovered by scanning rather than by a hardcoded model->repo map, so it
    stays correct for any model naming whisper-ctranslate2 happens to use.
    """
    if not HUB.is_dir():
        return []
    found = []
    for entry in sorted(HUB.glob("models--*")):
        if entry.is_dir() and "whisper" in entry.name.lower():
            found.append((entry.name, dir_size(entry)))
    return found


def model_matches(model: str, dir_name: str) -> bool:
    """Does this cache directory hold this model?

    Exact for known model names via MODEL_REPOS; for anything else (a newer
    model, or a raw repo id) fall back to requiring every token of the name to
    appear, which avoids 'small' matching 'distil-small.en'.
    """
    repo = MODEL_REPOS.get(model)
    if repo:
        return dir_name.lower() == cache_dir_name(repo).lower()
    tokens = [t for t in model.lower().replace("/", "-").split("-") if t]
    return all(t in dir_name.lower() for t in tokens)


def model_is_cached(model: str, cached: list[tuple[str, int]]) -> bool:
    return any(model_matches(model, name) for name, _ in cached)


def purge_model(model: str) -> None:
    """Delete one cached model. Refuses anything ambiguous or outside the cache."""
    cached = cached_models()
    matches = [(name, size) for name, size in cached if model_matches(model, name)]

    if not matches:
        say(f"no cached model matches '{model}'.", YELLOW)
        if cached:
            say("cached models:", DIM)
            for name, size in cached:
                say(f"  {name}  ({human(size)})", DIM)
        sys.exit(1)
    if len(matches) > 1:
        say(f"'{model}' is ambiguous — it matches several cached models:", YELLOW)
        for name, size in matches:
            say(f"  {name}  ({human(size)})", DIM)
        say("re-run with the full directory name.", YELLOW)
        sys.exit(1)

    name, size = matches[0]
    target = (HUB / name).resolve()
    # Never delete anything outside the hub cache, whatever was passed in.
    if HUB.resolve() not in target.parents:
        die(f"refusing to delete {target}: outside {HUB}")
    shutil.rmtree(target)
    say(f"✓ removed {name} — freed {human(size)}", GREEN)


# ---- environment doctor ----------------------------------------------------
def reachable(url: str, timeout: float = 5.0) -> bool:
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=timeout)
        return True
    except urllib.error.HTTPError:
        # The server answered (405, 403…), so the network path works.
        return True
    except Exception:  # noqa: BLE001 — any failure means "not reachable from here"
        return False


def doctor() -> int:
    """Report what this machine can actually do. Exit code: 0 ready, 1 degraded, 2 blocked."""
    say(f"{BOLD}offscript doctor{RESET}\n")

    say(f"{BOLD}tools{RESET}")
    versions = {}
    for tool in ("yt-dlp", "ffmpeg", "ffprobe", "whisper-ctranslate2"):
        versions[tool] = tool_version(tool)
        if versions[tool]:
            say(f"  {tool:<22} {GREEN}{versions[tool]}{RESET}")
        else:
            say(f"  {tool:<22} {RED}missing{RESET}  {DIM}→ {HINTS[tool]}{RESET}")

    say(f"\n{BOLD}whisper models cached{RESET} {DIM}({HUB}){RESET}")
    cached = cached_models()
    if cached:
        for name, size in cached:
            say(f"  {name:<48} {human(size)}")
    else:
        say(f"  {YELLOW}none{RESET}")

    say(f"\n{BOLD}network{RESET}")
    hf = reachable("https://huggingface.co")
    pypi = reachable("https://pypi.org")
    say(f"  huggingface.co         {(GREEN + 'reachable') if hf else (RED + 'unreachable')}{RESET}"
        f"{'' if hf else DIM + '  (no model downloads)' + RESET}")
    say(f"  pypi.org               {(GREEN + 'reachable') if pypi else (RED + 'unreachable')}{RESET}"
        f"{'' if pypi else DIM + '  (no tool installs)' + RESET}")

    free = shutil.disk_usage(Path.home()).free
    say(f"\n{BOLD}disk free{RESET}                {human(free)}")

    # What can actually run here, and why not.
    whisper_ok = bool(versions["whisper-ctranslate2"])
    ffmpeg_ok = bool(versions["ffmpeg"])
    ytdlp_ok = bool(versions["yt-dlp"])
    have_model = bool(cached)

    def cap(ok: bool, label: str, reasons: list[str]) -> None:
        mark = f"{GREEN}yes{RESET}" if ok else f"{RED}NO{RESET}"
        why = "" if ok else f"  {DIM}({'; '.join(reasons)}){RESET}"
        say(f"  {label:<30} {mark}{why}")

    local_reasons = []
    if not whisper_ok:
        local_reasons.append("whisper-ctranslate2 missing" + ("" if pypi else " and pypi.org unreachable"))
    if not ffmpeg_ok:
        local_reasons.append("ffmpeg missing")
    if not have_model and not hf:
        local_reasons.append("no cached model and huggingface.co unreachable")
    can_local = not local_reasons

    url_reasons = []
    if not ytdlp_ok:
        url_reasons.append("yt-dlp missing")
    if not ffmpeg_ok:
        url_reasons.append("ffmpeg missing")
    can_url = not url_reasons

    caption_reasons = [] if ytdlp_ok else ["yt-dlp missing"]
    can_captions = not caption_reasons

    say(f"\n{BOLD}capabilities{RESET}")
    cap(can_local, "transcribe a local file", local_reasons)
    cap(can_url, "download from a URL", url_reasons)
    cap(can_captions, "captions only (no model)", caption_reasons)

    if can_local and can_url:
        say(f"\n{BOLD}VERDICT:{RESET} {GREEN}ready{RESET}")
        if have_model and not hf:
            say(f"{DIM}offline with a cached model — pass --offline to skip network checks{RESET}")
        return 0
    if pypi and (not whisper_ok or not ytdlp_ok or not ffmpeg_ok):
        say(f"\n{BOLD}VERDICT:{RESET} {YELLOW}install-needed{RESET} — network is up, the missing tools above can be installed")
        return 1
    if can_captions or can_local or can_url:
        say(f"\n{BOLD}VERDICT:{RESET} {YELLOW}degraded{RESET} — only some capabilities are available here")
        return 1
    say(f"\n{BOLD}VERDICT:{RESET} {RED}blocked{RESET} — nothing can run in this environment")
    say(f"{DIM}run offscript on a machine with the tools installed, or with network access to install them{RESET}")
    return 2


# ---- target classification -------------------------------------------------
WANTS = ["video", "audio", "transcript", "subs", "thumb", "info"]
UNSUPPORTED_LOCAL = {"video", "audio", "subs", "thumb"}

URL_SCHEMES = ("http://", "https://", "ftp://", "ftps://", "rtmp://", "rtsp://", "magnet:")
MEDIA_SUFFIXES = {
    ".mp3", ".m4a", ".aac", ".opus", ".ogg", ".oga", ".wav", ".flac", ".wma", ".aiff",
    ".mp4", ".m4v", ".mkv", ".mov", ".webm", ".avi", ".flv", ".wmv", ".mpg", ".mpeg", ".ts",
}


def classify(raw: str, path: Path) -> str:
    """'local' | 'url' | 'missing' — a path that was clearly meant as a file and
    does not exist must never be handed to yt-dlp, or the error blames the URL
    parser for what is really an unreadable/unmounted file."""
    if path.is_file():
        return "local"
    if raw.lower().startswith(URL_SCHEMES):
        return "url"
    if path.is_dir():
        return "missing"
    if raw.startswith(("/", "./", "../", "~")) or path.suffix.lower() in MEDIA_SUFFIXES:
        return "missing"
    return "url"  # bare domain, ytsearch:, playlist id… let yt-dlp decide


def report_missing(raw: str, path: Path) -> None:
    if path.is_dir():
        say(f"  ✗ {raw} is a directory — pass files instead, e.g. {path}/*.mp3", RED)
        return
    say(f"  ✗ no such file: {path}", RED)
    parent = path.parent
    if not parent.exists():
        say(f"    the folder {parent} does not exist here either — if this path lives on"
            f" another machine (or a volume that is not mounted), run offscript there,"
            f" or copy the file into this environment first.", DIM)
    elif not os.access(parent, os.R_OK):
        say(f"    {parent} exists but is not readable — check permissions.", DIM)
    else:
        say(f"    the folder exists; check the filename (or quote it if it has spaces).", DIM)


def parse_wants(raw: list[str]) -> set[str]:
    wants: set[str] = set()
    for chunk in raw:
        for item in chunk.split(","):
            item = item.strip().lower()
            if not item:
                continue
            if item == "all":
                wants.update(WANTS)
            elif item in WANTS:
                wants.add(item)
            else:
                die(f"unknown target '{item}'. Valid: {', '.join(WANTS)}, all")
    return wants or {"audio"}


# ---- yt-dlp helpers --------------------------------------------------------
def run(cmd: list[str], quiet: bool = False) -> subprocess.CompletedProcess:
    if not quiet:
        say("  $ " + " ".join(cmd), DIM)
    return subprocess.run(cmd, check=False)


def fetch_info(ytdlp: str, url: str) -> dict:
    """Grab metadata first so we know where files will land."""
    out = subprocess.run(
        [ytdlp, "--no-warnings", "--dump-single-json", "--no-playlist", url],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"could not read info for {url}\n{out.stderr.strip()}")
    return json.loads(out.stdout)


def target_dir(base: Path, info: dict) -> Path:
    uploader = (info.get("uploader") or info.get("channel") or "Unknown").strip()
    title = (info.get("title") or info.get("id") or "untitled").strip()
    vid = info.get("id", "")
    safe = lambda s: "".join(c for c in s if c not in '/\\:*?"<>|').strip()[:120]
    folder = base / safe(uploader) / f"{safe(title)} [{vid}]"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def probe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return None


def fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return "?"
    total = int(seconds)
    if total >= 3600:
        return f"{total // 3600}h{(total % 3600) // 60:02d}m"
    return f"{total // 60}m{total % 60:02d}s"


# ---- main per-target pipelines ---------------------------------------------
def process(url: str, wants: set[str], args, ytdlp: str) -> dict:
    say(f"\n{BOLD}▶ {url}{RESET}", CYAN)
    info = fetch_info(ytdlp, url)
    dest = target_dir(Path(args.output or "downloads"), info)
    say(f"  → {dest}", DIM)

    title = info.get("title", url)
    say(f"  {BOLD}{title}{RESET}  ({fmt_duration(info.get('duration'))})")

    common = [ytdlp, "--no-playlist", "--no-warnings", "--newline"]

    # info.json + thumbnail are cheap; always write info if requested
    if "info" in wants:
        (dest / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
        say("  ✓ info.json", GREEN)

    if "thumb" in wants:
        run(common + ["--write-thumbnail", "--skip-download",
                      "--convert-thumbnails", "jpg",
                      "-o", str(dest / "thumbnail.%(ext)s"), url])

    if "subs" in wants:
        run(common + ["--write-subs", "--write-auto-subs", "--sub-langs", "all",
                      "--skip-download", "--sub-format", "srt/best",
                      "-o", str(dest / "subs.%(ext)s"), url])

    if "video" in wants:
        say("  ↓ video…", YELLOW)
        run(common + [
            "-f", f"bestvideo[height<={args.video_quality}]+bestaudio/best",
            "--merge-output-format", "mp4",
            "--embed-metadata", "--embed-thumbnail", "--embed-subs",
            "-o", str(dest / "video.%(ext)s"), url])

    audio_file = next(iter(dest.glob("audio.*")), None)
    if "audio" in wants or ("transcript" in wants and audio_file is None):
        say("  ↓ audio…", YELLOW)
        run(common + [
            "-f", "bestaudio/best", "-x",
            "--audio-format", args.audio_format, "--audio-quality", "0",
            "--embed-metadata", "--embed-thumbnail",
            "-o", str(dest / "audio.%(ext)s"), url])
        audio_file = next(iter(dest.glob("audio.*")), None)

    if "transcript" in wants:
        if not audio_file:
            say("  ✗ no audio to transcribe", RED)
        else:
            transcribe(audio_file, dest, args)
            # if user didn't want the audio, drop the temp file
            if "audio" not in wants:
                audio_file.unlink(missing_ok=True)

    return {"title": title, "dir": str(dest)}


def process_local(path: Path, wants: set[str], args) -> dict:
    say(f"\n{BOLD}▶ {path.name}{RESET}", CYAN)
    dest = (Path(args.output) / path.stem) if args.output else path.parent
    dest.mkdir(parents=True, exist_ok=True)
    say(f"  → {dest}", DIM)

    duration = probe_duration(path)
    say(f"  {BOLD}{path.name}{RESET}  ({fmt_duration(duration)})")

    unsupported = wants & UNSUPPORTED_LOCAL
    if unsupported:
        say(f"  ℹ {', '.join(sorted(unsupported))} n/a for local files (already have the media)", YELLOW)

    if "info" in wants:
        info = {"file": str(path), "duration_seconds": duration, "size_bytes": path.stat().st_size}
        (dest / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
        say("  ✓ info.json", GREEN)

    if "transcript" in wants:
        if duration and duration > 1800:
            say(f"  ℹ long file ({fmt_duration(duration)}) — a large model can take much longer"
                f" than the audio itself; distil-large-v3 or large-v3-turbo are far faster", YELLOW)
        transcribe(path, dest, args)

    return {"title": path.name, "dir": str(dest)}


def transcribe(audio: Path, dest: Path, args) -> None:
    whisper = need("whisper-ctranslate2")

    if args.whisper_model not in MODEL_REPOS:
        # Not rejected: whisper-ctranslate2 may know models this build doesn't.
        say(f"  ℹ '{args.whisper_model}' is not a name offscript recognises — if that's a typo,"
            f" valid names are: {', '.join(MODEL_REPOS)}", YELLOW)

    if args.whisper_model in ENGLISH_ONLY:
        lang = (args.language or "").lower()
        multilingual = "large-v3-turbo (fast) or large-v3 (most accurate)"
        if lang and lang not in ("en", "english"):
            die(f"'{args.whisper_model}' is an English-only model, but --language {args.language}"
                f" was requested.\n"
                f"  It would not fail — it would return confident English text that has nothing"
                f" to do with the audio.\n"
                f"  Use a multilingual model instead: {multilingual}.")
        if not lang:
            say(f"  ⚠ '{args.whisper_model}' is English-only and no --language was given."
                f" If this audio is not English the transcript will be nonsense —"
                f" use {multilingual}.", YELLOW)
        elif args.task == "translate":
            say(f"  ℹ --task translate on an English-only model does nothing;"
                f" it can only read English in the first place.", YELLOW)

    if not model_is_cached(args.whisper_model, cached_models()):
        size = MODEL_SIZE_MB.get(args.whisper_model)
        detail = f" (~{size} MB)" if size else ""
        if args.offline:
            die(f"model '{args.whisper_model}' is not cached and --offline was requested.\n"
                f"  Either drop --offline to download it{detail}, or pick a cached model "
                f"(see: offscript --doctor).")
        say(f"  ↓ model '{args.whisper_model}' not cached — downloading it first{detail}", YELLOW)

    say(f"  ✎ transcribing with whisper ({args.whisper_model}, task={args.task})…", YELLOW)
    cmd = [whisper, str(audio),
           "--model", args.whisper_model,
           "--output_dir", str(dest),
           "--output_format", args.transcript_format,
           "--task", args.task]
    if args.language:
        cmd += ["--language", args.language]
    if args.offline:
        cmd += ["--local_files_only", "True"]
    result = run(cmd, quiet=True)
    if result.returncode != 0:
        raise RuntimeError(f"whisper-ctranslate2 exited with code {result.returncode}")

    # whisper names outputs after the audio stem -> normalize to transcript.*
    stem = audio.stem
    exts = ("txt", "srt", "vtt", "tsv", "json") if args.transcript_format == "all" else (args.transcript_format,)
    written = []
    for ext in exts:
        src = dest / f"{stem}.{ext}"
        if src.exists():
            src.rename(dest / f"transcript.{ext}")
            written.append(ext)
    if not written:
        raise RuntimeError("whisper produced no output files")
    say(f"  ✓ transcript.{{{','.join(written)}}}", GREEN)


# ---- cli -------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Transcribe/download video/audio/transcript from a local file, YouTube, Vimeo and more.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("urls", nargs="*", help="one or more local file paths and/or URLs (freely mixed)")
    p.add_argument("-f", "--file", help="read URLs/paths from a file (one per line)")
    p.add_argument("-w", "--want", action="append", default=[],
                   help=f"what to get: {','.join(WANTS)} or 'all' "
                        f"(default: audio for URLs, transcript for local files)")
    p.add_argument("-o", "--output", default=None,
                   help="output folder (default: downloads/ for URLs, next to the file for local input)")
    p.add_argument("--audio-format", default="mp3",
                   help="mp3, m4a, opus, flac, wav… (default mp3)")
    p.add_argument("--video-quality", default="1080",
                   help="max video height, e.g. 720, 1080, 2160 (default 1080)")
    p.add_argument("--whisper-model", default="small",
                   help="tiny, base, small, medium, large-v3, distil-large-v3… (default small)")
    p.add_argument("--language", default=None,
                   help="force transcription language (default: auto-detect)")
    p.add_argument("--task", default="transcribe", choices=["transcribe", "translate"],
                   help="'transcribe' keeps the source language, 'translate' outputs English text (default transcribe)")
    p.add_argument("--transcript-format", default="all",
                   choices=["txt", "vtt", "srt", "tsv", "json", "all"],
                   help="which transcript file(s) to keep (default: all)")
    p.add_argument("--offline", action="store_true",
                   help="never reach the network: require an already-cached whisper model")
    p.add_argument("--doctor", action="store_true",
                   help="report which tools, models and network this machine has, then exit")
    p.add_argument("--purge-model", metavar="NAME", default=None,
                   help="delete one cached whisper model to free disk space, then exit")
    return p


def main() -> None:
    p = build_parser()
    args = p.parse_args()

    if args.doctor:
        sys.exit(doctor())
    if args.purge_model:
        purge_model(args.purge_model)
        sys.exit(0)

    urls = list(args.urls)
    if args.file:
        urls += [ln.strip() for ln in Path(args.file).read_text().splitlines()
                 if ln.strip() and not ln.startswith("#")]
    if not urls:
        p.print_help()
        sys.exit(0)

    raw_want_given = bool(args.want)
    wants = parse_wants(args.want)
    targets = [(raw, Path(raw).expanduser(), classify(raw, Path(raw).expanduser())) for raw in urls]

    if any(kind == "url" for _, _, kind in targets):
        need("yt-dlp")
    ytdlp = shutil.which("yt-dlp") or ""

    targets_desc = ", ".join(sorted(wants)) if raw_want_given else "audio (URLs) / transcript (local files)"
    say(f"{BOLD}offscript{RESET} — targets: {GREEN}{targets_desc}{RESET} | {len(urls)} item(s)")

    results, failures = [], 0
    for raw, path, kind in targets:
        try:
            if kind == "missing":
                say(f"\n{BOLD}▶ {raw}{RESET}", CYAN)
                report_missing(raw, path)
                failures += 1
            elif kind == "local":
                local_wants = wants if raw_want_given else {"transcript"}
                results.append(process_local(path, local_wants, args))
            else:
                results.append(process(raw, wants, args, ytdlp))
        except KeyboardInterrupt:
            die("interrupted")
        except Exception as e:  # noqa: BLE001
            say(f"  ✗ failed: {e}", RED)
            failures += 1

    say(f"\n{BOLD}Done.{RESET} {len(results)}/{len(urls)} ok.",
        GREEN if not failures else YELLOW)
    for r in results:
        say(f"  • {r['title']}\n    {DIM}{r['dir']}{RESET}")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
