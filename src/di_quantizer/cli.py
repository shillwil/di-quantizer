"""Click CLI entry point for diq."""

from __future__ import annotations

import os
from pathlib import Path

import click

from di_quantizer import __version__
from di_quantizer.corrections import apply_corrections, load_corrections
from di_quantizer.detector import detect_onsets
from di_quantizer.grid import build_grid, snap_to_grid
from di_quantizer.onset_map import extract_times, load_onset_map, save_onset_map
from di_quantizer.profiles import PROFILES, get_profile
from di_quantizer.reporter import format_summary, generate_report, save_report
from di_quantizer.reviewer import plot_onsets
from di_quantizer.slicer import quantize_audio


@click.group()
@click.version_option(__version__, prog_name="diq")
def cli():
    """DI Guitar Transient Quantizer — snap DI guitar onsets to grid."""


# --- Shared options ---

def detection_options(f):
    """Common detection tuning options."""
    f = click.option("--sensitivity", type=float, default=None,
                     help="Onset detection threshold 0-1. Lower = fewer onsets.")(f)
    f = click.option("--min-interval", type=float, default=None,
                     help="Minimum ms between onsets. Prevents double-triggers.")(f)
    f = click.option("--freq-low", type=int, default=None,
                     help="Lower bound of pre-emphasis band (Hz).")(f)
    f = click.option("--freq-high", type=int, default=None,
                     help="Upper bound of pre-emphasis band (Hz).")(f)
    f = click.option("--pre-emphasis", type=float, default=None,
                     help="Pre-emphasis filter strength 0-1.")(f)
    f = click.option("--onset-method", type=click.Choice(
                     ["spectral_flux", "complex_domain", "high_frequency_content", "energy"]),
                     default=None, help="Detection algorithm.")(f)
    return f


def _resolve_params(profile: str, **overrides) -> dict:
    """Merge profile defaults with CLI overrides."""
    defaults = {
        "sensitivity": 0.5,
        "min_onset_interval_ms": 50.0,
        "freq_low": 2000,
        "freq_high": 5000,
        "pre_emphasis": 0.7,
        "onset_method": "spectral_flux",
    }

    if profile != "custom":
        profile_params = get_profile(profile)
        defaults.update(profile_params)

    # CLI flags override profile and defaults
    mapping = {
        "sensitivity": "sensitivity",
        "min_interval": "min_onset_interval_ms",
        "freq_low": "freq_low",
        "freq_high": "freq_high",
        "pre_emphasis": "pre_emphasis",
        "onset_method": "onset_method",
    }

    for cli_key, param_key in mapping.items():
        val = overrides.get(cli_key)
        if val is not None:
            defaults[param_key] = val

    return defaults


# --- Commands ---

@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--bpm", type=float, required=True, help="Tempo of the session.")
@click.option("--time-sig", default="4/4", help="Time signature (default: 4/4).")
@click.option("--grid", "grid_res", default="16",
              type=click.Choice(["4", "8", "16", "32", "8t", "16t"]),
              help="Grid subdivision (default: 16).")
@click.option("--quantize-strength", type=float, default=1.0,
              help="0.0 = no snap, 1.0 = hard snap (default: 1.0).")
@click.option("--output", "output_path", type=click.Path(), default=None,
              help="Output file path.")
@click.option("--format", "output_format", type=click.Choice(["wav", "aiff"]),
              default="wav", help="Output format (default: wav).")
@click.option("--profile", default="custom",
              type=click.Choice(list(PROFILES.keys())),
              help="Preset profile name.")
@click.option("--corrections", "corrections_path", type=click.Path(exists=True),
              default=None, help="Corrections JSON for re-tuning detection.")
