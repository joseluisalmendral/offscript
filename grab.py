#!/usr/bin/env python3
"""
grab — mini CLI to transcribe/download video / audio / transcript from a
local file, or from YouTube, Vimeo and ~1800 other sites (anything yt-dlp
supports).

Examples:
    ./grab.py "/path/note.ogg"                          # transcribe a local file
    ./grab.py "https://youtu.be/xxxx"                   # audio only (default)
    ./grab.py URL -w video,audio,transcript             # several at once
    ./grab.py URL -w all                                # everything
    ./grab.py URL1 URL2 URL3 -w audio,transcript        # batch (URLs + local files mix freely)
    ./grab.py -f urls.txt -w transcript                 # URLs from a file
    ./grab.py "note.ogg" --language es --task translate # foreign audio -> English text

Outputs for URLs go to ./downloads/<uploader>/<title> [<id>]/; for local
files, next to the source file (or under -o/--output if given), with
consistent names: video.<ext>, audio.<fmt>, transcript.{txt,srt,vtt,tsv,json},
thumbnail.<ext>, info.json, subtitles (original captions if present).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
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


# ---- dependency checks -----------------------------------------------------
def need(tool: str, hint: str) -> str:
    path = shutil.which(tool)
    if not path:
        die(f"'{tool}' not found. Install it with: {hint}")
    return path


# ---- choices ---------------------------------------------------------------
WANTS = ["video", "audio", "transcript", "subs", "thumb", "info"]
UNSUPPORTED_LOCAL = {"video", "audio", "subs", "thumb"}


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
        die(f"could not read info for {url}\n{out.stderr.strip()}")
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


# ---- main per-target pipelines ---------------------------------------------
def process(url: str, wants: set[str], args, ytdlp: str) -> dict:
    say(f"\n{BOLD}▶ {url}{RESET}", CYAN)
    info = fetch_info(ytdlp, url)
    dest = target_dir(Path(args.output or "downloads"), info)
    say(f"  → {dest}", DIM)

    title = info.get("title", url)
    duration = info.get("duration")
    dur_str = f"{int(duration)//60}m{int(duration)%60:02d}s" if duration else "?"
    say(f"  {BOLD}{title}{RESET}  ({dur_str})")

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
    dur_str = f"{int(duration)//60}m{int(duration)%60:02d}s" if duration else "?"
    say(f"  {BOLD}{path.name}{RESET}  ({dur_str})")

    unsupported = wants & UNSUPPORTED_LOCAL
    if unsupported:
        say(f"  ℹ {', '.join(sorted(unsupported))} n/a for local files (already have the media)", YELLOW)

    if "info" in wants:
        info = {"file": str(path), "duration_seconds": duration, "size_bytes": path.stat().st_size}
        (dest / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))
        say("  ✓ info.json", GREEN)

    if "transcript" in wants:
        transcribe(path, dest, args)

    return {"title": path.name, "dir": str(dest)}


def transcribe(audio: Path, dest: Path, args) -> None:
    whisper = need("whisper-ctranslate2",
                   "uv tool install whisper-ctranslate2")
    say(f"  ✎ transcribing with whisper ({args.whisper_model}, task={args.task})…", YELLOW)
    cmd = [whisper, str(audio),
           "--model", args.whisper_model,
           "--output_dir", str(dest),
           "--output_format", args.transcript_format,
           "--task", args.task]
    if args.language:
        cmd += ["--language", args.language]
    run(cmd, quiet=True)
    # whisper names outputs after the audio stem -> normalize to transcript.*
    stem = audio.stem
    exts = ("txt", "srt", "vtt", "tsv", "json") if args.transcript_format == "all" else (args.transcript_format,)
    for ext in exts:
        src = dest / f"{stem}.{ext}"
        if src.exists():
            src.rename(dest / f"transcript.{ext}")
    shown = "{txt,srt,vtt,tsv,json}" if args.transcript_format == "all" else args.transcript_format
    say(f"  ✓ transcript.{shown}", GREEN)


# ---- cli -------------------------------------------------------------------
def main() -> None:
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
    args = p.parse_args()

    urls = list(args.urls)
    if args.file:
        urls += [ln.strip() for ln in Path(args.file).read_text().splitlines()
                 if ln.strip() and not ln.startswith("#")]
    if not urls:
        p.print_help()
        sys.exit(0)

    raw_want_given = bool(args.want)
    wants = parse_wants(args.want)
    targets = [(u, Path(u).expanduser()) for u in urls]
    ytdlp = need("yt-dlp", "brew install yt-dlp") if any(not p.is_file() for _, p in targets) else None

    targets_desc = ", ".join(sorted(wants)) if raw_want_given else "audio (URLs) / transcript (local files)"
    say(f"{BOLD}grab{RESET} — targets: {GREEN}{targets_desc}{RESET} "
        f"| {len(urls)} item(s)")

    results = []
    for raw, path in targets:
        try:
            if path.is_file():
                local_wants = wants if raw_want_given else {"transcript"}
                results.append(process_local(path, local_wants, args))
            else:
                results.append(process(raw, wants, args, ytdlp))
        except KeyboardInterrupt:
            die("interrupted")
        except Exception as e:  # noqa: BLE001
            say(f"  ✗ failed: {e}", RED)

    say(f"\n{BOLD}Done.{RESET} {len(results)}/{len(urls)} ok.", GREEN)
    for r in results:
        say(f"  • {r['title']}\n    {DIM}{r['dir']}{RESET}")


if __name__ == "__main__":
    main()
