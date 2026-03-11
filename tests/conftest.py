"""Shared test fixtures — programmatic test tone generation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def make_test_tone(tmp_dir):
    """Factory fixture that generates WAV files with sine bursts at known positions.

    Returns a function that creates test audio files with configurable parameters.
    """
    def _make(
        bpm: float = 120.0,
        duration_sec: float = 4.0,
        sr: int = 44100,
        frequency: float = 440.0,
        burst_duration_ms: float = 80.0,
        grid_resolution: str = "8",
        offset_ms: float = 0.0,
        soft_attack: bool = False,
        attack_ms: float = 20.0,
    ) -> tuple[str, list[float]]:
        """Generate a WAV file with sine wave bursts at grid positions.

        Args:
            bpm: Tempo.
            duration_sec: Total duration in seconds.
            sr: Sample rate.
            frequency: Sine wave frequency for bursts.
            burst_duration_ms: Duration of each burst in ms.
            grid_resolution: Grid subdivision for burst placement.
            offset_ms: Offset each burst by this many ms (simulates timing drift).
            soft_attack: If True, apply ramp-up envelope to simulate DI guitar.
            attack_ms: Attack ramp duration when soft_attack=True.

        Returns:
            Tuple of (wav_path, expected_onset_times).
        """
        from di_quantizer.grid import _RESOLUTION_MAP

        n_samples = int(duration_sec * sr)
        y = np.zeros(n_samples, dtype=np.float64)

        # Calculate grid interval
        subdivisions = _RESOLUTION_MAP.get(grid_resolution, 2.0)
        beat_dur = 60.0 / bpm
        grid_interval = beat_dur / subdivisions

        burst_samples = int(burst_duration_ms / 1000.0 * sr)
        offset_samples = int(offset_ms / 1000.0 * sr)
        attack_samples = int(attack_ms / 1000.0 * sr)

        onset_times = []
        t = 0.0
        while t < duration_sec - 0.1:
            onset_sample = int(round(t * sr)) + offset_samples
            if onset_sample < 0 or onset_sample >= n_samples:
                t += grid_interval
                continue

            onset_times.append((onset_sample + 0.0) / sr)

            end_sample = min(onset_sample + burst_samples, n_samples)
            n_burst = end_sample - onset_sample

            # Generate sine burst
            burst_t = np.arange(n_burst) / sr
            burst = 0.5 * np.sin(2 * np.pi * frequency * burst_t)

            # Apply envelope
            if soft_attack and attack_samples > 0:
                # Ramp-up attack to simulate DI guitar
                ramp_len = min(attack_samples, n_burst)
                ramp = np.linspace(0, 1, ramp_len)
                burst[:ramp_len] *= ramp
            else:
                # Sharp attack — just a quick fade-in to avoid click
                fade_len = min(10, n_burst)
                burst[:fade_len] *= np.linspace(0, 1, fade_len)

            # Decay envelope
            decay_len = n_burst
            decay = np.exp(-3.0 * np.arange(decay_len) / decay_len)
            burst *= decay

            y[onset_sample:end_sample] += burst

            t += grid_interval

        # Normalize
        peak = np.max(np.abs(y))
        if peak > 0:
            y = y / peak * 0.8

        wav_path = str(tmp_dir / "test_tone.wav")
        sf.write(wav_path, y, sr, subtype="FLOAT")

        return wav_path, onset_times

    return _make