@detection_options
def quantize(input_file, bpm, time_sig, grid_res, quantize_strength,
             output_path, output_format, profile, corrections_path, **det_kwargs):
    """Detect onsets, snap to grid, and render quantized audio.

    Produces a WAV/AIFF ready to drop back into your DAW.
    """
    params = _resolve_params(profile, **det_kwargs)

    # Apply corrections if provided
    if corrections_path:
        corrections = load_corrections(corrections_path)
        params = apply_corrections(params, corrections)

    click.echo(f"Detecting onsets (profile: {profile})...")
    onset_times = detect_onsets(
        input_file,
        sensitivity=params["sensitivity"],
        onset_method=params["onset_method"],
        freq_low=params["freq_low"],
        freq_high=params["freq_high"],
        pre_emphasis=params["pre_emphasis"],
        min_onset_interval_ms=params["min_onset_interval_ms"],
    )

    if not onset_times:
        click.echo("No onsets detected. Try increasing --sensitivity.")
        return

    click.echo(f"Detected {len(onset_times)} onsets.")

    # Build grid and snap
    import soundfile as sf
    info = sf.info(input_file)
    duration = info.duration

    grid = build_grid(bpm, time_sig, grid_res, duration)
    snap_results = snap_to_grid(
        onset_times, grid, quantize_strength, bpm, time_sig, grid_res
    )

    snapped_times = [s["snapped_sec"] for s in snap_results]

    # Render quantized audio
    if not output_path:
        stem = Path(input_file).stem
        ext = "aiff" if output_format == "aiff" else "wav"
        output_path = str(Path(input_file).parent / f"{stem}_quantized.{ext}")

    click.echo(f"Rendering quantized audio...")
    quantize_audio(
        input_file, output_path, onset_times, snapped_times,
        output_format=output_format,
    )

    # Generate and save report
    detection_params_report = {
        "sensitivity": params["sensitivity"],
        "min_interval_ms": params["min_onset_interval_ms"],
        "freq_low": params["freq_low"],
        "freq_high": params["freq_high"],
        "pre_emphasis": params["pre_emphasis"],
        "onset_method": params["onset_method"],
    }

    report = generate_report(
        input_file, bpm, grid_res, quantize_strength, profile,
        detection_params_report, snap_results,
    )

    report_path = str(Path(output_path).with_suffix(".json"))
    save_report(report, report_path)

    click.echo(f"\nOutput: {output_path}")
    click.echo(f"Report: {report_path}")
    click.echo(f"\n{format_summary(report)}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--bpm", type=float, required=True, help="Tempo of the session.")
@click.option("--time-sig", default="4/4", help="Time signature.")
@click.option("--grid", "grid_res", default="16",
              type=click.Choice(["4", "8", "16", "32", "8t", "16t"]),
              help="Grid subdivision.")
@click.option("--profile", default="custom",
              type=click.Choice(list(PROFILES.keys())),
              help="Preset profile name.")
@click.option("--visualize/--no-visualize", default=True,
              help="Generate visualization PNG.")
@click.option("--corrections", "corrections_path", type=click.Path(exists=True),
              default=None, help="Corrections JSON.")
