"""Preset parameter bundles for common DI guitar playing styles."""

from __future__ import annotations

PROFILES: dict[str, dict] = {
    "rhythm-tight": {
        "description": "Palm mutes, chugging, tight rhythm",
        "sensitivity": 0.4,
        "min_onset_interval_ms": 60.0,
        "freq_low": 2000,
        "freq_high": 5000,
        "pre_emphasis": 0.85,
        "onset_method": "spectral_flux",
    },
    "rhythm-loose": {
        "description": "Open chord strumming",
        "sensitivity": 0.6,
        "min_onset_interval_ms": 50.0,
        "freq_low": 2000,
        "freq_high": 5000,
        "pre_emphasis": 0.5,
        "onset_method": "spectral_flux",
    },
    "lead-fast": {
        "description": "Shred, fast alternate picking",
        "sensitivity": 0.6,
        "min_onset_interval_ms": 30.0,
        "freq_low": 2000,
        "freq_high": 5000,
        "pre_emphasis": 0.7,
        "onset_method": "spectral_flux",
    },
    "lead-legato": {
        "description": "Legato, hammer-ons/pull-offs",
        "sensitivity": 0.7,
        "min_onset_interval_ms": 50.0,
        "freq_low": 1500,
        "freq_high": 5000,
        "pre_emphasis": 0.6,
        "onset_method": "complex_domain",
    },
    "clean": {
        "description": "Clean tone DI",
        "sensitivity": 0.5,
        "min_onset_interval_ms": 50.0,
        "freq_low": 2000,
        "freq_high": 5000,
        "pre_emphasis": 0.4,
        "onset_method": "spectral_flux",
    },
    "custom": {
        "description": "All manual via CLI flags",
    },
}


def get_profile(name: str) -> dict:
    """Get a profile's parameter defaults.

    Args:
        name: Profile name.

    Returns:
        Dict of parameter defaults (excluding 'description').

    Raises:
        ValueError: If profile name is unknown.
    """
    if name not in PROFILES:
        available = ", ".join(PROFILES)
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")

    profile = {k: v for k, v in PROFILES[name].items() if k != "description"}
    return profile


def list_profiles() -> list[dict]:
    """List all available profiles with descriptions.

    Returns:
        List of dicts with 'name' and 'description' keys.
    """
    return [
        {"name": name, "description": info.get("description", "")}
        for name, info in PROFILES.items()
    ]
