from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Iterable


@dataclass
class Cut:
    start: float
    end: float
    kind: str
    label: str
    enabled: bool = True

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


PRESETS = {
    "Natural": {"silence_db": -38, "min_silence": 0.75, "keep_padding": 0.22},
    "Dinámico": {"silence_db": -36, "min_silence": 0.50, "keep_padding": 0.16},
    "Shorts": {"silence_db": -34, "min_silence": 0.35, "keep_padding": 0.10},
}

DEFAULT_FILLERS = {"eh", "emm", "em", "mmm", "este", "esto", "bueno", "digamos", "osea", "o sea"}


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def ensure_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg no está instalado o no está en PATH. Ejecuta install_windows.bat y vuelve a abrir la app.")
    return ffmpeg, ffprobe


def media_duration(path: Path) -> float:
    _, ffprobe = ensure_ffmpeg()
    proc = _run([ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", str(path)])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "No se pudo leer la duración del video.")
    return float(json.loads(proc.stdout)["format"]["duration"])


def detect_silences(path: Path, mode: str = "Natural") -> list[Cut]:
    ffmpeg, _ = ensure_ffmpeg()
    cfg = PRESETS.get(mode, PRESETS["Natural"])
    proc = _run([ffmpeg, "-hide_banner", "-i", str(path), "-af", f"silencedetect=noise={cfg['silence_db']}dB:d={cfg['min_silence']}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", proc.stderr)]
    duration = media_duration(path)
    cuts = []
    for idx, start in enumerate(starts):
        end = ends[idx] if idx < len(ends) else duration
        cut_start = start + cfg["keep_padding"]
        cut_end = end - cfg["keep_padding"]
        if cut_end - cut_start >= 0.08:
            cuts.append(Cut(cut_start, cut_end, "silencio", "Silencio / pausa larga"))
    return cuts


def _normalize_token(text: str) -> str:
    text = re.sub(r"[^a-záéíóúüñ0-9 ]+", "", text.lower().strip())
    return re.sub(r"\s+", " ", text)


def transcribe_words(path: Path, model_size: str = "small") -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Falta faster-whisper. Ejecuta install_windows.bat.") from exc
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(path), language="es", word_timestamps=True, vad_filter=True)
    words = []
    for segment in segments:
        for word in segment.words or []:
            words.append({"start": float(word.start), "end": float(word.end), "text": word.word.strip()})
    return words


def detect_fillers(words: list[dict], fillers: Iterable[str] | None = None) -> list[Cut]:
    filler_set = {_normalize_token(x) for x in (fillers or DEFAULT_FILLERS)}
    return [Cut(max(0.0, w["start"] - 0.03), w["end"] + 0.03, "muletilla", f"Muletilla: {w['text']}") for w in words if _normalize_token(w["text"]) in filler_set]


def detect_repetitions(words: list[dict]) -> list[Cut]:
    cuts = []
    tokens = [_normalize_token(w["text"]) for w in words]
    for i in range(1, len(words)):
        if tokens[i] and tokens[i] == tokens[i - 1]:
            cuts.append(Cut(words[i - 1]["start"], words[i - 1]["end"], "repetición", f"Repetición: {words[i - 1]['text']}"))
    for i in range(2, len(words) - 1):
        a, b = tokens[i - 2:i], tokens[i:i + 2]
        if all(a) and a == b:
            cuts.append(Cut(words[i - 2]["start"], words[i - 1]["end"], "repetición", "Frase repetida: " + " ".join(a)))
    return cuts


def merge_cuts(cuts: list[Cut], gap: float = 0.04) -> list[Cut]:
    if not cuts:
        return []
    cuts = sorted(cuts, key=lambda c: (c.start, c.end))
    merged = [cuts[0]]
    for cut in cuts[1:]:
        last = merged[-1]
        if cut.start <= last.end + gap and cut.kind == last.kind:
            last.end = max(last.end, cut.end)
            if cut.label not in last.label:
                last.label = f"{last.label}; {cut.label}"
        else:
            merged.append(cut)
    return merged


def invert_cuts(duration: float, cuts: list[Cut]) -> list[tuple[float, float]]:
    enabled = sorted((c for c in cuts if c.enabled), key=lambda c: c.start)
    if not enabled:
        return [(0.0, duration)]
    spans, cursor = [], 0.0
    for cut in enabled:
        start = max(0.0, min(duration, cut.start))
        end = max(start, min(duration, cut.end))
        if start > cursor + 0.01:
            spans.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < duration - 0.01:
        spans.append((cursor, duration))
    return [(s, e) for s, e in spans if e - s >= 0.05]


def export_video(source: Path, output: Path, cuts: list[Cut]) -> None:
    """Export using a filter script file instead of a huge command-line argument.

    Windows has a relatively small command-line length limit. A long video with
    hundreds of cuts made filter_complex exceed it and raised WinError 206.
    filter_complex_script keeps the command short regardless of cut count.
    """
    ffmpeg, _ = ensure_ffmpeg()
    duration = media_duration(source)
    keep = invert_cuts(duration, cuts)
    if not keep:
        raise RuntimeError("Los cortes eliminan todo el video. Desactiva algunos antes de exportar.")

    filter_parts, concat_inputs = [], []
    for i, (start, end) in enumerate(keep):
        filter_parts.append(f"[0:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS[v{i}]")
        filter_parts.append(f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs.append(f"[v{i}][a{i}]")
    filter_parts.append("".join(concat_inputs) + f"concat=n={len(keep)}:v=1:a=1[outv][outa]")
    filter_complex = ";\n".join(filter_parts)

    output.parent.mkdir(parents=True, exist_ok=True)
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".ffscript", delete=False) as script:
            script.write(filter_complex)
            script_path = Path(script.name)

        cmd = [ffmpeg, "-y", "-hide_banner", "-i", str(source), "-filter_complex_script", str(script_path), "-map", "[outv]", "-map", "[outa]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-4000:] or "FFmpeg no pudo exportar el video.")
    finally:
        if script_path:
            try:
                os.unlink(script_path)
            except OSError:
                pass
