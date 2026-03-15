"""Compare auto-quantized onsets against a human-edited reference.

Given the original DI recording and a human-edited version, this module
detects onsets in both, pairs them up, and reports where the auto-quantizer
agrees or disagrees with the human engineer's edits.
"""

from __future__ import annotations

import numpy as np
import soundfile as sf

from di_quantizer.detector import detect_onsets
from di_quantizer.grid import build_grid, snap_to_grid


def detect_human_edits(
    original_path: str,
    edited_path: str,
    detection_params: dict,
    bpm: float,
    time_sig: str,
    grid_res: str,
    match_tolerance_ms: float = 30.0,
) -> dict:
    """Detect onsets in both files and pair them to find human edits.

    Args:
        original_path: Path to original (unedited) DI recording.
        edited_path: Path to the human-edited/quantized version.
        detection_params: Dict with sensitivity, onset_method, etc.
        bpm: Tempo in BPM.
        time_sig: Time signature string.
        grid_res: Grid resolution string.
        match_tolerance_ms: Max ms distance to consider two onsets "the same note".

    Returns:
        Dict with paired onsets, stats, and diff details.
    """
    # Detect onsets in both files
    orig_onsets = detect_onsets(original_path, **detection_params)
    human_onsets = detect_onsets(edited_path, **detection_params)

    # Build grid and auto-snap the original
    info = sf.info(original_path)
    grid = build_grid(bpm, time_sig, grid_res, info.duration)
    auto_snap_results = snap_to_grid(orig_onsets, grid, 1.0, bpm, time_sig, grid_res)

    # Pair original onsets with human-edited onsets
    pairs = _pair_onsets(orig_onsets, human_onsets, match_tolerance_ms / 1000.0)

    # Build comparison for each paired onset
    comparisons = []
    for i, (orig_idx, human_idx) in enumerate(pairs):
        orig_sec = orig_onsets[orig_idx] if orig_idx is not None else None
        human_sec = human_onsets[human_idx] if human_idx is not None else None

        auto_snap = auto_snap_results[orig_idx] if orig_idx is not None else None

        entry = _build_comparison_entry(
            orig_sec, human_sec, auto_snap, grid, bpm, time_sig, grid_res
        )
        comparisons.append(entry)

    # Compute summary stats
    summary = _compute_summary(comparisons)

    return {
        "original_file": original_path,
        "edited_file": edited_path,
        "bpm": bpm,
        "time_signature": time_sig,
        "grid_resolution": grid_res,
        "detection_params": detection_params,
        "total_original_onsets": len(orig_onsets),
        "total_human_onsets": len(human_onsets),
        "comparisons": comparisons,
        "summary": summary,
    }


def _pair_onsets(
    orig_onsets: list[float],
    human_onsets: list[float],
    tolerance_sec: float,
) -> list[tuple[int | None, int | None]]:
    """Pair original onsets with their corresponding human-edited onsets.

    Uses nearest-neighbor matching within tolerance. Unmatched onsets
    from either side are included as unpaired entries.

    Returns list of (orig_index, human_index) tuples. One side can be None.
    """
    if not orig_onsets and not human_onsets:
        return []

    orig = np.array(orig_onsets)
    human = np.array(human_onsets)
    pairs = []
    used_human = set()

    # For each original onset, find the closest human onset
    for oi, ot in enumerate(orig):
        if len(human) == 0:
            pairs.append((oi, None))
            continue

        dists = np.abs(human - ot)
        best_hi = int(np.argmin(dists))

        if dists[best_hi] <= tolerance_sec and best_hi not in used_human:
            pairs.append((oi, best_hi))
            used_human.add(best_hi)
        else:
            pairs.append((oi, None))

    # Any human onsets not matched = notes the human added or the detector missed
    for hi in range(len(human)):
        if hi not in used_human:
            pairs.append((None, hi))

    return pairs


