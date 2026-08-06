"""Deterministic narrated-slide renderer for LearnHub Studio.

The worker creates branded PNG slides, obtains grounded narration through
Gemini TTS, and combines them into an H.264/AAC MP4 with FFmpeg. No user data or
model-generated imagery is involved.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import math
import shutil
import subprocess
import textwrap
import wave
from collections.abc import Awaitable, Callable
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from PIL import Image, ImageDraw, ImageFont, features

from app.config import settings
from app.db.supabase import get_supabase

WIDTH, HEIGHT = 1920, 1080
BG = "#050816"
SURFACE = "#0d1424"
TEXT = "#ffffff"
MUTED = "#94a3b8"
ACCENT = "#00d4aa"


def _font(size: int, *, urdu: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"] if urdu else []
    ) + [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def _text_from_blocks(section: dict) -> str:
    parts: list[str] = []
    for block in section.get("blocks", []):
        if block.get("text"):
            parts.append(block["text"])
        elif block.get("lines"):
            parts.extend(block["lines"])
        elif block.get("head") and block.get("rows"):
            parts.append(". ".join(block["head"]))
            parts.extend(". ".join(row) for row in block["rows"][:3])
    return " ".join(parts)


def _segments(pack: dict) -> list[tuple[str, str]]:
    lesson = pack["lesson"]
    output = [(lesson["title"], lesson.get("subtitle", ""))]
    output.extend((section["heading"], _text_from_blocks(section)) for section in lesson["sections"])
    output.append(("Key takeaways", " ".join(pack.get("notes", []))))
    if pack.get("keyTerms"):
        output.append(("Key terms", ". ".join(pack["keyTerms"])))
    questions = []
    for question in lesson.get("quiz", []):
        options = question.get("options") or []
        correct = question.get("correct", -1)
        answer = options[correct] if 0 <= correct < len(options) else ""
        questions.append(
            f"Question: {question.get('q', '')} Correct answer: {answer}. "
            f"{question.get('explanation', '')}"
        )
    if questions:
        output.append(("Knowledge check", " ".join(questions)))
    flashcards = [
        f"{card.get('front', '')}: {card.get('back', '')}"
        for card in pack.get("flashcards", [])
    ]
    if flashcards:
        output.append(("Flashcard recap", ". ".join(flashcards)))
    return [(title, body.strip()) for title, body in output if body.strip()]


def _render_slide(path: Path, title: str, body: str, *, urdu: bool) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((110, 95, WIDTH - 110, HEIGHT - 95), radius=32, fill=SURFACE, outline="#1b2942", width=2)
    draw.rounded_rectangle((110, 95, 126, HEIGHT - 95), radius=8, fill=ACCENT)
    title_font = _font(64, urdu=urdu)
    body_font = _font(36, urdu=urdu)
    small_font = _font(24, urdu=urdu)
    direction = "rtl" if urdu else "ltr"
    anchor = "ra" if urdu else "la"
    x = WIDTH - 180 if urdu else 180
    direction_args = {"direction": direction} if features.check_feature("raqm") else {}
    draw.text((x, 165), title, font=title_font, fill=TEXT, anchor=anchor, **direction_args)
    wrapped = textwrap.wrap(body, width=72 if not urdu else 58)[:11]
    draw.multiline_text(
        (x, 295), "\n".join(wrapped), font=body_font, fill=MUTED,
        spacing=20, anchor=anchor, **direction_args,
    )
    draw.text(
        (x, HEIGHT - 155), "NafaIQ LearnHub · Educational content only",
        font=small_font, fill=ACCENT, anchor=anchor, **direction_args,
    )
    image.save(path, "PNG", optimize=True)


async def _tts(text: str, output: Path) -> None:
    keys = settings.gemini_api_key_pool
    if not keys:
        raise RuntimeError("Gemini API key is not configured")
    body = {
        "contents": [{"parts": [{"text": "Read this educational PSX lecture clearly and naturally:\n\n" + text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Kore"}}},
        },
    }
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=120) as client:
        for key in keys:
            try:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{settings.learn_studio_tts_model}:generateContent",
                    params={"key": key}, json=body,
                )
                response.raise_for_status()
                inline = response.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                audio = base64.b64decode(inline["data"])
                mime = inline.get("mimeType", "")
                if "wav" in mime:
                    output.write_bytes(audio)
                else:
                    with wave.open(str(output), "wb") as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(24000)
                        wav.writeframes(audio)
                return
            except Exception as exc:
                last = exc
    raise RuntimeError("Gemini narration failed") from last


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def _write_vtt(path: Path, segments: list[tuple[str, str]], total: float) -> None:
    slice_seconds = total / len(segments)
    lines = ["WEBVTT", ""]
    for index, (title, body) in enumerate(segments):
        lines.extend([
            f"{_timestamp(index * slice_seconds)} --> {_timestamp(min(total, (index + 1) * slice_seconds))}",
            f"{title}. {body}", "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


def _render_video(
    slides: list[Path], audio: Path, output: Path, duration: float, audio_tempo: float
) -> None:
    per_slide = duration / len(slides)
    # A concat demuxer keeps only one still image decoded at a time. The former
    # multi-input filter graph held every 1080p loop in memory concurrently and
    # was OOM-killed on the Railway worker during a real four-slide render.
    concat = output.parent / "slides.ffconcat"
    lines = ["ffconcat version 1.0"]
    for slide in slides:
        escaped = str(slide).replace("'", "'\\''")
        lines.extend([f"file '{escaped}'", f"duration {per_slide:.3f}"])
    # concat requires the last frame to be repeated for its duration to apply.
    lines.append(f"file '{str(slides[-1]).replace("'", "'\\''")}'")
    concat.write_text("\n".join(lines), encoding="utf-8")
    command = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-i", str(audio), "-vf", "scale=1280:720,fps=24,format=yuv420p",
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264",
        "-preset", "veryfast", "-threads", "1", "-crf", "23", "-c:a", "aac",
        "-filter:a", f"atempo={audio_tempo:.5f}", "-b:a", "160k", "-shortest",
        "-movflags", "+faststart", str(output),
    ]
    subprocess.run(command, check=True, capture_output=True)


async def _upload(path: Path, object_path: str, content_type: str) -> None:
    payload = path.read_bytes()
    def run() -> None:
        get_supabase().storage.from_(settings.learn_studio_media_bucket).upload(
            object_path, payload, {"content-type": content_type, "upsert": "true"}
        )
    await asyncio.to_thread(run)


async def render_study_pack_video(
    project_id: str,
    pack: dict,
    lang: str,
    on_rendering: Callable[[], Awaitable[None]] | None = None,
) -> dict:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and ffprobe are required by the Studio worker")
    segments = _segments(pack)
    narration = "\n\n".join(f"{title}. {body}" for title, body in segments)
    with TemporaryDirectory(prefix="nafaiq-studio-") as tmp:
        root = Path(tmp)
        slides = []
        for index, (title, body) in enumerate(segments):
            path = root / f"slide-{index:03}.png"
            _render_slide(path, title, body, urdu=lang == "ur")
            slides.append(path)
        audio = root / "narration.wav"
        await _tts(narration, audio)
        raw_seconds = _duration(audio)
        # Keep the promised 3–5 minute format while limiting tempo correction
        # to a natural-sounding range. The expanded grounded recap above makes
        # the lower quality gate attainable without padding the video silently.
        seconds = min(300.0, max(180.0, raw_seconds))
        audio_tempo = raw_seconds / seconds
        if not 0.65 <= audio_tempo <= 2.0:
            raise RuntimeError("Narration duration failed the 3–5 minute quality gate")
        if on_rendering:
            await on_rendering()
        video = root / "lesson.mp4"
        captions = root / "captions.vtt"
        _write_vtt(captions, segments, seconds)
        await asyncio.to_thread(_render_video, slides, audio, video, seconds, audio_tempo)
        prefix = f"generated/{project_id}"
        await asyncio.gather(
            _upload(video, f"{prefix}/lesson.mp4", "video/mp4"),
            _upload(captions, f"{prefix}/captions.vtt", "text/vtt"),
            _upload(slides[0], f"{prefix}/poster.png", "image/png"),
        )
        return {
            "video_path": f"{prefix}/lesson.mp4",
            "captions_path": f"{prefix}/captions.vtt",
            "thumbnail_path": f"{prefix}/poster.png",
            "duration_seconds": math.ceil(seconds),
        }
