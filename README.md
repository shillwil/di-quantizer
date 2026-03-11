# di-quantizer

CLI tool that quantizes DI guitar recordings to grid. Because Flex Time sucks at guitar.

## Why This Exists

Logic Pro X's Flex Time onset detection is tuned for percussive material — drums, percussion, sharp transients. DI guitar signals have soft, rampy attack envelopes, and Flex Time consistently misses onsets, places them late, or triggers on string noise instead of pick attacks.

`di-quantizer` uses spectral-flux onset detection with configurable **high-frequency pre-emphasis** (2-5kHz, where pick attack energy lives) to detect DI guitar onsets far more accurately than Flex Time. It gets your audio **90-95% tight** and hands back a clean WAV/AIFF. You do final touch-ups in your DAW.

## Install

```bash
pipx install di-quantizer
# or
pip install di-quantizer
```

## Quick Start

```bash
# Quantize a DI guitar recording at 145 BPM with the rhythm-tight profile
diq quantize guitar_di.wav --bpm 145 --profile rhythm-tight

# Output: guitar_di_quantized.wav + guitar_di_quantized.json (report)
```

## Workflow

1. **Record** DI guitar in Logic Pro (or any DAW)
2. **Export** the DI track as WAV or AIFF
3. **Run** `diq quantize` on it
4. **Import** the quantized WAV back into your session
5. **Touch up** any remaining timing issues in Logic Pro
6. **Reamp** through your amp sim / real cab as usual

## Profiles

| Profile | Use Case | Key Settings |
|---------|----------|--------------|
| `rhythm-tight` | Palm mutes, chugging, tight rhythm | High pre-emphasis (0.85), sensitivity 0.4, min-interval 60ms |
| `rhythm-loose` | Open chord strumming | Pre-emphasis 0.5, sensitivity 0.6 |
| `lead-fast` | Shred, fast alternate picking | Very low min-interval (30ms), sensitivity 0.6 |
| `lead-legato` | Legato, hammer-ons/pull-offs | Complex domain detection, sensitivity 0.7 |
| `clean` | Clean tone DI | Pre-emphasis 0.4, sensitivity 0.5 |
| `custom` | All manual via CLI flags | No overrides |

```bash
diq quantize guitar_di.wav --bpm 120 --profile rhythm-tight
diq quantize lead_part.wav --bpm 120 --profile lead-fast --grid 16
```

## CLI Reference

### `diq quantize`

Full pipeline: detect onsets, snap to grid, render quantized audio.

```bash
diq quantize <input_file> --bpm <float> [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--bpm` | float | required | Tempo of the session |
| `--time-sig` | string | `4/4` | Time signature |
| `--grid` | string | `16` | Grid subdivision: `4`, `8`, `16`, `32`, `8t`, `16t` |
| `--quantize-strength` | float | `1.0` | 0.0 = no snap, 1.0 = hard snap |
| `--output` | path | `<input>_quantized.wav` | Output file path |
| `--format` | string | `wav` | Output format: `wav` or `aiff` |
| `--profile` | string | `custom` | Preset profile name |
| `--sensitivity` | float | `0.5` | Detection threshold 0-1 |
| `--min-interval` | float | `50` | Min ms between onsets |
| `--freq-low` | int | `2000` | Pre-emphasis band lower bound (Hz) |
| `--freq-high` | int | `5000` | Pre-emphasis band upper bound (Hz) |
| `--pre-emphasis` | float | `0.7` | Pre-emphasis strength 0-1 |
| `--onset-method` | string | `spectral_flux` | Detection algorithm |
| `--corrections` | path | — | Corrections JSON for re-tuning |

### `diq detect`

Detect onsets only. Outputs onset map JSON and optional visualization PNG. No audio output.

```bash
diq detect guitar_di.wav --bpm 120 --profile rhythm-tight
# Output: guitar_di_onsets.json + guitar_di_onsets.png
```

### `diq render`

Render quantized audio from a previously generated onset map. Useful for reusing onset maps across double/quad tracked parts.

```bash
diq render guitar_di_double.wav --onset-map guitar_di_onsets.json
```

### `diq review`

Visualize onset map overlaid on waveform for a quick sanity check.

```bash
diq review guitar_di.wav --onset-map guitar_di_onsets.json
```

## Double/Quad Tracking Workflow

When you have multiple takes of the same part (double or quad tracking), detect onsets on one take and reuse the onset map:

```bash
# 1. Detect and tune on the first take
diq detect take1.wav --bpm 145 --profile rhythm-tight

# 2. Review the detection
diq review take1.wav --onset-map take1_onsets.json

# 3. Quantize all takes using the same onset map
diq render take1.wav --onset-map take1_onsets.json
diq render take2.wav --onset-map take1_onsets.json
diq render take3.wav --onset-map take1_onsets.json
diq render take4.wav --onset-map take1_onsets.json
```

## Correction / Feedback Loop

If detection isn't perfect on the first pass, create a corrections JSON:

```json
{
  "missed_onsets": [
    { "time_sec": 1.482, "note": "palm mute at bar 3" }
  ],
  "false_positives": [
    { "index": 14, "note": "string noise, not a real note" }
  ],
  "threshold_hint": "more_sensitive"
}
```

Then re-run with corrections:

```bash
diq quantize guitar_di.wav --bpm 120 --corrections corrections.json
```

The tool adjusts detection parameters deterministically based on your feedback — no ML, just parameter nudging.

## How It Works

1. **Load** audio at native sample rate via soundfile
2. **Pre-emphasis** — bandpass boost in the 2-5kHz range where pick attack energy concentrates. This is the key differentiator vs. Flex Time's equal-frequency approach
3. **Onset detection** — spectral flux via librosa with configurable sensitivity
4. **Grid math** — generate beat grid from BPM + time signature + subdivision
5. **Snap** — move each onset to nearest grid point, with configurable strength
6. **Slice & shift** — cut audio at onsets, shift to new positions
7. **Crossfade** — raised cosine crossfades at boundaries to prevent clicks
8. **Output** — same duration, sample rate, and bit depth as input

## Development

```bash
git clone https://github.com/shillwil/di-quantizer.git
cd di-quantizer
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT
