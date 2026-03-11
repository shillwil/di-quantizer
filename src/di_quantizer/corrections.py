"""Parse user corrections and adjust detection parameters.

Deterministic parameter adjustment based on user feedback — NOT machine learning.
"""

from __future__ import annotations

import json


def load_corrections(path: str) -> dict:
    """Load corrections JSON file.

    Expected format:
    {
        "missed_onsets": [{"time_sec": 1.482, "note": "palm mute"}],
        "false_positives": [{"index": 14, "note": "string noise"}],
        "threshold_hint": "more_sensitive"  // or "less_sensitive"
    }

    Args:
        path: Path to corrections JSON file.

    Returns:
        Corrections dict.
    """
    with open(path) as f:
        return json.load(f)


def apply_corrections(
    current_params: dict,
    corrections: dict,
) -> dict:
    """Adjust detection parameters based on user corrections.

    Args:
        current_params: Current detection parameter dict.
        corrections: Corrections dict from load_corrections().

    Returns:
        Adjusted parameter dict.
    """
    params = current_params.copy()

    missed = corrections.get("missed_onsets", [])
    false_pos = corrections.get("false_positives", [])
    hint = corrections.get("threshold_hint", "")

    # Adjust sensitivity based on correction counts
    sensitivity = params.get("sensitivity", 0.5)

    if len(missed) > len(false_pos):
        # More missed than false positives — increase sensitivity
        adjustment = min(0.15, len(missed) * 0.03)
        sensitivity = min(1.0, sensitivity + adjustment)
    elif len(false_pos) > len(missed):
        # More false positives — decrease sensitivity
        adjustment = min(0.15, len(false_pos) * 0.03)
        sensitivity = max(0.0, sensitivity - adjustment)

    # Apply direct hint
    if hint == "more_sensitive":
        sensitivity = min(1.0, sensitivity + 0.1)
    elif hint == "less_sensitive":
        sensitivity = max(0.0, sensitivity - 0.1)

    params["sensitivity"] = round(sensitivity, 2)

    # If missed onsets exist, also reduce minimum interval slightly
    if missed:
        min_interval = params.get("min_onset_interval_ms", 50.0)
        params["min_onset_interval_ms"] = max(20.0, min_interval - 5.0)

    # If false positives exist, increase minimum interval slightly
    if false_pos:
        min_interval = params.get("min_onset_interval_ms", 50.0)
        params["min_onset_interval_ms"] = min(200.0, min_interval + 5.0)

    return params
