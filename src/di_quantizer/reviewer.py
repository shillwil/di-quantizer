"""Waveform + onset visualization for sanity checking detection results."""

from __future__ import annotations

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_onsets(
    audio_path: str,
    onset_times: list[float],
    grid: np.ndarray | None = None,
    snapped_times: list[float] | None = None,
    output_path: str | None = None,
    title: str | None = None,
) -> None:
    """Generate waveform plot with onset markers and grid lines.

    Args:
        audio_path: Path to audio file.
        onset_times: Detected onset times in seconds.
        grid: Optional grid positions array.
        snapped_times: Optional snapped onset times.
        output_path: Path to save PNG. If None, shows plot.
        title: Optional plot title.
    """
    y, sr = sf.read(audio_path, dtype="float64")
    if y.ndim > 1:
        y = np.mean(y, axis=1)

    duration = len(y) / sr
    times = np.linspace(0, duration, len(y))

    fig, ax = plt.subplots(figsize=(16, 4), dpi=150)

    # Waveform
    ax.plot(times, y, color="#444444", linewidth=0.3, alpha=0.7)

    # Grid lines (gray dashed)
    if grid is not None:
        visible_grid = grid[grid <= duration]
        for g in visible_grid:
            ax.axvline(g, color="#CCCCCC", linestyle="--", linewidth=0.5, alpha=0.5)

    # Detected onsets (red)
    for t in onset_times:
        ax.axvline(t, color="#FF3333", linewidth=0.8, alpha=0.8)

    # Snapped positions (green) + delta arrows
    if snapped_times:
        for orig, snap in zip(onset_times, snapped_times):
            ax.axvline(snap, color="#33CC33", linewidth=0.8, alpha=0.6, linestyle=":")
            if abs(snap - orig) > 0.001:
                y_pos = max(abs(y)) * 0.8
                ax.annotate(
                    "",
                    xy=(snap, y_pos),
                    xytext=(orig, y_pos),
                    arrowprops=dict(
                        arrowstyle="->",
                        color="#3366FF",
                        lw=1.0,
                    ),
                )

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.set_title(title or "Onset Detection Review")
    ax.set_xlim(0, duration)

    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color="#FF3333", linewidth=1.5, label="Detected onsets"),
    ]
    if grid is not None:
        legend_elements.append(
            Line2D([0], [0], color="#CCCCCC", linestyle="--", linewidth=1, label="Grid")
        )
    if snapped_times:
        legend_elements.append(
            Line2D([0], [0], color="#33CC33", linestyle=":", linewidth=1.5, label="Snapped")
        )
    ax.legend(handles=legend_elements, loc="upper right", fontsize=8)

    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
    else:
        plt.show()
