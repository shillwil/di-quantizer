"""JSON transient report generation."""

from __future__ import annotations

import json
from pathlib import Path


def generate_report(
    source_file: str,
    bpm: float,
    grid_resolution: str,
    quantize_strength: float,
    profile: str,
    detection_params: dict,
    snap_results: list[dict],
    onset_confidences: list[float] | None = None,
) -> dict:
    """Generate a structured transient report.

    Args:
        source_file: Path to the source audio file.
        bpm: Tempo in BPM.
        grid_resolution: Grid resolution string.
        quantize_strength: Quantize strength 0-1.
        profile: Profile name used.
        detection_params: Dict of detection parameters.
        snap_results: List of snap result dicts from grid.snap_to_grid().
        onset_confidences: Optional list of confidence values per onset.

    Returns:
        Report dict.
    """
    onsets = []
    deltas = []

    for i, snap in enumerate(snap_results):
        onset_entry = {
            "index": i,
            "original_sec": snap["original_sec"],
            "snapped_sec": snap["snapped_sec"],
            "delta_ms": snap["delta_ms"],
            "nearest_grid_label": snap["nearest_grid_label"],
        }
        if onset_confidences and i < len(onset_confidences):
            onset_entry["confidence"] = round(onset_confidences[i], 3)
        onsets.append(onset_entry)
        deltas.append(abs(snap["delta_ms"]))

    report = {
        "source_file": str(Path(source_file).name),
        "bpm": bpm,
        "grid_resolution": grid_resolution,
        "quantize_strength": quantize_strength,
        "profile": profile,
        "detection_params": detection_params,
        "onsets": onsets,
        "summary": {
            "total_onsets_detected": len(onsets),
            "average_drift_ms": round(sum(deltas) / len(deltas), 1) if deltas else 0.0,
            "max_drift_ms": round(max(deltas), 1) if deltas else 0.0,
        },
    }

    return report


def save_report(report: dict, output_path: str) -> None:
    """Save report to JSON file.

    Args:
        report: Report dict from generate_report().
        output_path: Path to write JSON file.
    """
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)


def format_summary(report: dict) -> str:
    """Format report summary for CLI output.

    Args:
        report: Report dict.

    Returns:
        Human-readable summary string.
    """
    s = report["summary"]
    lines = [
        f"Onsets detected: {s['total_onsets_detected']}",
        f"Average drift:   {s['average_drift_ms']:.1f} ms",
        f"Max drift:       {s['max_drift_ms']:.1f} ms",
    ]
    return "\n".join(lines)
