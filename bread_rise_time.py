#!/usr/bin/env python3
"""
bread_rise_time.py

Yeast-dough rise time estimator AND "required yeast" calculator.

Supports:
  - dry yeast (instant or active dry)
  - fresh yeast (compressed/cake), via conversion to dry-equivalent

NOT for sourdough/levain, chemical leaveners, or laminated doughs.

Baseline calibration (user requirement):
  7 g DRY yeast per 500 g flour -> 1 hour at 25°C.

What "rise time" means here
---------------------------
The underlying model estimates BULK fermentation time (first rise).

This script can also report:
  - FINAL proof time (after shaping) as a factor of bulk time
  - TOTAL time = bulk + final

Defaults:
  final_time = bulk_time * 0.60
  total_time = bulk_time + final_time

You can override the factor with --final-factor.

Model (approx):
  time = baseline_time
         * (baseline_ratio / ratio)^(yeast_exponent)
         * q10^((baseline_temp - room_temp)/10)

Where:
  baseline_ratio = baseline_yeast / baseline_flour
  ratio = (dry_equivalent_yeast_g / flour_g)

Inversion (to solve for needed yeast):
  ratio = baseline_ratio * (baseline_time * temp_factor / desired_time)^(1/yeast_exponent)
  yeast_dry_equiv_g = ratio * flour_g

Fresh yeast conversion:
  dry_equiv_g = fresh_g * 0.33     (fresh ≈ 3× dry by weight)
  fresh_g     = dry_equiv_g / 0.33
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RiseEstimate:
    hours: float
    low_hours: float
    high_hours: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class YeastNeeded:
    dry_equiv_g: float
    yeast_g: float
    yeast_type: str
    warnings: tuple[str, ...]


def parse_duration_to_hours(value: str) -> float:
    """
    Parse a duration like:
      "90m", "90min", "1.5h", "1h", "2 hours"
    into hours (float).
    If no unit is given, assumes hours.
    """
    s = value.strip().lower()
    s = s.replace(",", ".")

    if re.fullmatch(r"\d+(\.\d+)?", s):
        h = float(s)
        if h <= 0:
            raise ValueError("time must be > 0")
        return h

    m = re.fullmatch(r"\s*(\d+(\.\d+)?)\s*(m|min|mins|minute|minutes)\s*", s)
    if m:
        minutes = float(m.group(1))
        if minutes <= 0:
            raise ValueError("time must be > 0")
        return minutes / 60.0

    h = re.fullmatch(r"\s*(\d+(\.\d+)?)\s*(h|hr|hrs|hour|hours)\s*", s)
    if h:
        hours = float(h.group(1))
        if hours <= 0:
            raise ValueError("time must be > 0")
        return hours

    raise ValueError(
        "Could not parse --time. Examples: 90m, 1.5h, 2 hours, or just 1.25 (hours)."
    )


def to_dry_equivalent_grams(
    yeast_g: float,
    yeast_type: str,
    *,
    fresh_to_dry_factor: float = 0.33,
) -> float:
    if yeast_g <= 0:
        raise ValueError("yeast must be > 0 (tool is only for yeast dough).")

    yt = yeast_type.strip().lower()
    if yt == "dry":
        return yeast_g
    if yt == "fresh":
        return yeast_g * fresh_to_dry_factor

    raise ValueError("yeast_type must be 'dry' or 'fresh'.")


def from_dry_equivalent_grams(
    dry_equiv_g: float,
    yeast_type: str,
    *,
    fresh_to_dry_factor: float = 0.33,
) -> float:
    if dry_equiv_g <= 0:
        raise ValueError("dry_equiv_g must be > 0")

    yt = yeast_type.strip().lower()
    if yt == "dry":
        return dry_equiv_g
    if yt == "fresh":
        return dry_equiv_g / fresh_to_dry_factor

    raise ValueError("yeast_type must be 'dry' or 'fresh'.")


def estimate_rise_time_hours(
    flour_g: float,
    dry_yeast_equiv_g: float,
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
    Estimate BULK fermentation time in hours (first rise).
    """
    warnings: list[str] = []

    if flour_g <= 0:
        raise ValueError("flour_g must be > 0")
    if dry_yeast_equiv_g <= 0:
        raise ValueError("dry_yeast_equiv_g must be > 0")
    if room_temp_c < -10 or room_temp_c > 50:
        warnings.append("Room temperature looks unusual; results may be unreliable.")

    if room_temp_c < 10:
        warnings.append("Cold environment: yeast activity will be very slow.")
    if room_temp_c > 32:
        warnings.append("Very warm environment: dough may overproof quickly; watch closely.")
    if room_temp_c >= 40:
        warnings.append("Caution: very warm conditions can stress or kill yeast in real dough.")

    baseline_ratio = baseline_yeast_g / baseline_flour_g
    ratio = dry_yeast_equiv_g / flour_g

    yeast_factor = (baseline_ratio / ratio) ** yeast_exponent
    temp_factor = q10 ** ((baseline_temp_c - room_temp_c) / 10.0)

    est_h = baseline_time_h * yeast_factor * temp_factor

    est_h = max(0.15, est_h)   # >= ~9 minutes
    est_h = min(72.0, est_h)   # <= 3 days

    low = est_h * 0.75
    high = est_h * 1.35

    return RiseEstimate(hours=est_h, low_hours=low, high_hours=high, warnings=tuple(warnings))


