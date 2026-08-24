"""Unit tests for offscript's pure logic — no network, no models, no media needed.

Run with:  pytest
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from offscript import (  # noqa: E402
    cache_dir_name,
    classify,
    human,
    model_is_cached,
    parse_wants,
)


class TestClassify:
    """A path that was clearly meant as a file must never be sent to yt-dlp:
    the resulting 'not a valid URL' error blames the wrong thing and hides the
    real cause (typo, unreadable folder, volume not mounted)."""

    def test_existing_file_is_local(self, tmp_path):
        f = tmp_path / "note.ogg"
        f.write_bytes(b"")
        assert classify(str(f), f) == "local"

    def test_explicit_schemes_are_urls(self):
        for raw in (
            "https://youtu.be/abc123",
            "http://example.com/v/1",
            "https://cdn.example.com/audio.mp3",
        ):
            assert classify(raw, Path(raw)) == "url"

    def test_bare_domain_and_ytdlp_shorthand_are_urls(self):
        for raw in ("youtube.com/watch?v=x", "ytsearch:some song"):
            assert classify(raw, Path(raw)) == "url"

    def test_absolute_path_that_does_not_exist_is_missing(self):
        raw = "/nonexistent-root-dir/Downloads/x.ogg"
        assert classify(raw, Path(raw)) == "missing"

    def test_relative_and_bare_media_names_are_missing(self):
        for raw in ("./relative.wav", "../up.mp3", "just-a-name.mp4"):
            assert classify(raw, Path(raw).expanduser()) == "missing"

    def test_directory_is_missing_not_url(self, tmp_path):
        assert classify(str(tmp_path), tmp_path) == "missing"


class TestParseWants:
    def test_defaults_to_audio(self):
        assert parse_wants([]) == {"audio"}

    def test_comma_and_repeated_flags_merge(self):
        assert parse_wants(["audio,transcript", "info"]) == {"audio", "transcript", "info"}

    def test_all_expands(self):
        assert parse_wants(["all"]) == {
            "video", "audio", "transcript", "subs", "thumb", "info",
        }


class TestModelIsCached:
    """Real cache directory names, as produced by faster-whisper's repo map."""

    CACHE = [
        ("models--Systran--faster-whisper-small", 0),
        ("models--Systran--faster-distil-whisper-large-v3", 0),
        ("models--mobiuslabsgmbh--faster-whisper-large-v3-turbo", 0),
    ]

    def test_matches_plain_name(self):
        assert model_is_cached("small", self.CACHE)

    def test_matches_distil_whose_repo_reorders_the_words(self):
        # "distil-large-v3" is NOT a substring of "faster-distil-whisper-large-v3"
        assert model_is_cached("distil-large-v3", self.CACHE)

    def test_matches_turbo_under_a_different_org(self):
        assert model_is_cached("turbo", self.CACHE)
        assert model_is_cached("large-v3-turbo", self.CACHE)

    def test_absent_model_is_not_cached(self):
        assert not model_is_cached("medium", self.CACHE)

    def test_small_does_not_match_distil_small_en(self):
        assert not model_is_cached("small", [("models--Systran--faster-distil-whisper-small.en", 0)])

    def test_plain_small_does_not_match_large(self):
        assert not model_is_cached("large-v3", self.CACHE)

    def test_empty_cache(self):
        assert not model_is_cached("small", [])


class TestCacheDirName:
    def test_slash_becomes_double_dash(self):
        assert cache_dir_name("Systran/faster-whisper-small") == "models--Systran--faster-whisper-small"


class TestHuman:
    def test_scales_units(self):
        assert human(512) == "512 B"
        assert human(2 * 1024) == "2 KB"
        assert human(5 * 1024**2) == "5 MB"
        assert human(int(1.4 * 1024**3)) == "1.4 GB"
