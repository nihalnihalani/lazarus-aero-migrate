#!/usr/bin/env python3
"""Gemini transcription in video-use's transcript schema — a drop-in for
ElevenLabs Scribe (video-use/helpers/transcribe.py). Uses the Gemini API
(GEMINI_API_KEY) instead of ELEVENLABS_API_KEY.

  GEMINI_API_KEY=... python launch/transcribe_gemini.py <video> <out.json>

Output: {"words": [{"text","start","end","type":"word"}, ...], ...} — the shape
video-use/helpers/render.py reads to build burned-in captions. We ask Gemini for
phrase-level segments (LLMs time phrases far more reliably than single words) and
expand each phrase to evenly-spaced word timestamps.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
from google import genai
from google.genai import types

PROMPT = (
    "Transcribe the spoken narration in this audio precisely. "
    "Return ONLY valid JSON (no markdown, no prose): an array of segments in "
    "chronological order that together cover the whole audio. Each segment is "
    '{"text": "<a short spoken phrase, 3-8 words>", "start": <seconds, number>, '
    '"end": <seconds, number>}. Timestamps are seconds from the audio start, '
    "increasing and non-overlapping. Transcribe exactly what is said."
)

def extract_audio(video: Path, dest: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(dest)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main() -> int:
    if len(sys.argv) != 3:
        print("usage: transcribe_gemini.py <video> <out.json>", file=sys.stderr); return 2
    video, out = Path(sys.argv[1]), Path(sys.argv[2])
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY not set", file=sys.stderr); return 1

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        extract_audio(video, wav)
        audio = wav.read_bytes()

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.environ.get("LAZ_ASR_MODEL", "gemini-2.5-flash")
    resp = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=audio, mime_type="audio/wav"), PROMPT],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    raw = (resp.text or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    segs = json.loads(raw)

    words: list[dict] = []
    for s in segs:
        text = str(s.get("text", "")).strip()
        st, en = float(s.get("start", 0)), float(s.get("end", 0))
        toks = [w for w in re.split(r"\s+", text) if w]
        if not toks or en <= st:
            continue
        step = (en - st) / len(toks)
        for i, w in enumerate(toks):
            words.append({"text": w, "start": round(st + i * step, 3),
                          "end": round(st + (i + 1) * step, 3), "type": "word"})

    payload = {"words": words, "language_code": "en",
               "text": " ".join(w["text"] for w in words)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {len(words)} words ({len(segs)} segments) via {model} -> {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