@detection_options
def detect(input_file, bpm, time_sig, grid_res, profile, visualize,
           corrections_path, **det_kwargs):
    """Detect onsets only. Writes onset map JSON + optional visualization.

    No audio output. For previewing/tuning detection settings.
    """
    params = _resolve_params(profile, **det_kwargs)

    if corrections_path:
        corrections = load_corrections(corrections_path)
        params = apply_corrections(params, corrections)

    click.echo(f"Detecting onsets (profile: {profile})...")
    onset_times = detect_onsets(
        input_file,
        sensitivity=params["sensitivity"],
        onset_method=params["onset_method"],
        freq_low=params["freq_low"],
        freq_high=params["freq_high"],
        pre_emphasis=params["pre_emphasis"],
        min_onset_interval_ms=params["min_onset_interval_ms"],
    )

    if not onset_times:
        click.echo("No onsets detected. Try increasing --sensitivity.")
        return

    click.echo(f"Detected {len(onset_times)} onsets.")

    import soundfile as sf
    info = sf.info(input_file)
    duration = info.duration

    grid = build_grid(bpm, time_sig, grid_res, duration)
    snap_results = snap_to_grid(
        onset_times, grid, 1.0, bpm, time_sig, grid_res
    )

    # Save onset map
    stem = Path(input_file).stem
    onset_map_path = str(Path(input_file).parent / f"{stem}_onsets.json")

    metadata = {
        "bpm": bpm,
        "time_signature": time_sig,
        "grid_resolution": grid_res,
        "profile": profile,
        "detection_params": {
            "sensitivity": params["sensitivity"],
            "min_interval_ms": params["min_onset_interval_ms"],
            "freq_low": params["freq_low"],
            "freq_high": params["freq_high"],
            "pre_emphasis": params["pre_emphasis"],
            "onset_method": params["onset_method"],
        },
    }

    save_onset_map(onset_map_path, onset_times, snap_results, metadata)
    click.echo(f"Onset map: {onset_map_path}")

    # Visualization
    if visualize:
        snapped_times = [s["snapped_sec"] for s in snap_results]
        png_path = str(Path(input_file).parent / f"{stem}_onsets.png")
        plot_onsets(
            input_file, onset_times, grid, snapped_times,
            output_path=png_path,
            title=f"{Path(input_file).name} — {len(onset_times)} onsets @ {bpm} BPM",
        )
        click.echo(f"Visualization: {png_path}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--onset-map", "onset_map_path", type=click.Path(exists=True),
              required=True, help="Path to onset map JSON.")
@click.option("--quantize-strength", type=float, default=1.0,
              help="0.0 = no snap, 1.0 = hard snap.")
@click.option("--output", "output_path", type=click.Path(), default=None,
              help="Output file path.")
@click.option("--format", "output_format", type=click.Choice(["wav", "aiff"]),
              default="wav", help="Output format.")
def render(input_file, onset_map_path, quantize_strength, output_path, output_format):
    """Render quantized audio from a previously generated onset map.

    Useful for reusing onset maps across double/quad tracked guitar parts.
    """
    onset_map = load_onset_map(onset_map_path)
    original_times, snapped_times = extract_times(onset_map)

    # Apply quantize strength
    if quantize_strength < 1.0:
        snapped_times = [
            orig + (snap - orig) * quantize_strength
            for orig, snap in zip(original_times, snapped_times)
        ]

    if not output_path:
        stem = Path(input_file).stem
        ext = "aiff" if output_format == "aiff" else "wav"
        output_path = str(Path(input_file).parent / f"{stem}_quantized.{ext}")

    click.echo(f"Rendering from onset map ({len(original_times)} onsets)...")
    quantize_audio(
        input_file, output_path, original_times, snapped_times,
        output_format=output_format,
    )

    click.echo(f"Output: {output_path}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--onset-map", "onset_map_path", type=click.Path(exists=True),
              required=True, help="Path to onset map JSON.")
@click.option("--output", "output_path", type=click.Path(), default=None,
              help="Output PNG path.")
def review(input_file, onset_map_path, output_path):
    """Visualize onset map overlaid on waveform. Quick sanity check."""
    onset_map = load_onset_map(onset_map_path)
    original_times, snapped_times = extract_times(onset_map)

    # Rebuild grid from metadata if available
    grid = None
    meta = onset_map.get("metadata", {})
    if meta.get("bpm"):
        import soundfile as sf
        info = sf.info(input_file)
        grid = build_grid(
            meta["bpm"],
            meta.get("time_signature", "4/4"),
            meta.get("grid_resolution", "16"),
            info.duration,
        )

    if not output_path:
        stem = Path(input_file).stem
        output_path = str(Path(input_file).parent / f"{stem}_review.png")

    plot_onsets(
        input_file, original_times, grid, snapped_times,
        output_path=output_path,
        title=f"{Path(input_file).name} — Onset Review",
    )

    click.echo(f"Review visualization: {output_path}")
