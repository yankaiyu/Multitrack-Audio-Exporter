"""Float-only, stereo-linked transient control shared by audition and export.

The limiter operates relative to the selected audio's peak: zero drive is an
exact bypass, and positive drive raises the body without raising the original
peak. Later normalization owns output level. Intermediate math is double float.
"""
import array
import math
import subprocess
import sys
import json
from collections import deque


def validate_transient(value):
    if not isinstance(value, dict) or not isinstance(value.get("enabled", False), bool):
        raise ValueError("transientInvalid")
    try:
        drive = float(value.get("drive", 0))
    except (TypeError, ValueError):
        raise ValueError("transientInvalid") from None
    if not math.isfinite(drive) or not 0 <= drive <= 12:
        raise ValueError("transientInvalid")
    return {"enabled": value.get("enabled", False), "drive": drive}


def limit_audio(ffmpeg, ffprobe, source, output, peak_db, drive, register=None):
    """Bounded-memory, linked lookahead gain envelope; no integer PCM or clipping.

    A forward 5-ms minimum-gain window anticipates peaks. Exponential release
    (50-ms time constant) only slows recovery. A trailing 5-ms moving average
    smooths attack: every term contributing at frame t has already seen t, so
    their average is <= the gain required at t. Audio samples are never delayed,
    dropped or duplicated, including files shorter than the lookahead window.
    """
    drive = validate_transient({"enabled": True, "drive": drive})["drive"]
    metadata = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=channels,sample_rate', '-of', 'json', str(source)]))['streams'][0]
    channels, rate = int(metadata['channels']), int(metadata['sample_rate'])
    lookahead = max(1, round(rate * .005))
    recovery = -math.expm1(-1 / (rate * .05))
    drive_gain = 10 ** (drive / 20)
    ceiling = 10 ** (peak_db / 20) if peak_db is not None else 0
    processes = []
    try:
        decoder = subprocess.Popen([ffmpeg, '-v', 'error', '-i', str(source), '-f', 'f64le', '-'],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        processes.append(decoder)
        if register: register(decoder, True)
        encoder = subprocess.Popen([ffmpeg, '-v', 'error', '-y', '-f', 'f64le', '-ar', str(rate),
            '-ac', str(channels), '-i', '-', '-c:a', 'pcm_f32le', str(output)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(encoder)
        if register: register(encoder, True)
        pending, peaks, smoothing = deque(), deque(), deque()
        index = count = limited = 0
        previous = 1.0
        smooth_sum = 0.0
        max_reduction = 0.0
        output_chunk = array.array('d')

        def emit():
            nonlocal previous, smooth_sum, count, limited, max_reduction, output_chunk
            frame_index, frame = pending.popleft()
            while peaks and peaks[0][0] < frame_index:
                peaks.popleft()
            maximum = peaks[0][1] if peaks else 0
            required = min(1.0, ceiling / (maximum * drive_gain)) if maximum else 1.0
            previous = min(required, previous + (1 - previous) * recovery)
            if not smoothing:
                smoothing.extend([previous] * (lookahead + 1))
                smooth_sum = previous * (lookahead + 1)
            smooth_sum += previous - smoothing.popleft()
            smoothing.append(previous)
            gain = max(0.0, min(1.0, smooth_sum / len(smoothing)))
            reduction = -20 * math.log10(max(gain, 1e-30))
            max_reduction = max(max_reduction, reduction)
            limited += reduction > .1
            count += 1
            output_chunk.extend(value * drive_gain * gain for value in frame)
            if len(output_chunk) >= 8192:
                if sys.byteorder != 'little': output_chunk.byteswap()
                encoder.stdin.write(output_chunk.tobytes())
                output_chunk = array.array('d')

        while chunk := decoder.stdout.read(8192 * channels * 8):
            values = array.array('d'); values.frombytes(chunk)
            if sys.byteorder != 'little': values.byteswap()
            for i in range(0, len(values), channels):
                frame = values[i:i + channels]
                peak = max(map(abs, frame))
                while peaks and peaks[-1][1] <= peak: peaks.pop()
                peaks.append((index, peak))
                pending.append((index, frame))
                index += 1
                if len(pending) > lookahead: emit()
        while pending: emit()
        if sys.byteorder != 'little': output_chunk.byteswap()
        encoder.stdin.write(output_chunk.tobytes())
        encoder.stdin.close()
        if any(p.wait() != 0 for p in processes): raise ValueError('transientFailed')
        return {"maxReduction": round(max_reduction, 2), "limitedPercent": round(100 * limited / max(1, count), 2)}
    finally:
        for p in processes:
            if p.poll() is None: p.kill()
            p.wait()
            if p.stdout: p.stdout.close()
            if p.stdin and not p.stdin.closed: p.stdin.close()
            if register: register(p, False)


def reduction_stats(ffmpeg, before, after, channels, drive, run=None):
    """Measure the actual linked envelope, ignoring near-zero sample ratios.

    Streaming uses bounded memory. The denominator includes silent frames; a
    frame counts as limited when any measurable channel loses >0.1 dB relative
    to the driven input. Tiny numerical differences are not counted.
    """
    processes = []
    try:
        for path in (before, after):
            p = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(path),
                                  "-f", "f32le", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            processes.append(p)
            if run:
                run(p, True)
        maximum = limited = frames = 0
        gain = 10 ** (drive / 20)
        while True:
            chunks = [p.stdout.read(4096 * channels * 4) for p in processes]
            if not any(chunks):
                break
            if len(chunks[0]) != len(chunks[1]):
                raise ValueError("transientFailed")
            values = []
            for chunk in chunks:
                a = array.array("f"); a.frombytes(chunk)
                if sys.byteorder != "little":
                    a.byteswap()
                values.append(a)
            for i in range(0, len(values[0]), channels):
                # Largest channel avoids ratios around a zero crossing.
                c = max(range(channels), key=lambda c: abs(values[0][i + c]))
                original = abs(values[0][i + c]) * gain
                output = abs(values[1][i + c])
                reduction = max(0, 20 * math.log10(original / max(output, 1e-30))) if original > 1e-7 else 0
                maximum = max(maximum, reduction)
                limited += reduction > .1
                frames += 1
        if any(p.wait() != 0 for p in processes):
            raise ValueError("transientFailed")
        return {"maxReduction": round(maximum, 2), "limitedPercent": round(100 * limited / max(1, frames), 2)}
    finally:
        for p in processes:
            if p.poll() is None:
                p.kill()
            p.wait()
            p.stdout.close()
            if run:
                run(p, False)