def _build_comparison_entry(
    orig_sec: float | None,
    human_sec: float | None,
    auto_snap: dict | None,
    grid: np.ndarray,
    bpm: float,
    time_sig: str,
    grid_res: str,
) -> dict:
    """Build a single comparison entry for one onset pair."""
    entry = {}

    if orig_sec is not None and human_sec is not None:
        # Paired onset — compare human edit vs auto snap
        human_delta_ms = (human_sec - orig_sec) * 1000.0
        auto_snapped_sec = auto_snap["snapped_sec"] if auto_snap else orig_sec
        auto_delta_ms = (auto_snapped_sec - orig_sec) * 1000.0
        disagreement_ms = (human_sec - auto_snapped_sec) * 1000.0

        # Find which grid position the human snapped to
        human_grid_idx = int(np.argmin(np.abs(grid - human_sec)))
        human_grid_sec = grid[human_grid_idx]
        human_grid_dist_ms = (human_sec - human_grid_sec) * 1000.0

        # Did the human snap to the same grid line as the auto?
        auto_grid_label = auto_snap["nearest_grid_label"] if auto_snap else "?"

        entry = {
            "type": "paired",
            "original_sec": round(orig_sec, 6),
            "human_sec": round(human_sec, 6),
            "auto_sec": round(auto_snapped_sec, 6),
            "human_delta_ms": round(human_delta_ms, 2),
            "auto_delta_ms": round(auto_delta_ms, 2),
            "disagreement_ms": round(disagreement_ms, 2),
            "auto_grid_label": auto_grid_label,
            "human_on_grid": bool(abs(human_grid_dist_ms) < 2.0),
            "same_direction": bool(
                (human_delta_ms >= 0) == (auto_delta_ms >= 0)
                if abs(human_delta_ms) > 0.5 and abs(auto_delta_ms) > 0.5
                else True
            ),
        }

    elif orig_sec is not None and human_sec is None:
        # Original onset with no matching human onset — human may have deleted it
        # or it's a false positive
        entry = {
            "type": "auto_only",
            "original_sec": round(orig_sec, 6),
            "auto_sec": round(auto_snap["snapped_sec"], 6) if auto_snap else None,
            "auto_grid_label": auto_snap["nearest_grid_label"] if auto_snap else "?",
            "note": "Onset in original not found in human edit (deleted or merged?)",
        }

    elif human_sec is not None and orig_sec is None:
        # Human onset with no matching original — human added a split point?
        entry = {
            "type": "human_only",
            "human_sec": round(human_sec, 6),
            "note": "Onset in human edit not found in original (added by engineer?)",
        }

    return entry


def _compute_summary(comparisons: list[dict]) -> dict:
    """Compute aggregate stats from all comparison entries."""
    paired = [c for c in comparisons if c.get("type") == "paired"]
    auto_only = [c for c in comparisons if c.get("type") == "auto_only"]
    human_only = [c for c in comparisons if c.get("type") == "human_only"]

    if not paired:
        return {
            "paired_onsets": 0,
            "auto_only_onsets": len(auto_only),
            "human_only_onsets": len(human_only),
        }

    disagreements = [abs(c["disagreement_ms"]) for c in paired]
    human_deltas = [abs(c["human_delta_ms"]) for c in paired]
    auto_deltas = [abs(c["auto_delta_ms"]) for c in paired]

    # How many onsets did the human not move (left in place)?
    human_untouched = sum(1 for d in human_deltas if d < 1.0)

    # How many did auto and human agree on (within 2ms)?
    close_agreement = sum(1 for d in disagreements if d < 2.0)
    moderate_agreement = sum(1 for d in disagreements if d < 5.0)

    # Direction agreement
    same_direction = sum(1 for c in paired if c.get("same_direction", True))

    return {
        "paired_onsets": len(paired),
        "auto_only_onsets": len(auto_only),
        "human_only_onsets": len(human_only),
        "human_untouched": human_untouched,
        "agreement_within_2ms": close_agreement,
        "agreement_within_5ms": moderate_agreement,
        "agreement_pct": round(close_agreement / len(paired) * 100, 1),
        "avg_disagreement_ms": round(float(np.mean(disagreements)), 2),
        "max_disagreement_ms": round(float(np.max(disagreements)), 2),
        "avg_human_drift_ms": round(float(np.mean(human_deltas)), 2),
        "avg_auto_drift_ms": round(float(np.mean(auto_deltas)), 2),
        "same_direction_pct": round(same_direction / len(paired) * 100, 1),
    }


