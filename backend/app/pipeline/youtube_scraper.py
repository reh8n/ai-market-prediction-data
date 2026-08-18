"""YouTube transcript acquisition.

Strategy: pull existing captions first (free, fast, no auth) via
youtube-transcript-api. Only if the video has no captions at all do we fall
back to downloading audio with yt-dlp and transcribing it with Whisper, which
is slow and costs compute.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings

settings = get_settings()

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


class ScrapeError(RuntimeError):
    pass


def parse_video_id(url_or_id: str) -> str:
    """Accept a full YouTube URL in any common shape, or a bare 11-char id."""
    value = url_or_id.strip()
    if _VIDEO_ID_RE.match(value):
        return value

    patterns = [
        r"(?:youtube\.com/watch\?(?:.*&)?v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/live/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            return match.group(1)

    raise ScrapeError(f"Could not parse a YouTube video id from: {url_or_id!r}")


@dataclass
class VideoMeta:
    video_id: str
    title: str | None = None
    channel: str | None = None
    published_at: str | None = None
    duration_seconds: float | None = None


@dataclass
class TranscriptResult:
    video_id: str
    text: str
    segments: list[dict] = field(default_factory=list)
    language: str | None = None
    method: str = "captions"
    duration_seconds: float | None = None
    meta: VideoMeta | None = None


def fetch_metadata(video_id: str) -> VideoMeta:
    """Best-effort metadata via yt-dlp. Never fatal - transcript is the payload."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return VideoMeta(video_id=video_id)

    options = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
    except Exception:
        return VideoMeta(video_id=video_id)

    upload_date = info.get("upload_date")  # YYYYMMDD
    published = (
        f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
        if upload_date and len(upload_date) == 8
        else None
    )
    return VideoMeta(
        video_id=video_id,
        title=info.get("title"),
        channel=info.get("uploader") or info.get("channel"),
        published_at=published,
        duration_seconds=(
            float(info["duration"]) if info.get("duration") is not None else None
        ),
    )


def _best_effort_transcript(transcript_list):
    """Pick a usable transcript when no exact English match exists.

    Regional English (`en-IN`, `en-AU`, ...) is already English, so it must be
    fetched directly. Asking YouTube to translate it into `en` fails - `en` is
    not in a regional English track's translation list - and that error used to
    look like "no captions" on videos that plainly had them.
    """
    tracks = list(transcript_list)

    for track in tracks:
        if (track.language_code or "").lower().startswith("en"):
            return track

    for track in tracks:
        if not track.is_translatable:
            continue
        available = {
            (lang.get("language_code") if isinstance(lang, dict) else lang.language_code)
            for lang in track.translation_languages
        }
        if "en" in available:
            return track.translate("en")

    # Untranslatable and not English: the raw text still beats nothing, since
    # extraction runs on a multilingual model.
    return tracks[0]


def fetch_captions(video_id: str, languages: list[str] | None = None) -> TranscriptResult:
    """Pull existing captions. Raises ScrapeError when the video has none."""
    from youtube_transcript_api import (
        CouldNotRetrieveTranscript,
        NoTranscriptFound,
        YouTubeTranscriptApi,
    )

    languages = languages or ["en", "en-US", "en-GB"]
    api = YouTubeTranscriptApi()

    try:
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(languages)
        except NoTranscriptFound:
            transcript = _best_effort_transcript(transcript_list)
        fetched = transcript.fetch()
        language = transcript.language_code
    except CouldNotRetrieveTranscript as exc:
        # Covers TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
        # IpBlocked, AgeRestricted, and the rest of the library's error tree.
        raise ScrapeError(f"No captions available for {video_id}: {exc}") from exc

    segments = [
        {"start": snippet.start, "duration": snippet.duration, "text": snippet.text}
        for snippet in fetched
    ]
    text = " ".join(seg["text"].replace("\n", " ") for seg in segments).strip()
    if not text:
        raise ScrapeError(f"Captions for {video_id} were empty")

    last = segments[-1] if segments else None
    duration = (
        (last.get("start") or 0) + (last.get("duration") or 0) if last else None
    )

    return TranscriptResult(
        video_id=video_id,
        text=text,
        segments=segments,
        language=language,
        method="captions",
        duration_seconds=duration,
    )


def transcribe_with_whisper(video_id: str) -> TranscriptResult:
    """Fallback path: download audio with yt-dlp, transcribe with faster-whisper."""
    if not settings.enable_whisper_fallback:
        raise ScrapeError(
            "No captions found and ENABLE_WHISPER_FALLBACK is false. "
            "Set it to true and `pip install faster-whisper` to transcribe audio."
        )

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ScrapeError(
            "Whisper fallback requested but faster-whisper is not installed. "
            "Run: pip install faster-whisper"
        ) from exc

    from yt_dlp import YoutubeDL

    audio_stem = settings.audio_path / video_id
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(audio_stem) + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }
        ],
    }
    try:
        with YoutubeDL(options) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    except Exception as exc:
        raise ScrapeError(f"Audio download failed for {video_id}: {exc}") from exc

    audio_file = Path(f"{audio_stem}.mp3")
    if not audio_file.exists():
        matches = list(settings.audio_path.glob(f"{video_id}.*"))
        if not matches:
            raise ScrapeError(f"Audio file not found after download for {video_id}")
        audio_file = matches[0]

    model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
    whisper_segments, info = model.transcribe(str(audio_file))

    segments = [
        {"start": seg.start, "duration": seg.end - seg.start, "text": seg.text.strip()}
        for seg in whisper_segments
    ]
    text = " ".join(seg["text"] for seg in segments).strip()
    if not text:
        raise ScrapeError(f"Whisper produced an empty transcript for {video_id}")

    return TranscriptResult(
        video_id=video_id,
        text=text,
        segments=segments,
        language=getattr(info, "language", None),
        method="whisper",
        duration_seconds=getattr(info, "duration", None),
    )


def scrape_youtube(url_or_id: str) -> TranscriptResult:
    """Captions first, Whisper only as a fallback."""
    video_id = parse_video_id(url_or_id)
    meta = fetch_metadata(video_id)

    try:
        result = fetch_captions(video_id)
    except ScrapeError:
        result = transcribe_with_whisper(video_id)

    result.meta = meta
    if result.duration_seconds is None:
        result.duration_seconds = meta.duration_seconds
    return result


def write_transcript_file(source_id: int, result: TranscriptResult) -> Path:
    """Persist the raw transcript to disk; the DB stores only the path."""
    path = settings.transcripts_path / f"{source_id}.json"
    payload = {
        "source_id": source_id,
        "video_id": result.video_id,
        "url": f"https://www.youtube.com/watch?v={result.video_id}",
        "title": result.meta.title if result.meta else None,
        "channel": result.meta.channel if result.meta else None,
        "published_at": result.meta.published_at if result.meta else None,
        "language": result.language,
        "method": result.method,
        "duration_seconds": result.duration_seconds,
        "text": result.text,
        "segments": result.segments,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_transcript_text(path: str | Path) -> str | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text(encoding="utf-8")).get("text")
    except (json.JSONDecodeError, OSError):
        return None
