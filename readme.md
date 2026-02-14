# Backing Slop
**All scripts were created with the help of AI.**

I have created Python scripts to help me bake with yeast dough. Each script has a --help flag with detailed explanations.

## bread_rise_time.py
Estimate rise time for YEAST dough (commercial yeast: instant or active dry).
Not for sourdough starters/levain, chemical leaveners, or laminated doughs.

Model (approx):
- Baseline: 7g dry yeast per 500g flour -> 1 hour at 25°C.
- Rise time scales ~ inversely with yeast-to-flour ratio (with mild diminishing returns).
- Temperature effect uses Q10 rule-of-thumb: every +10°C doubles activity (time halves).

This is an estimator. Real rise time depends on hydration, sugar/fat, salt,
kneading strength, dough temperature (not just room temp), yeast age, etc.

EXAMPLES
  Baseline (should be ~1 hour):
    python bread_rise_time.py --flour 500 --yeast 7 --temp 25

  Less yeast + cooler room:
    python bread_rise_time.py --flour 500 --yeast 3 --temp 21

  Bigger batch, same yeast:
    python bread_rise_time.py --flour 1000 --yeast 7 --temp 24

  Show the model constants:
    python bread_rise_time.py --flour 500 --yeast 7 --temp 25 --show-model

## water_calc_mix.py
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
