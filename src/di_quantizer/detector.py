"""Onset detection engine for DI guitar signals.

Uses spectral-flux onset detection with configurable high-frequency
pre-emphasis (2-5kHz where pick attack energy lives) to detect onsets
far more accurately than DAW built-in detection for guitar DI signals.
"""

from __future__ import annotations

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt


def detect_onsets(
    audio_path: str,
    sensitivity: float = 0.5,
    onset_method: str = "spectral_flux",
    freq_low: int = 2000,
    freq_high: int = 5000,
    pre_emphasis: float = 0.7,
    min_onset_interval_ms: float = 50.0,
) -> list[float]:
    """Detect onsets in a DI guitar audio file.

    Args:
        audio_path: Path to WAV or AIFF file.
        sensitivity: Detection sensitivity 0-1. Lower = fewer onsets (higher threshold).
        onset_method: Detection algorithm. One of: spectral_flux, complex_domain,
            high_frequency_content, energy.
        freq_low: Lower bound of pre-emphasis band in Hz.
        freq_high: Upper bound of pre-emphasis band in Hz.
        pre_emphasis: Pre-emphasis filter strength 0-1.
        min_onset_interval_ms: Minimum ms between detected onsets.

    Returns:
        List of onset times in seconds.
    """
    y, sr = sf.read(audio_path, dtype="float64")

    # Handle stereo by mixing to mono
    if y.ndim > 1:
        y = np.mean(y, axis=1)

    # Apply pre-emphasis bandpass boost in pick-attack frequency range
    if pre_emphasis > 0 and freq_low < freq_high:
        y_processed = apply_pre_emphasis(y, sr, freq_low, freq_high, pre_emphasis)
    else:
        y_processed = y

    # Compute onset envelope using the chosen method
    onset_env = _compute_onset_envelope(y_processed, sr, onset_method)

    # Map sensitivity (0-1, higher=more sensitive) to delta for peak picking.
    # delta is the threshold for peak picking — lower delta = more peaks detected.
    # sensitivity=1.0 -> delta=0.01 (very sensitive)
    # sensitivity=0.0 -> delta=1.0 (very selective)
    delta = max(0.01, 1.0 - sensitivity)

    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        units="frames",
        delta=delta,
        backtrack=False,
    )

    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # Filter out double-triggers
    onset_times = filter_onsets(onset_times.tolist(), min_onset_interval_ms)

    return onset_times


def apply_pre_emphasis(
    y: np.ndarray,
    sr: int,
    freq_low: int = 2000,
    freq_high: int = 5000,
    strength: float = 0.7,
) -> np.ndarray:
    """Apply bandpass boost in the pick-attack frequency range.

    This is the key to detecting DI guitar onsets — pick attacks concentrate
    energy in the 2-5kHz range. Boosting this band before onset detection
    dramatically improves accuracy vs equal-frequency approaches.

    Uses zero-phase filtering (sosfiltfilt) to avoid phase distortion,
    which is critical since DI guitar gets reamped.

    Args:
        y: Audio signal.
        sr: Sample rate.
        freq_low: Lower cutoff frequency in Hz.
        freq_high: Upper cutoff frequency in Hz.
        strength: Blend strength 0-1. 0=no boost, 1=full boost.

    Returns:
        Audio with pre-emphasis applied.
    """
    nyq = sr / 2.0

    # Clamp frequencies to valid range
    freq_low = max(20, min(freq_low, nyq - 100))
    freq_high = max(freq_low + 100, min(freq_high, nyq - 10))

    sos = butter(4, [freq_low / nyq, freq_high / nyq], btype="band", output="sos")
    y_band = sosfiltfilt(sos, y)

    # Blend: original + boosted band
    return y + strength * y_band


def filter_onsets(onset_times: list[float], min_interval_ms: float) -> list[float]:
    """Remove onsets that are too close together (double triggers).

    Args:
        onset_times: List of onset times in seconds, sorted ascending.
        min_interval_ms: Minimum interval between onsets in milliseconds.

    Returns:
        Filtered list of onset times.
    """
    if not onset_times:
        return []

    min_interval_sec = min_interval_ms / 1000.0
    filtered = [onset_times[0]]

    for t in onset_times[1:]:
        if t - filtered[-1] >= min_interval_sec:
            filtered.append(t)

    return filtered


def _compute_onset_envelope(
    y: np.ndarray, sr: int, method: str
) -> np.ndarray:
    """Compute onset strength envelope using the specified method.

    Args:
        y: Audio signal (with pre-emphasis already applied).
        sr: Sample rate.
        method: One of spectral_flux, complex_domain, high_frequency_content, energy.

    Returns:
        Onset strength envelope.
    """
    if method == "energy":
        # RMS energy-based onset detection
        return librosa.onset.onset_strength(
            y=y, sr=sr, feature=librosa.feature.rms
        )
    elif method == "complex_domain":
        # Use STFT magnitude for complex domain approximation
        S = np.abs(librosa.stft(y))
        return librosa.onset.onset_strength(S=librosa.amplitude_to_db(S), sr=sr)
    elif method == "high_frequency_content":
        # Weight higher frequency bins more heavily
        S = np.abs(librosa.stft(y))
        n_bins = S.shape[0]
        weights = np.linspace(0, 1, n_bins).reshape(-1, 1)
        S_weighted = S * weights
        return librosa.onset.onset_strength(
            S=librosa.amplitude_to_db(S_weighted), sr=sr
        )
    else:
        # Default: spectral_flux using mel spectrogram
        return librosa.onset.onset_strength(y=y, sr=sr)
