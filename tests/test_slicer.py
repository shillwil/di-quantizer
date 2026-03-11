"""Tests for audio slicer module."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from di_quantizer.slicer import (
    _raised_cosine_fade,
    quantize_audio,
    shift_slices,
    slice_at_onsets,
)


class TestSliceAtOnsets:
    def test_basic_slicing(self):
        sr = 44100
        y = np.ones(sr, dtype=np.float64)  # 1 second
        onsets = [0.0, 0.25, 0.5, 0.75]

        slices = slice_at_onsets(y, sr, onsets)

        # First onset is at 0.0, so no pre-onset segment
        assert len(slices) == 4
        total_samples = sum(len(s) for s in slices)
        assert total_samples == len(y)

    def test_preserves_all_samples(self):
        sr = 44100
        y = np.arange(sr, dtype=np.float64)
        onsets = [0.25, 0.5, 0.75]

        slices = slice_at_onsets(y, sr, onsets)

        # Should include pre-onset segment + 3 onset segments
        total_samples = sum(len(s) for s in slices)
        assert total_samples == len(y)

    def test_no_onsets_returns_full_audio(self):
        sr = 44100
        y = np.ones(sr, dtype=np.float64)
        slices = slice_at_onsets(y, sr, [])
        assert len(slices) == 1
        assert len(slices[0]) == len(y)


class TestShiftSlices:
    def test_output_length_matches_input(self):
        """Output must be exactly the same length as input."""
        sr = 44100
        y = np.random.randn(sr * 2).astype(np.float64)
        orig = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75]
        snapped = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75]  # no movement

        result = shift_slices(y, sr, orig, snapped)
        assert len(result) == len(y)

    def test_no_movement_preserves_audio(self):
        """When snapped == original, output should closely match input."""
        sr = 44100
        y = np.random.randn(sr).astype(np.float64)
        orig = [0.25, 0.5, 0.75]
        snapped = orig.copy()

        result = shift_slices(y, sr, orig, snapped)
        assert len(result) == len(y)
        # Most samples should be identical (within skip threshold)
        np.testing.assert_allclose(result, y, atol=1e-10)

    def test_no_nan_or_inf(self):
        """Output must not contain NaN or Inf values."""
        sr = 44100
        y = np.random.randn(sr * 2).astype(np.float64)
        orig = [0.2, 0.5, 0.8, 1.1, 1.4, 1.7]
        snapped = [0.25, 0.5, 0.75, 1.0, 1.5, 1.75]

        result = shift_slices(y, sr, orig, snapped)
        assert not np.any(np.isnan(result))
        assert not np.any(np.isinf(result))

    def test_empty_onsets_returns_copy(self):
        sr = 44100
        y = np.random.randn(sr).astype(np.float64)
        result = shift_slices(y, sr, [], [])
        np.testing.assert_array_equal(result, y)

    def test_skip_threshold(self):
        """Onsets within skip threshold should not be moved."""
        sr = 44100
        y = np.ones(sr, dtype=np.float64)
        # 1ms offset — within default 2ms threshold
        orig = [0.500]
        snapped = [0.501]

        result = shift_slices(y, sr, orig, snapped, skip_threshold_ms=2.0)
        assert len(result) == len(y)


class TestRaisedCosineFade:
    def test_fade_in_starts_zero_ends_one(self):
        fade = _raised_cosine_fade(100, fade_in=True)
        assert abs(fade[0]) < 1e-10
        assert abs(fade[-1] - 1.0) < 1e-10

    def test_fade_out_starts_one_ends_zero(self):
        fade = _raised_cosine_fade(100, fade_in=False)
        assert abs(fade[0] - 1.0) < 1e-10
        assert abs(fade[-1]) < 1e-10

    def test_correct_length(self):
        fade = _raised_cosine_fade(256)
        assert len(fade) == 256

    def test_values_in_range(self):
        fade = _raised_cosine_fade(100)
        assert np.all(fade >= -1e-10)
        assert np.all(fade <= 1.0 + 1e-10)


class TestQuantizeAudio:
    def test_output_same_duration(self, make_test_tone, tmp_dir):
        """Output file must have exact same duration as input."""
        wav_path, onset_times = make_test_tone(bpm=120.0, duration_sec=2.0)

        # Small shifts
        snapped = [t + 0.005 for t in onset_times]
        output_path = str(tmp_dir / "quantized.wav")

        quantize_audio(wav_path, output_path, onset_times, snapped)

        info_in = sf.info(wav_path)
        info_out = sf.info(output_path)

        assert info_out.frames == info_in.frames
        assert info_out.samplerate == info_in.samplerate

    def test_output_no_artifacts(self, make_test_tone, tmp_dir):
        """Output should not have NaN/Inf."""
        wav_path, onset_times = make_test_tone(bpm=120.0, duration_sec=2.0)
        snapped = [t + 0.01 for t in onset_times]
        output_path = str(tmp_dir / "quantized.wav")

        quantize_audio(wav_path, output_path, onset_times, snapped)

        y, _ = sf.read(output_path)
        assert not np.any(np.isnan(y))
        assert not np.any(np.isinf(y))
