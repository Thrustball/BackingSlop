#!/usr/bin/env python3
"""
Mixed-flour yeast dough water calculator (hydration-based).

Hydration = water / flour * 100
Outputs water in grams and milliliters (for water: 1 g ≈ 1 ml).

Two input modes:
  1) Grams mode: repeat --item flour:GRAMS[:HYDRATION]
  2) Percent mode: provide --total-flour-g and repeat --item flour:PERCENT%[:HYDRATION]

Examples:
  python water_calc_mix.py --item wheat_550:350 --item spelt_1050:150 --firmness standard
  python water_calc_mix.py --item wheat_whole:400:84 --item spelt_630:100
  python water_calc_mix.py --total-flour-g 800 --item wheat_1050:70% --item spelt_whole:30% --firmness soft
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class HydrationProfile:
    min_pct: float
    default_pct: float
    max_pct: float
    note: str = ""


FLOUR_PROFILES: Dict[str, HydrationProfile] = {
    # Wheat
    "wheat_550":   HydrationProfile(65.0, 70.0, 70.0, "Reference flour for many standard breads."),
    "wheat_1050":  HydrationProfile(75.0, 76.0, 77.0, "Higher extraction typically needs more water than 550."),
    "wheat_whole": HydrationProfile(80.0, 83.0, 85.0, "Whole grain binds more water; soaking helps."),

    # Spelt
    "spelt_630":   HydrationProfile(67.0, 68.0, 68.0, "Often a touch less water than wheat 550."),
    "spelt_1050":  HydrationProfile(72.0, 73.0, 75.0, "Derived guideline: spelt often needs a bit less than comparable wheat."),
    "spelt_whole": HydrationProfile(75.0, 76.5, 78.0, "Whole spelt: higher hydration; handle gently."),
}

ALIASES: Dict[str, str] = {
    # Wheat aliases
    "weizen550": "wheat_550", "weizen_550": "wheat_550", "w550": "wheat_550", "wheat550": "wheat_550",
    "weizen1050": "wheat_1050", "weizen_1050": "wheat_1050", "w1050": "wheat_1050", "wheat1050": "wheat_1050",
    "weizenvollkorn": "wheat_whole", "weizen_vollkorn": "wheat_whole", "wvk": "wheat_whole",

    # Spelt aliases
    "dinkel630": "spelt_630", "dinkel_630": "spelt_630", "d630": "spelt_630",
    "dinkel1050": "spelt_1050", "dinkel_1050": "spelt_1050", "d1050": "spelt_1050",
    "dinkelvollkorn": "spelt_whole", "dinkel_vollkorn": "spelt_whole", "dvk": "spelt_whole",
}


def normalize_flour_key(flour: str) -> str:
    key = flour.strip().lower().replace(" ", "")
    return ALIASES.get(key, key)


def choose_hydration(profile: HydrationProfile, firmness: str) -> float:
    f = firmness.strip().lower()
    if f in ("tight", "firm", "stiff"):
        return profile.min_pct
    if f in ("soft", "wet"):
        return profile.max_pct
    if f in ("standard", "default", "normal"):
        return profile.default_pct
    raise ValueError("firmness must be one of: tight | standard | soft")


@dataclass
class MixItem:
    flour_key: str
    flour_g: float
    hydration_pct: float

    @property
    def water_g(self) -> float:
        return self.flour_g * (self.hydration_pct / 100.0)

    @property
    def water_ml(self) -> float:
        return self.water_g  # 1 g water ≈ 1 ml


def parse_item(raw: str, total_flour_g: Optional[float]) -> Tuple[str, float, Optional[float], bool]:
    """
    Parses:
      flour:GRAMS
      flour:GRAMS:HYDRATION
      flour:PERCENT%
      flour:PERCENT%:HYDRATION
    Returns (flour_key, amount, hydration_override, is_percent)
    """
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(
            f"Invalid --item '{raw}'. Use flour:grams[:hydration] or flour:percent%[:hydration]."
        )

    flour_key = normalize_flour_key(parts[0])
    amount_str = parts[1].strip()
    hydration_override = float(parts[2]) if len(parts) == 3 else None

    is_percent = amount_str.endswith("%")
    if is_percent:
        if total_flour_g is None:
            raise ValueError(f"--item '{raw}' uses %, but --total-flour-g is missing.")
        pct = float(amount_str[:-1])
        if pct <= 0:
            raise ValueError(f"Percent must be > 0 in '{raw}'.")
        amount = pct
    else:
        grams = float(amount_str)
        if grams <= 0:
            raise ValueError(f"Grams must be > 0 in '{raw}'.")
        amount = grams

    return flour_key, amount, hydration_override, is_percent


def build_mix(items_raw: List[str], firmness: str, total_flour_g: Optional[float]) -> List[MixItem]:
    parsed: List[Tuple[str, float, Optional[float], bool]] = []
    for raw in items_raw:
        flour_key, amount, hyd_override, is_percent = parse_item(raw, total_flour_g)
        if flour_key not in FLOUR_PROFILES:
            valid = ", ".join(sorted(FLOUR_PROFILES.keys()))
            raise ValueError(f"Unknown flour '{flour_key}' from '{raw}'. Valid: {valid}")
        parsed.append((flour_key, amount, hyd_override, is_percent))

    # If any percent items are present, all items should be percent-based and sum to 100%.
    if any(is_percent for *_, is_percent in parsed):
        assert total_flour_g is not None
        if not all(is_percent for *_, is_percent in parsed):
            raise ValueError("If you use % for one item, all --item entries must use %.")
        pct_sum = sum(amount for _, amount, _, _ in parsed)
        if abs(pct_sum - 100.0) > 1e-6:
            raise ValueError(f"Percent items must sum to 100%, but sum to {pct_sum:.2f}%.")

    mix: List[MixItem] = []
    for flour_key, amount, hyd_override, is_percent in parsed:
        flour_g = (total_flour_g * (amount / 100.0)) if is_percent else amount
        profile = FLOUR_PROFILES[flour_key]
        hyd = hyd_override if hyd_override is not None else choose_hydration(profile, firmness)
        mix.append(MixItem(flour_key=flour_key, flour_g=flour_g, hydration_pct=hyd))

    return mix


def summarize(mix: List[MixItem]) -> str:
    total_flour = sum(i.flour_g for i in mix)
    total_water = sum(i.water_g for i in mix)
    weighted_hyd = (total_water / total_flour * 100.0) if total_flour > 0 else 0.0
    ta = weighted_hyd + 100.0

    lines = []
    lines.append("Mix breakdown (water shown as g and ~ml):")
    lines.append("-" * 76)
    lines.append(f"{'Flour':<14} {'Flour g':>10} {'Hyd %':>8} {'Water g':>10} {'Water ml':>10}  {'Range %':>12}")
    lines.append("-" * 76)
    for i in mix:
        p = FLOUR_PROFILES[i.flour_key]
        rng = f"{p.min_pct:.0f}-{p.max_pct:.0f}"
        lines.append(
            f"{i.flour_key:<14} {i.flour_g:>10.0f} {i.hydration_pct:>8.1f} {i.water_g:>10.0f} "
            f"{i.water_ml:>10.0f}  {rng:>12}"
        )
    lines.append("-" * 76)
    lines.append(
        f"{'TOTAL':<14} {total_flour:>10.0f} {weighted_hyd:>8.1f} {total_water:>10.0f} {total_water:>10.0f}"
    )
    lines.append("")
    lines.append(f"Weighted hydration: {weighted_hyd:.1f}%  (TA {ta:.1f})")
    return "\n".join(lines)


def print_examples() -> None:
    print(
        "\nEXAMPLES (copy/paste)\n"
        "1) Grams mode (simple):\n"
        "   python water_calc_mix.py --item wheat_550:350 --item spelt_1050:150 --firmness standard\n\n"
        "2) Grams mode with per-item override:\n"
        "   python water_calc_mix.py --item wheat_whole:400:84 --item spelt_630:100 --firmness standard\n\n"
        "3) Percent mode (must sum to 100% + needs total flour grams):\n"
        "   python water_calc_mix.py --total-flour-g 800 --item wheat_1050:70% --item spelt_whole:30% --firmness soft\n\n"
        "4) Percent mode with per-item override:\n"
        "   python water_calc_mix.py --total-flour-g 1000 --item wheat_550:60%:70 --item wheat_whole:40%:84\n"
    )


def print_flours() -> None:
    print("\nSUPPORTED FLOURS\n")
    for k in sorted(FLOUR_PROFILES.keys()):
        p = FLOUR_PROFILES[k]
        print(f"- {k:12}  range {p.min_pct:.1f}–{p.max_pct:.1f}  default {p.default_pct:.1f}  ({p.note})")

    print("\nCOMMON ALIASES (examples)\n")
    samples = [
        "weizen550 -> wheat_550",
        "weizen1050 -> wheat_1050",
        "weizenvollkorn -> wheat_whole",
        "dinkel630 -> spelt_630",
        "dinkel1050 -> spelt_1050",
        "dinkelvollkorn -> spelt_whole",
    ]
    for s in samples:
        print(f"- {s}")


def build_parser() -> argparse.ArgumentParser:
    description = (
        "Calculate water for yeast dough with mixed flours.\n\n"
        "Input modes:\n"
        "  Grams mode:   --item flour:GRAMS[:HYDRATION]\n"
        "  Percent mode: --total-flour-g N  AND  --item flour:PERCENT[:HYDRATION]\n"
        "               (PERCENT items must sum to 100)\n\n"
        "Hydration (water percent) is chosen per flour via --firmness unless you override it per item."
    )

    parser = argparse.ArgumentParser(
        prog="water_calc_mix.py",
        description=description,
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "--item",
        action="append",
        help=(
            "Repeatable ingredient entry.\n"
            "Formats:\n"
            "  flour:GRAMS[:HYDRATION]\n"
            "  flour:PERCENT[:HYDRATION]   (use a trailing percent sign in actual input)\n"
            "Examples (see --examples for copy/paste):\n"
            "  --item wheat_550:350\n"
            "  --item spelt_whole:30percent:78  (illustrative only; real examples are in --examples)"
        ),
    )

    parser.add_argument(
        "--firmness",
        default="standard",
        choices=["tight", "standard", "soft"],
        help="Pick min/default/max hydration per flour (ignored when hydration override is provided)."
    )

    parser.add_argument(
        "--total-flour-g",
        type=float,
        default=None,
        help="Required if any --item uses percentages (e.g., 800)."
    )

    parser.add_argument(
        "--examples",
        action="store_true",
        help="Print usage examples and exit."
    )

    parser.add_argument(
        "--list-flours",
        action="store_true",
        help="List supported flours and exit."
    )

    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.examples:
        print_examples()
        return

    if args.list_flours:
        print_flours()
        return

    if not args.item:
        parser.error("You must provide at least one --item. Use --examples to see how.")

    if args.total_flour_g is not None and args.total_flour_g <= 0:
        raise SystemExit("--total-flour-g must be > 0")

    try:
        mix = build_mix(args.item, args.firmness, args.total_flour_g)
    except ValueError as e:
        raise SystemExit(str(e))

    print(summarize(mix))


if __name__ == "__main__":
    main()
