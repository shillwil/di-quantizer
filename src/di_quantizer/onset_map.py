"""Onset map JSON read/write.

Enables reusing a tuned onset map across double/quad tracked guitar parts.
"""

from __future__ import annotations

import json


def save_onset_map(
    path: str,
    onset_times: list[float],
    snap_results: list[dict],
    metadata: dict | None = None,
) -> None:
    """Save onset map to JSON file.

    Args:
        path: Output file path.
        onset_times: Original onset times in seconds.
        snap_results: Snap results from grid.snap_to_grid().
        metadata: Optional metadata dict (bpm, grid_resolution, etc).
    """
    onset_map = {
        "metadata": metadata or {},
        "onsets": [
            {
                "original_sec": snap["original_sec"],
                "snapped_sec": snap["snapped_sec"],
                "delta_ms": snap["delta_ms"],
                "nearest_grid_label": snap["nearest_grid_label"],
            }
            for snap in snap_results
        ],
    }

    with open(path, "w") as f:
        json.dump(onset_map, f, indent=2)


def load_onset_map(path: str) -> dict:
    """Load onset map from JSON file.

    Args:
        path: Path to onset map JSON file.

    Returns:
        Dict with 'metadata' and 'onsets' keys.
    """
    with open(path) as f:
        return json.load(f)


def extract_times(onset_map: dict) -> tuple[list[float], list[float]]:
    """Extract original and snapped times from an onset map.

    Args:
        onset_map: Loaded onset map dict.

    Returns:
        Tuple of (original_times, snapped_times) in seconds.
    """
    original = [o["original_sec"] for o in onset_map["onsets"]]
    snapped = [o["snapped_sec"] for o in onset_map["onsets"]]
    return original, snapped
