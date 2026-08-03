- Per-model weighting in the pct/token calibration fit (`calibrate()` in `hooks/usage_common.py`):
  weighting components by published price ratios fit better in one trial (worst residual 1.5 vs 2.1
  points) but didn't explain the spread. Worth revisiting if readings ever arrive under a genuinely
  different traffic mix.
