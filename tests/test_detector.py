"""Tests for onset detection engine."""

from __future__ import annotations

import numpy as np
import pytest

from di_quantizer.detector import apply_pre_emphasis, detect_onsets, filter_onsets


class TestFilterOnsets:
    def test_empty_list(self):
        assert filter_onsets([], 50.0) == []

    def test_single_onset(self):
        assert filter_onsets([1.0], 50.0) == [1.0]

    def test_removes_double_triggers(self):
        # 20ms apart, min interval 50ms — second should be removed
        result = filter_onsets([1.0, 1.02, 1.5], 50.0)
        assert result == [1.0, 1.5]

    def test_keeps_well_spaced_onsets(self):
        onsets = [0.0, 0.5, 1.0, 1.5]
        result = filter_onsets(onsets, 50.0)
        assert result == onsets

    def test_respects_min_interval(self):
        # All 30ms apart, min interval 25ms — should keep all
        onsets = [0.0, 0.030, 0.060, 0.090]
        result = filter_onsets(onsets, 25.0)
        assert len(result) == 4


class TestApplyPreEmphasis:
    def test_output_same_length(self):
        sr = 44100
        y = np.random.randn(sr)  # 1 second
        result = apply_pre_emphasis(y, sr, 2000, 5000, 0.7)
        assert len(result) == len(y)

    def test_zero_strength_returns_original(self):
        sr = 44100
        y = np.random.randn(sr)
        result = apply_pre_emphasis(y, sr, 2000, 5000, 0.0)
        np.testing.assert_array_equal(result, y)

    def test_boosts_target_frequencies(self):
        sr = 44100
        duration = 1.0
        t = np.arange(int(sr * duration)) / sr

        # 3kHz sine (in the pre-emphasis band)
        y = np.sin(2 * np.pi * 3000 * t)
        result = apply_pre_emphasis(y, sr, 2000, 5000, 0.7)

        # Energy should be higher after pre-emphasis
        assert np.sum(result ** 2) > np.sum(y ** 2)


class TestDetectOnsets:
    def test_detects_sharp_attacks(self, make_test_tone):
        """Detect onsets on a test tone with sharp attacks at known positions."""
        wav_path, expected_times = make_test_tone(
            bpm=120.0, duration_sec=4.0, grid_resolution="4",
            soft_attack=False,
        )

        detected = detect_onsets(
            wav_path, sensitivity=0.6, pre_emphasis=0.5,
            min_onset_interval_ms=200.0,
        )

        # Should detect most onsets (at least 70%)
        assert len(detected) >= len(expected_times) * 0.7

        # Each detected onset should be within 50ms of an expected position
        for d in detected:
            min_dist = min(abs(d - e) for e in expected_times)
            assert min_dist < 0.05, f"Detected onset at {d}s not near any expected position"

    def test_detects_soft_attacks(self, make_test_tone):
        """Detect onsets with soft/rampy attacks (DI guitar simulation)."""
        wav_path, expected_times = make_test_tone(
            bpm=120.0, duration_sec=4.0, grid_resolution="4",
            soft_attack=True, attack_ms=20.0,
        )

        detected = detect_onsets(
            wav_path, sensitivity=0.6, pre_emphasis=0.7,
            min_onset_interval_ms=200.0,
        )

        # Should still detect most onsets even with soft attacks
        assert len(detected) >= len(expected_times) * 0.5

    def test_respects_min_interval(self, make_test_tone):
        """No double triggers within min_onset_interval."""
        wav_path, _ = make_test_tone(
            bpm=120.0, duration_sec=4.0, grid_resolution="8",
        )

        detected = detect_onsets(
            wav_path, sensitivity=0.8, min_onset_interval_ms=200.0,
        )

        for i in range(1, len(detected)):
            interval_ms = (detected[i] - detected[i - 1]) * 1000
            assert interval_ms >= 200.0 - 1.0  # 1ms tolerance

    def test_different_methods_produce_results(self, make_test_tone):
        """Smoke test: each onset method produces some results."""
        wav_path, _ = make_test_tone(bpm=120.0, duration_sec=2.0)

        for method in ["spectral_flux", "energy", "complex_domain", "high_frequency_content"]:
            detected = detect_onsets(
                wav_path, sensitivity=0.7, onset_method=method,
            )
            # Should detect at least something
            assert len(detected) > 0, f"Method {method} detected nothing"

    def test_pre_emphasis_improves_soft_attack_detection(self, make_test_tone):
        """Pre-emphasis should help detect soft transients."""
        wav_path, expected_times = make_test_tone(
            bpm=120.0, duration_sec=4.0, grid_resolution="4",
            soft_attack=True, attack_ms=30.0, frequency=3000.0,
        )

        # Without pre-emphasis
        detected_no_emph = detect_onsets(
            wav_path, sensitivity=0.5, pre_emphasis=0.0,
            min_onset_interval_ms=200.0,
        )

        # With pre-emphasis
        detected_with_emph = detect_onsets(
            wav_path, sensitivity=0.5, pre_emphasis=0.8,
            min_onset_interval_ms=200.0,
        )

        # Pre-emphasis should detect at least as many (usually more)
        assert len(detected_with_emph) >= len(detected_no_emph)
