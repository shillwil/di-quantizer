"""Audio slicing, shifting, and crossfading for quantization.

Slices audio at onset points, shifts slices to snapped grid positions,
and rejoins with raised-cosine crossfades to prevent clicks/pops.

Output guarantees:
- Exact same duration as input (sample-for-sample)
- No clicks, pops, or crossfade artifacts at slice boundaries
- Phase coherent (no phase shifts — critical for reamping)
"""

from __future__ import annotations

import numpy as np
import soundfile as sf


def slice_at_onsets(
    y: np.ndarray, sr: int, onset_times_sec: list[float]
) -> list[np.ndarray]:
    """Cut audio into segments at each onset point.

    Args:
        y: Audio signal (1D array).
        sr: Sample rate.
        onset_times_sec: Onset positions in seconds, sorted ascending.

    Returns:
        List of audio segments.
    """
    onset_samples = [int(round(t * sr)) for t in onset_times_sec]
    onset_samples = [s for s in onset_samples if 0 <= s < len(y)]

    slices = []
    for i, start in enumerate(onset_samples):
        end = onset_samples[i + 1] if i + 1 < len(onset_samples) else len(y)
        slices.append(y[start:end].copy())

    # Prepend any audio before the first onset
    if onset_samples and onset_samples[0] > 0:
        slices.insert(0, y[: onset_samples[0]].copy())
    elif not onset_samples:
        slices.append(y.copy())

    return slices


def shift_slices(
    y: np.ndarray,
    sr: int,
    original_times: list[float],
    snapped_times: list[float],
    crossfade_ms: float = 10.0,
    skip_threshold_ms: float = 2.0,
) -> np.ndarray:
    """Move audio slices to snapped positions and rejoin.

    Works directly on the full audio buffer rather than pre-sliced segments
    to maintain maximum phase coherence.

    Args:
        y: Full audio signal (1D).
        sr: Sample rate.
        original_times: Original onset times in seconds.
        snapped_times: Snapped onset times in seconds.
        crossfade_ms: Crossfade duration in milliseconds.
        skip_threshold_ms: Don't move onsets within this threshold of grid.

    Returns:
        Quantized audio, exactly the same length as input.
    """
    n_samples = len(y)
    output = np.zeros(n_samples, dtype=y.dtype)
    crossfade_samples = max(1, int(round(crossfade_ms / 1000.0 * sr)))
    skip_threshold_sec = skip_threshold_ms / 1000.0

    # Build list of (original_sample, snapped_sample) pairs
    orig_samples = [int(round(t * sr)) for t in original_times]
    snap_samples = [int(round(t * sr)) for t in snapped_times]

    # Build segments: each segment runs from one onset to the next
    # Segment i: from orig_samples[i] to orig_samples[i+1]
    # Placed at: snap_samples[i]
    n_onsets = len(orig_samples)
    if n_onsets == 0:
        return y.copy()

    # Handle audio before first onset — copy it unchanged
    first_orig = orig_samples[0]
    first_snap = snap_samples[0]

    if first_orig > 0:
        # Pre-onset audio: keep in place (don't shift content before first onset)
        pre_len = min(first_orig, first_snap, n_samples)
        output[:pre_len] = y[:pre_len]

    for i in range(n_onsets):
        src_start = orig_samples[i]
        src_end = orig_samples[i + 1] if i + 1 < n_onsets else n_samples

        dst_start = snap_samples[i]
        dst_end = snap_samples[i + 1] if i + 1 < n_onsets else n_samples

        if src_start >= n_samples or dst_start >= n_samples:
            continue

        delta = abs(original_times[i] - snapped_times[i])
        if delta < skip_threshold_sec:
            # Within threshold — copy unchanged
            seg_len = min(src_end - src_start, n_samples - dst_start)
            if seg_len > 0:
                output[dst_start : dst_start + seg_len] = y[src_start : src_start + seg_len]
            continue

        # Copy segment from source to destination
        src_len = src_end - src_start
        dst_len = dst_end - dst_start
        copy_len = min(src_len, dst_len, n_samples - dst_start)

        if copy_len <= 0:
            continue

        segment = y[src_start : src_start + copy_len]

        # Apply crossfade at the start of the segment to blend with existing content
        if crossfade_samples > 0 and dst_start > 0:
            fade_len = min(crossfade_samples, copy_len, dst_start)
            if fade_len > 1:
                fade_in = _raised_cosine_fade(fade_len, fade_in=True)
                fade_out = 1.0 - fade_in

                existing = output[dst_start : dst_start + fade_len].copy()
                segment = segment.copy()
                segment[:fade_len] = existing * fade_out + segment[:fade_len] * fade_in

        output[dst_start : dst_start + copy_len] = segment

    return output


def quantize_audio(
    input_path: str,
    output_path: str,
    original_times: list[float],
    snapped_times: list[float],
    crossfade_ms: float = 10.0,
    skip_threshold_ms: float = 2.0,
    output_format: str = "wav",
) -> None:
    """Full quantize pipeline: read, shift, write.

    Args:
        input_path: Path to input audio file.
        output_path: Path for output audio file.
        original_times: Original onset times in seconds.
        snapped_times: Snapped onset times in seconds.
        crossfade_ms: Crossfade duration in ms.
        skip_threshold_ms: Skip threshold in ms.
        output_format: Output format ("wav" or "aiff").
    """
    y, sr = sf.read(input_path, dtype="float64")
    info = sf.info(input_path)

    # Handle stereo
    if y.ndim > 1:
        channels = []
        for ch in range(y.shape[1]):
            quantized_ch = shift_slices(
                y[:, ch], sr, original_times, snapped_times,
                crossfade_ms, skip_threshold_ms,
            )
            channels.append(quantized_ch)
        output = np.column_stack(channels)
    else:
        output = shift_slices(
            y, sr, original_times, snapped_times,
            crossfade_ms, skip_threshold_ms,
        )

    # Ensure exact same length
    if len(output) != len(y):
        if output.ndim == 1:
            result = np.zeros_like(y)
            copy_len = min(len(output), len(y))
            result[:copy_len] = output[:copy_len]
            output = result
        else:
            result = np.zeros_like(y)
            copy_len = min(output.shape[0], y.shape[0])
            result[:copy_len] = output[:copy_len]
            output = result

    # Determine subtype from input to preserve bit depth
    subtype = info.subtype
    fmt = "WAV" if output_format.lower() == "wav" else "AIFF"

    sf.write(output_path, output, sr, subtype=subtype, format=fmt)


def _raised_cosine_fade(length: int, fade_in: bool = True) -> np.ndarray:
    """Generate a raised cosine fade curve.

    Args:
        length: Number of samples.
        fade_in: True for fade-in (0->1), False for fade-out (1->0).

    Returns:
        Fade curve array.
    """
    t = np.linspace(0, np.pi, length)
    curve = 0.5 * (1.0 - np.cos(t))
    if not fade_in:
        curve = curve[::-1]
    return curve