def format_compare_summary(result: dict) -> str:
    """Format comparison results as a human-readable summary."""
    s = result["summary"]
    lines = []

    lines.append(f"  Onsets in original:   {result['total_original_onsets']}")
    lines.append(f"  Onsets in human edit:  {result['total_human_onsets']}")
    lines.append(f"  Paired (matched):     {s['paired_onsets']}")

    if s.get("auto_only_onsets"):
        lines.append(f"  Auto-only (no human):  {s['auto_only_onsets']}")
    if s.get("human_only_onsets"):
        lines.append(f"  Human-only (added):    {s['human_only_onsets']}")

    if s["paired_onsets"] > 0:
        lines.append("")
        lines.append(f"  Agreement (within 2ms): {s['agreement_within_2ms']}/{s['paired_onsets']} ({s['agreement_pct']}%)")
        lines.append(f"  Agreement (within 5ms): {s['agreement_within_5ms']}/{s['paired_onsets']}")
        lines.append(f"  Same snap direction:    {s['same_direction_pct']}%")
        lines.append(f"  Avg disagreement:       {s['avg_disagreement_ms']} ms")
        lines.append(f"  Max disagreement:       {s['max_disagreement_ms']} ms")
        lines.append(f"  Human left untouched:   {s.get('human_untouched', 0)}")
        lines.append(f"  Avg human drift:        {s['avg_human_drift_ms']} ms")
        lines.append(f"  Avg auto drift:         {s['avg_auto_drift_ms']} ms")

    return "\n".join(lines)


def plot_comparison(
    original_path: str,
    result: dict,
    output_path: str,
) -> None:
    """Generate a side-by-side visualization comparing human vs auto edits.

    Shows waveform with color-coded markers:
    - Red: original onset positions
    - Green: where the human moved them
    - Blue: where auto-quantizer would move them
    - Orange highlights: disagreements > 5ms
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    y, sr = sf.read(original_path, dtype="float64")
    if y.ndim > 1:
        y = np.mean(y, axis=1)

    duration = len(y) / sr
    times = np.linspace(0, duration, len(y))

    fig, ax = plt.subplots(figsize=(16, 5), dpi=150)

    # Waveform
    ax.plot(times, y, color="#444444", linewidth=0.3, alpha=0.5)

    peak = max(abs(y)) if len(y) > 0 else 1.0

    for comp in result["comparisons"]:
        if comp["type"] == "paired":
            orig = comp["original_sec"]
            human = comp["human_sec"]
            auto = comp["auto_sec"]
            disagree = abs(comp["disagreement_ms"])

            # Original position (thin gray)
            ax.axvline(orig, color="#999999", linewidth=0.5, alpha=0.4)

            # Human edit (green)
            ax.axvline(human, color="#33CC33", linewidth=1.0, alpha=0.7)

            # Auto snap (blue)
            ax.axvline(auto, color="#3366FF", linewidth=1.0, alpha=0.7, linestyle=":")

            # Highlight disagreements
            if disagree > 5.0:
                ax.axvspan(
                    min(human, auto), max(human, auto),
                    alpha=0.15, color="#FF6600",
                )

        elif comp["type"] == "auto_only":
            ax.axvline(comp["original_sec"], color="#FF3333", linewidth=0.8, alpha=0.6)

        elif comp["type"] == "human_only":
            ax.axvline(comp["human_sec"], color="#33CC33", linewidth=1.2,
                       alpha=0.8, linestyle="--")

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_xlim(0, duration)

    s = result["summary"]
    title = (
        f"Human vs Auto — {s['paired_onsets']} paired, "
        f"{s.get('agreement_pct', 0)}% agree (within 2ms), "
        f"avg disagreement {s.get('avg_disagreement_ms', 0)} ms"
    )
    ax.set_title(title, fontsize=10)

    legend_elements = [
        Line2D([0], [0], color="#33CC33", linewidth=1.5, label="Human edit"),
        Line2D([0], [0], color="#3366FF", linewidth=1.5, linestyle=":", label="Auto quantize"),
        Line2D([0], [0], color="#999999", linewidth=1, label="Original position"),
    ]
    if any(c["type"] == "auto_only" for c in result["comparisons"]):
        legend_elements.append(
            Line2D([0], [0], color="#FF3333", linewidth=1, label="Auto-only (not in human)")
        )
    ax.legend(handles=legend_elements, loc="upper right", fontsize=8)

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