def required_yeast_for_time(
    flour_g: float,
    desired_time_h: float,
    room_temp_c: float,
    yeast_type: str,
    *,
    fresh_to_dry_factor: float = 0.33,
    baseline_flour_g: float = 500.0,
    baseline_yeast_g: float = 7.0,
    baseline_time_h: float = 1.0,
    baseline_temp_c: float = 25.0,
    yeast_exponent: float = 0.90,
    q10: float = 2.0,
) -> YeastNeeded:
    """
    Compute required yeast for a desired BULK fermentation duration.
    (If you request stage=total or stage=final in the CLI, we convert that to bulk internally.)
    """
    warnings: list[str] = []

    if flour_g <= 0:
        raise ValueError("flour_g must be > 0")
    if desired_time_h <= 0:
        raise ValueError("desired_time_h must be > 0")
    if room_temp_c < -10 or room_temp_c > 50:
        warnings.append("Room temperature looks unusual; results may be unreliable.")

    if room_temp_c < 10:
        warnings.append("Cold environment: required yeast may be high; consider a warmer spot.")
    if room_temp_c > 32:
        warnings.append("Very warm environment: required yeast may be very low; watch closely.")

    baseline_ratio = baseline_yeast_g / baseline_flour_g
    temp_factor = q10 ** ((baseline_temp_c - room_temp_c) / 10.0)

    ratio = baseline_ratio * (baseline_time_h * temp_factor / desired_time_h) ** (1.0 / yeast_exponent)
    dry_equiv_g = ratio * flour_g

    if dry_equiv_g < 0.1:
        warnings.append("Computed yeast is extremely small; measurement error will dominate (use a scale).")
    if dry_equiv_g > 30:
        warnings.append("Computed yeast is very high; dough may taste yeasty and rise too fast/unevenly.")
    if desired_time_h < 0.5:
        warnings.append("Very short rise targets are hard to control; consider increasing temperature instead.")

    yeast_g = from_dry_equivalent_grams(dry_equiv_g, yeast_type, fresh_to_dry_factor=fresh_to_dry_factor)

    return YeastNeeded(
        dry_equiv_g=dry_equiv_g,
        yeast_g=yeast_g,
        yeast_type=yeast_type,
        warnings=tuple(warnings),
    )


def stage_times_from_bulk(bulk_h: float, final_factor: float) -> dict[str, float]:
    """
    Return a dict of stage durations (hours) derived from bulk time.
    final = bulk * final_factor
    total = bulk + final
    """
    final_h = bulk_h * final_factor
    total_h = bulk_h + final_h
    return {"bulk": bulk_h, "final": final_h, "total": total_h}


