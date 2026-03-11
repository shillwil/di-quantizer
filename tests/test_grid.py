"""Tests for grid math module."""

from __future__ import annotations

import numpy as np
import pytest

from di_quantizer.grid import build_grid, snap_to_grid


class TestBuildGrid:
    def test_quarter_notes_120bpm(self):
        """120 BPM, quarter notes: 0.5s interval."""
        grid = build_grid(120.0, "4/4", "4", 4.0)
        expected_interval = 0.5
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, expected_interval, atol=1e-10)

    def test_eighth_notes_120bpm(self):
        """120 BPM, eighth notes: 0.25s interval."""
        grid = build_grid(120.0, "4/4", "8", 2.0)
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, 0.25, atol=1e-10)

    def test_sixteenth_notes_120bpm(self):
        """120 BPM, sixteenth notes: 0.125s interval."""
        grid = build_grid(120.0, "4/4", "16", 2.0)
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, 0.125, atol=1e-10)

    def test_32nd_notes_120bpm(self):
        """120 BPM, 32nd notes: 0.0625s interval."""
        grid = build_grid(120.0, "4/4", "32", 1.0)
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, 0.0625, atol=1e-10)

    def test_eighth_triplets(self):
        """120 BPM, eighth triplets: 3 per beat = 0.5/3 ≈ 0.1667s."""
        grid = build_grid(120.0, "4/4", "8t", 2.0)
        expected = 60.0 / 120.0 / 3.0  # 0.16667
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, expected, atol=1e-10)

    def test_sixteenth_triplets(self):
        """120 BPM, sixteenth triplets: 6 per beat."""
        grid = build_grid(120.0, "4/4", "16t", 1.0)
        expected = 60.0 / 120.0 / 6.0
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, expected, atol=1e-10)

    def test_starts_at_zero(self):
        grid = build_grid(120.0, "4/4", "16", 4.0)
        assert grid[0] == 0.0

    def test_does_not_exceed_duration(self):
        grid = build_grid(120.0, "4/4", "16", 3.0)
        assert grid[-1] <= 3.0 + 1e-9

    def test_different_bpm(self):
        """145 BPM, sixteenth notes."""
        grid = build_grid(145.0, "4/4", "16", 2.0)
        expected = 60.0 / 145.0 / 4.0
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, expected, atol=1e-10)

    def test_seven_eight_time(self):
        """7/8 time signature produces correct grid."""
        grid = build_grid(120.0, "7/8", "8", 4.0)
        # Grid interval is still based on BPM, not time sig
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, 0.25, atol=1e-10)

    def test_five_four_time(self):
        """5/4 time signature produces correct grid."""
        grid = build_grid(120.0, "5/4", "4", 4.0)
        intervals = np.diff(grid)
        np.testing.assert_allclose(intervals, 0.5, atol=1e-10)

    def test_invalid_resolution_raises(self):
        with pytest.raises(ValueError, match="Unsupported grid resolution"):
            build_grid(120.0, "4/4", "3", 4.0)


class TestSnapToGrid:
    def test_full_strength_snaps_exactly(self):
        """strength=1.0 should snap exactly to nearest grid point."""
        grid = build_grid(120.0, "4/4", "8", 4.0)
        onsets = [0.26, 0.51, 0.74]  # slightly off from 0.25, 0.5, 0.75

        results = snap_to_grid(onsets, grid, 1.0, 120.0, "4/4", "8")

        assert abs(results[0]["snapped_sec"] - 0.25) < 1e-6
        assert abs(results[1]["snapped_sec"] - 0.50) < 1e-6
        assert abs(results[2]["snapped_sec"] - 0.75) < 1e-6

    def test_zero_strength_no_movement(self):
        """strength=0.0 should not move onsets at all."""
        grid = build_grid(120.0, "4/4", "8", 4.0)
        onsets = [0.26, 0.51, 0.74]

        results = snap_to_grid(onsets, grid, 0.0, 120.0, "4/4", "8")

        for r, orig in zip(results, onsets):
            assert abs(r["snapped_sec"] - orig) < 1e-6

    def test_half_strength_moves_halfway(self):
        """strength=0.5 should move halfway to grid."""
        grid = build_grid(120.0, "4/4", "8", 4.0)
        onsets = [0.26]  # 10ms off from 0.25

        results = snap_to_grid(onsets, grid, 0.5, 120.0, "4/4", "8")

        # Should be at 0.255 (halfway between 0.26 and 0.25)
        expected = 0.26 + (0.25 - 0.26) * 0.5  # 0.255
        assert abs(results[0]["snapped_sec"] - expected) < 1e-6

    def test_delta_ms_computed_correctly(self):
        grid = build_grid(120.0, "4/4", "8", 4.0)
        onsets = [0.260]  # 10ms off

        results = snap_to_grid(onsets, grid, 1.0, 120.0, "4/4", "8")

        # Delta should be -10ms (moved backward)
        assert abs(results[0]["delta_ms"] - (-10.0)) < 0.1

    def test_returns_grid_labels(self):
        grid = build_grid(120.0, "4/4", "8", 4.0)
        onsets = [0.0, 0.25, 0.5]

        results = snap_to_grid(onsets, grid, 1.0, 120.0, "4/4", "8")

        for r in results:
            assert "nearest_grid_label" in r
            assert isinstance(r["nearest_grid_label"], str)

    def test_empty_grid(self):
        result = snap_to_grid([1.0], np.array([]), 1.0)
        assert result == []

    def test_empty_onsets(self):
        grid = build_grid(120.0, "4/4", "8", 4.0)
        result = snap_to_grid([], grid, 1.0)
        assert result == []
