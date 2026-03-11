"""Grid math — BPM + time signature to grid positions and onset snapping."""

from __future__ import annotations

import numpy as np


# Map resolution strings to subdivision divisors (relative to quarter note)
_RESOLUTION_MAP: dict[str, float] = {
    "4": 1.0,       # quarter notes
    "8": 2.0,       # eighth notes
    "16": 4.0,      # sixteenth notes
    "32": 8.0,      # thirty-second notes
    "8t": 3.0,      # eighth-note triplets (3 per beat)
    "16t": 6.0,     # sixteenth-note triplets (6 per beat)
}


def build_grid(
    bpm: float,
    time_signature: str = "4/4",
    grid_resolution: str = "16",
    duration_sec: float = 180.0,
) -> np.ndarray:
    """Generate array of all grid positions in seconds.

    Args:
        bpm: Tempo in beats per minute.
        time_signature: Time signature string like "4/4", "7/8", "5/4".
        grid_resolution: Subdivision: "4", "8", "16", "32", "8t", "16t".
        duration_sec: Duration in seconds to generate grid for.

    Returns:
        Sorted array of grid positions in seconds.
    """
    if grid_resolution not in _RESOLUTION_MAP:
        raise ValueError(
            f"Unsupported grid resolution '{grid_resolution}'. "
            f"Supported: {', '.join(_RESOLUTION_MAP)}"
        )

    subdivisions_per_beat = _RESOLUTION_MAP[grid_resolution]

    # Grid interval: time per subdivision
    beat_duration = 60.0 / bpm
    grid_interval = beat_duration / subdivisions_per_beat

    # Generate grid from 0 to duration
    n_points = int(duration_sec / grid_interval) + 1
    grid = np.arange(n_points) * grid_interval

    # Trim to duration
    grid = grid[grid <= duration_sec + 1e-9]

    return grid


def snap_to_grid(
    onset_times: list[float],
    grid: np.ndarray,
    quantize_strength: float = 1.0,
    bpm: float = 120.0,
    time_signature: str = "4/4",
    grid_resolution: str = "16",
) -> list[dict]:
    """Snap onset times to nearest grid positions.

    Args:
        onset_times: Detected onset times in seconds.
        grid: Grid positions array from build_grid().
        quantize_strength: 0.0 = no snap, 1.0 = hard snap.
        bpm: BPM (for grid label computation).
        time_signature: Time signature string (for grid label computation).
        grid_resolution: Grid resolution string (for grid label computation).

    Returns:
        List of dicts with original_sec, snapped_sec, delta_ms, nearest_grid_label.
    """
    if len(grid) == 0:
        return []

    results = []
    for onset in onset_times:
        # Find nearest grid point
        idx = int(np.argmin(np.abs(grid - onset)))
        nearest_grid = grid[idx]

        # Apply quantize strength
        snapped = onset + (nearest_grid - onset) * quantize_strength
        delta_ms = (snapped - onset) * 1000.0

        label = _grid_label(nearest_grid, bpm, time_signature, grid_resolution)

        results.append({
            "original_sec": round(onset, 6),
            "snapped_sec": round(snapped, 6),
            "delta_ms": round(delta_ms, 2),
            "nearest_grid_label": label,
        })

    return results


def _grid_label(
    time_sec: float,
    bpm: float,
    time_signature: str = "4/4",
    grid_resolution: str = "16",
) -> str:
    """Generate a bar.beat.subdivision label for a grid position.

    Args:
        time_sec: Time in seconds.
        bpm: Tempo.
        time_signature: Time signature string.
        grid_resolution: Grid resolution string.

    Returns:
        Label like "1.1", "1.2.3", "2.1.1".
    """
    parts = time_signature.split("/")
    beats_per_bar = int(parts[0])

    beat_duration = 60.0 / bpm
    subdivisions_per_beat = _RESOLUTION_MAP.get(grid_resolution, 4.0)

    # Total beats from start
    total_beats = time_sec / beat_duration
    bar = int(total_beats // beats_per_bar) + 1
    beat_in_bar = int(total_beats % beats_per_bar) + 1

    # Subdivision within the beat
    beat_start = (total_beats % 1.0) * subdivisions_per_beat
    subdivision = int(round(beat_start)) + 1

    if subdivisions_per_beat <= 1:
        return f"{bar}.{beat_in_bar}"
    else:
        return f"{bar}.{beat_in_bar}.{subdivision}"
