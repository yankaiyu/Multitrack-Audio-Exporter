"""Conservative transient suggestions and non-destructive local gain envelopes.

All times use the original track timeline. Detection never changes audio.
The same sample-accurate envelope is used for preview and export, before
normalization. Stereo channels share one envelope to preserve their balance.
"""
from __future__ import annotations

import array
import math
import subprocess
import sys
from pathlib import Path


def validate_edits(edits: object, duration: float | None = None) -> list[dict]:
    if not isinstance(edits, list) or len(edits) > 100:
        raise ValueError("peakInvalidEdits")
    result = []
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("peakInvalidEdits")
        try:
            start, end, db = (float(edit[k]) for k in ("start", "end", "db"))
        except (KeyError, TypeError, ValueError):
            raise ValueError("peakInvalidEdits") from None
        if (not all(math.isfinite(v) for v in (start, end, db)) or
                start < 0 or end <= start or db > 0 or db < -60 or
                (duration is not None and end > duration + .001)):
            raise ValueError("peakInvalidEdits")
        result.append({"start": start, "end": end, "db": db})
    return sorted(result, key=lambda e: e["start"])


def envelope_filter(channels: int, edits: list[dict]) -> str:
    """Sanitize float data and apply smoothly ramped attenuation (never boost).

    Overlaps use the strongest attenuation, rather than multiplying gains.
    10 ms (or half of a shorter region) ramps prevent discontinuities.
    """
    gain = "1"
    for edit in validate_edits(edits):
        a, b, db = edit["start"], edit["end"], edit["db"]
        fade = min(.01, (b - a) / 2)
        strength = 1 - 10 ** (db / 20)
        region = (f"1-{strength:.12g}*max(0,min(1,min((t-{a:.9f})/{fade:.12g},"
                  f"({b:.9f}-t)/{fade:.12g})))")
        gain = f"min({gain},{region})"
    expressions = "|".join(
        f"if(isnan(val({c}))+isinf(val({c})),0,val({c}))*({gain})" for c in range(channels))
    return f"aeval=exprs='{expressions}':c=same"


def suggest_regions(peaks: list[float], step: float, offset: float, end: float) -> list[dict]:
    """Flag unusually isolated peaks, not ordinary repeated drum transients."""
    finite = [v if math.isfinite(v) else 0 for v in peaks]
    if len(finite) < 20:
        return []
    ordered = sorted(finite)
    global_reference = ordered[min(len(ordered) - 1, int(len(ordered) * .95))]
    suggestions = []
    for i, peak in enumerate(finite):
        if peak < .01 or peak < global_reference * 4:
            continue
        if i and peak < finite[i - 1] or i + 1 < len(finite) and peak <= finite[i + 1]:
            continue
        neighbours = finite[max(0, i - 200):max(0, i - 5)] + finite[i + 6:i + 201]
        if len(neighbours) < 10:
            continue
        neighbours.sort()
        reference = max(global_reference, neighbours[int(len(neighbours) * .9)], 1e-6)
        if peak < reference * 4:
            continue
        left = right = i
        while left > 0 and finite[left - 1] > reference * 2:
            left -= 1
        while right + 1 < len(finite) and finite[right + 1] > reference * 2:
            right += 1
        if (right - left + 1) * step > .3:
            continue
        start = max(offset, offset + left * step - .02)
        stop = min(end, offset + (right + 1) * step + .02)
        if suggestions and start <= suggestions[-1]["end"]:
            continue
        suggestions.append({"start": start, "end": stop, "time": min(end, offset + (i + .5) * step),
                            "db": round(max(-30, min(-3, 20 * math.log10(reference * 2 / peak))), 1),
                            "peak": round(20 * math.log10(peak), 2)})
        if len(suggestions) == 100:
            break
    return suggestions


def detect_peaks(ffmpeg: str, path: Path, channels: int, rate: int,
                 start: float, end: float, track_process=None) -> list[dict]:
    """Stream float samples in 10 ms blocks; memory scales with time, not PCM size."""
    frames = max(1, round(rate * .01))
    command = [ffmpeg, "-v", "error", "-i", str(path), "-af",
               f"asetpts=PTS-STARTPTS,atrim=start={start}:end={end},{envelope_filter(channels, [])}",
               "-f", "f32le", "-c:a", "pcm_f32le", "-"]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        if track_process:
            track_process(process, True)
        peaks = []
        try:
            while chunk := process.stdout.read(frames * channels * 4):
                if len(chunk) % 4:
                    raise ValueError("peakAnalysisFailed")
                values = array.array("f")
                values.frombytes(chunk)
                if sys.byteorder != "little":
                    values.byteswap()
                peaks.append(max(map(abs, values), default=0))
            if process.wait() != 0:
                raise ValueError("peakAnalysisFailed")
        except BaseException:
            process.kill()
            process.wait()
            raise
        finally:
            if track_process:
                track_process(process, False)
    return suggest_regions(peaks, frames / rate, start, end)
