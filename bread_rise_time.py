#!/usr/bin/env python3
"""
bread_rise_time.py

Estimate rise time for YEAST dough (commercial yeast: instant or active dry).
Not for sourdough starters/levain, chemical leaveners, or laminated doughs.

Model (approx):
- Baseline: 7g dry yeast per 500g flour -> 1 hour at 25°C.
- Rise time scales ~ inversely with yeast-to-flour ratio (with mild diminishing returns).
- Temperature effect uses Q10 rule-of-thumb: every +10°C doubles activity (time halves).

This is an estimator. Real rise time depends on hydration, sugar/fat, salt,
kneading strength, dough temperature (not just room temp), yeast age, etc.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True)
class RiseEstimate:
    hours: float
    low_hours: float
    high_hours: float
    warnings: tuple[str, ...]


def estimate_rise_time_hours(
    flour_g: float,
    dry_yeast_g: float,
    room_temp_c: float,
    *,
    baseline_flour_g: float = 500.0,
    baseline_yeast_g: float = 7.0,
    baseline_time_h: float = 1.0,
    baseline_temp_c: float = 25.0,
    yeast_exponent: float = 0.90,
    q10: float = 2.0,
) -> RiseEstimate:
    """
    Estimate rise time in hours for yeast dough.

    Parameters
    ----------
    flour_g : float
        Flour mass in grams.
    dry_yeast_g : float
        Dry yeast mass in grams (instant or active dry).
    room_temp_c : float
        Room temperature in °C (used as a proxy for dough temp).
    baseline_* :
        Calibration point. Default matches the user's baseline.
    yeast_exponent :
        <1 adds diminishing returns for large yeast increases (more realistic than linear).
    q10 :
        Activity multiplier per +10°C. q10=2 => doubles each 10°C.

    Returns
    -------
    RiseEstimate : includes central estimate and a practical range.
    """
    warnings: list[str] = []

    # Strict: "yeast dough only" => require yeast > 0
    if flour_g <= 0:
        raise ValueError("flour_g must be > 0")
    if dry_yeast_g <= 0:
        raise ValueError("dry_yeast_g must be > 0 (tool is only for yeast dough).")
    if room_temp_c < -10 or room_temp_c > 50:
        warnings.append("Room temperature looks unusual; results may be unreliable.")

    # Practical notes
    if room_temp_c < 10:
        warnings.append("Cold environment: yeast activity will be very slow.")
    if room_temp_c > 32:
        warnings.append("Very warm environment: dough may overproof quickly; watch closely.")
    if room_temp_c >= 40:
        warnings.append("Caution: very warm conditions can stress or kill yeast in real dough.")

    # Yeast-to-flour ratios
    baseline_ratio = baseline_yeast_g / baseline_flour_g
    ratio = dry_yeast_g / flour_g

    # Yeast scaling: time ∝ (baseline_ratio / ratio)^exponent
    yeast_factor = (baseline_ratio / ratio) ** yeast_exponent

    # Temperature scaling (Q10): time ∝ q10^((baseline_temp - temp)/10)
    temp_factor = q10 ** ((baseline_temp_c - room_temp_c) / 10.0)

    est_h = baseline_time_h * yeast_factor * temp_factor

    # Guardrails
    est_h = max(0.15, est_h)   # >= ~9 minutes
    est_h = min(72.0, est_h)   # <= 3 days

    # Practical uncertainty band
    low = est_h * 0.75
    high = est_h * 1.35

    return RiseEstimate(hours=est_h, low_hours=low, high_hours=high, warnings=tuple(warnings))


def _fmt_hours(h: float) -> str:
    if h < 1:
        mins = int(round(h * 60))
        return f"{mins} min"
    if h < 2:
        return f"{h:.2f} h"
    if h < 10:
        return f"{h:.1f} h"
    return f"{h:.0f} h"


def _build_parser() -> argparse.ArgumentParser:
    desc = """\
Estimate yeast-dough rise time from:
  • flour amount (g)
  • dry yeast amount (g)
  • room temperature (°C)

YEAST DOUGH ONLY:
  This tool is for commercial yeast doughs (instant or active dry).
  It is NOT for sourdough/levain, baking powder/soda, or laminated doughs.

HOW THE ESTIMATE WORKS (high level):
  1) Calibration (your baseline):
       7 g dry yeast per 500 g flour -> 1 hour at 25°C
  2) Yeast scaling (with diminishing returns):
       time ∝ (baseline yeast/flour ÷ your yeast/flour)^(0.90)
  3) Temperature scaling (Q10 rule-of-thumb):
       time ∝ 2^((25 - room_temp)/10)

WHAT YOU GET:
  • a central estimate
  • a "likely range" to reflect real-world variability
"""

    epi = """\
EXAMPLES
  Baseline (should be ~1 hour):
    python bread_rise_time.py --flour 500 --yeast 7 --temp 25

  Less yeast + cooler room:
    python bread_rise_time.py --flour 500 --yeast 3 --temp 21

  Bigger batch, same yeast:
    python bread_rise_time.py --flour 1000 --yeast 7 --temp 24

  Show the model constants:
    python bread_rise_time.py --flour 500 --yeast 7 --temp 25 --show-model

INTERPRETING RESULTS (VERY IMPORTANT)
  Use the estimate to plan your schedule, but judge doneness by the dough:
    • volume increase (often ~1.5x–2x for first rise)
    • feels lighter / gassier, smoother dome
    • finger-dent test (dent springs back slowly)

COMMON REASONS REAL LIFE DIFFERS
  • dough temperature ≠ room temperature (mixing friction, warm/cold water)
  • salt, sugar, fat slow fermentation (sometimes a lot)
  • hydration and flour type change fermentation speed
  • yeast age/brand and how it was stored
  • covered vs uncovered, container shape, drafts

SAFETY / QUALITY NOTES
  • Very warm conditions can overproof fast—check frequently above ~30–32°C.
  • If you want the tool to match YOUR kitchen better, adjust the baseline_temp_c
    in code to the temperature where your "1 hour" baseline is true.

"""

    return argparse.ArgumentParser(
        prog="bread_rise_time.py",
        description=desc,
        epilog=epi,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def main() -> None:
    p = _build_parser()
    p.add_argument("--flour", type=float, required=True, help="Flour in grams (e.g., 500).")
    p.add_argument("--yeast", type=float, required=True, help="Dry yeast in grams (e.g., 7).")
    p.add_argument("--temp", type=float, required=True, help="Room temperature in °C (e.g., 22).")
    p.add_argument(
        "--show-model",
        action="store_true",
        help="Print the underlying calibration/constants used by the estimator.",
    )
    args = p.parse_args()

    # Keep these aligned with estimate_rise_time_hours defaults
    model = {
        "baseline_flour_g": 500.0,
        "baseline_yeast_g": 7.0,
        "baseline_time_h": 1.0,
        "baseline_temp_c": 25.0,
        "yeast_exponent": 0.90,
        "q10": 2.0,
    }

    est = estimate_rise_time_hours(args.flour, args.yeast, args.temp)

    print(f"Estimated rise time: {_fmt_hours(est.hours)}")
    print(f"Likely range:       {_fmt_hours(est.low_hours)} – {_fmt_hours(est.high_hours)}")
    if est.warnings:
        print("\nNotes:")
        for w in est.warnings:
            print(f" - {w}")

    if args.show_model:
        print("\nModel settings:")
        for k, v in model.items():
            print(f" - {k}: {v}")

    print("\nTip: Use this as a schedule guide—judge readiness by volume/feel, not the clock.")


if __name__ == "__main__":
    main()