def bulk_from_stage_time(stage: str, stage_time_h: float, final_factor: float) -> float:
    """
    Convert a user-provided stage time to the equivalent BULK time used by the model.

    If stage == bulk:  bulk = stage_time
    If stage == final: final = bulk*final_factor => bulk = final/final_factor
    If stage == total: total = bulk + bulk*final_factor = bulk*(1+final_factor)
                       => bulk = total/(1+final_factor)
    """
    if stage_time_h <= 0:
        raise ValueError("time must be > 0")
    if final_factor <= 0:
        raise ValueError("final_factor must be > 0")

    st = stage.strip().lower()
    if st == "bulk":
        return stage_time_h
    if st == "final":
        return stage_time_h / final_factor
    if st == "total":
        return stage_time_h / (1.0 + final_factor)

    raise ValueError("stage must be one of: bulk, final, total")


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
Estimate yeast-dough rise time OR calculate required yeast.

You must provide:
  --flour (g), --temp (°C), and EITHER:
    A) --yeast (g) [plus --yeast-type], to estimate the rise time
    B) --time  (desired rise duration), to compute required yeast

The underlying model estimates BULK fermentation (first rise).
You can choose to display/target BULK, FINAL, or TOTAL using --stage.
"""

    epi = """\
EXAMPLES

  Estimate time from yeast, show all stages:
    python bread_rise_time.py --flour 500 --temp 25 --yeast 7 --yeast-type dry --stage all

  Estimate time from yeast, only total time:
    python bread_rise_time.py --flour 500 --temp 25 --yeast 7 --stage total

  Compute required yeast for a TOTAL target time (dry):
    python bread_rise_time.py --flour 500 --temp 22 --time 2h --stage total --yeast-type dry

  Compute required yeast for a FINAL-proof target time (fresh output):
    python bread_rise_time.py --flour 500 --temp 22 --time 60m --stage final --yeast-type fresh

CONTROL FINAL PROOF ASSUMPTION
  By default: final = bulk * 0.60
  Override:   --final-factor 0.75   (final proof 75% of bulk)
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
    p.add_argument("--temp", type=float, required=True, help="Room temperature in °C (e.g., 22).")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--yeast", type=float, help="Yeast amount in grams (see --yeast-type).")
    mode.add_argument("--time", type=str, help="Desired rise time (e.g., 90m, 1.5h, 2 hours).")

    p.add_argument(
        "--yeast-type",
        choices=["dry", "fresh"],
        default="dry",
        help="Yeast type for input/output: dry (instant/active) or fresh (compressed/cake). Default: dry.",
    )
    p.add_argument(
        "--fresh-to-dry-factor",
        type=float,
        default=0.33,
        help="Conversion factor for fresh->dry equivalent. Default 0.33 (fresh ≈ 3× dry).",
    )
    p.add_argument(
        "--stage",
        choices=["bulk", "final", "total", "all"],
        default="bulk",
        help="Which stage time to display/target. Default: bulk. Use 'all' to print bulk+final+total.",
    )
    p.add_argument(
        "--final-factor",
        type=float,
        default=0.60,
        help="Assumed final proof time as a factor of bulk time. Default 0.60 (final = bulk*0.60).",
    )
    p.add_argument(
        "--show-model",
        action="store_true",
        help="Print the underlying calibration/constants used by the estimator.",
    )

    args = p.parse_args()

    model = {
        "baseline_flour_g": 500.0,
        "baseline_yeast_g": 7.0,
        "baseline_time_h": 1.0,
        "baseline_temp_c": 25.0,
        "yeast_exponent": 0.90,
        "q10": 2.0,
        "fresh_to_dry_factor": args.fresh_to_dry_factor,
        "final_factor": args.final_factor,
    }

    if args.yeast is not None:
        dry_equiv = to_dry_equivalent_grams(
            args.yeast, args.yeast_type, fresh_to_dry_factor=args.fresh_to_dry_factor
        )
        bulk_est = estimate_rise_time_hours(args.flour, dry_equiv, args.temp)
        times = stage_times_from_bulk(bulk_est.hours, args.final_factor)

        # Input reporting
        if args.yeast_type == "fresh":
            print(f"Yeast input:        {args.yeast:.2f} g fresh  (~{dry_equiv:.2f} g dry-equivalent)")
        else:
            print(f"Yeast input:        {args.yeast:.2f} g dry")

        # Output by stage selection
        if args.stage == "all":
            print(f"Bulk (first rise):  {_fmt_hours(times['bulk'])}")
            print(f"Final proof:        {_fmt_hours(times['final'])}  (final = bulk*{args.final_factor:.2f})")
            print(f"Total:              {_fmt_hours(times['total'])}")
        else:
            label = {
                "bulk": "Bulk (first rise)",
                "final": "Final proof",
                "total": "Total",
            }[args.stage]
            print(f"{label}: { _fmt_hours(times[args.stage]) }")

        # Range (bulk-based; propagate factor for final/total)
        low_times = stage_times_from_bulk(bulk_est.low_hours, args.final_factor)
        high_times = stage_times_from_bulk(bulk_est.high_hours, args.final_factor)

        if args.stage == "all":
            print("\nLikely ranges:")
            print(f"  Bulk:  {_fmt_hours(low_times['bulk'])} – {_fmt_hours(high_times['bulk'])}")
            print(f"  Final: {_fmt_hours(low_times['final'])} – {_fmt_hours(high_times['final'])}")
            print(f"  Total: {_fmt_hours(low_times['total'])} – {_fmt_hours(high_times['total'])}")
        else:
            print(
                f"Likely range:       {_fmt_hours(low_times[args.stage])} – {_fmt_hours(high_times[args.stage])}"
            )

        if bulk_est.warnings:
            print("\nNotes:")
            for w in bulk_est.warnings:
                print(f" - {w}")

    else:
        stage_time_h = parse_duration_to_hours(args.time)
        # Convert the user's requested stage time to the bulk time the model uses
        bulk_target_h = bulk_from_stage_time(args.stage if args.stage != "all" else "bulk", stage_time_h, args.final_factor)

        needed = required_yeast_for_time(
            flour_g=args.flour,
            desired_time_h=bulk_target_h,
            room_temp_c=args.temp,
            yeast_type=args.yeast_type,
            fresh_to_dry_factor=args.fresh_to_dry_factor,
        )

        # Report what the user asked for and what we targeted internally
        if args.stage == "all":
            # "all" doesn't make sense as a target; treat as bulk
            stage_label = "bulk"
        else:
            stage_label = args.stage

        print(f"Target {stage_label} time:  {_fmt_hours(stage_time_h)}")
        if stage_label != "bulk":
            print(f"(Converted to bulk: {_fmt_hours(bulk_target_h)} using final_factor={args.final_factor:.2f})")

        if args.yeast_type == "fresh":
            print(f"Required yeast:     {needed.yeast_g:.2f} g fresh  (~{needed.dry_equiv_g:.2f} g dry-equivalent)")
        else:
            print(f"Required yeast:     {needed.yeast_g:.2f} g dry")

        if needed.warnings:
            print("\nNotes:")
            for w in needed.warnings:
                print(f" - {w}")

        # Sanity check: compute bulk estimate from computed yeast, then present in requested stage terms
        check_bulk = estimate_rise_time_hours(args.flour, needed.dry_equiv_g, args.temp)
        check_times = stage_times_from_bulk(check_bulk.hours, args.final_factor)
        if args.stage == "all":
            print("\nSanity check (predicted stages):")
            print(f"  Bulk:  {_fmt_hours(check_times['bulk'])}")
            print(f"  Final: {_fmt_hours(check_times['final'])}")
            print(f"  Total: {_fmt_hours(check_times['total'])}")
        else:
            print(f"\nSanity check (predicted): {_fmt_hours(check_times[stage_label])}")

    if args.show_model:
        print("\nModel settings:")
        for k, v in model.items():
            print(f" - {k}: {v}")

    print("\nTip: Use this as a schedule guide—judge readiness by volume/feel, not the clock.")


if __name__ == "__main__":
    main()
