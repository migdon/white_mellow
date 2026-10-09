# ORB (orb_app.py) — can the exit fix "lose 1R, win 0.75R"?  No.

Code: `bot_audit/orb_exits.py`. Vantage M5 2012-2026. Entry exactly as orb_app.py (75-min range from NY 9:00, M5 close beyond it,
EURUSD short only / USDJPY long only, stop = far side of the range +/- ATR14). Exploratory: ~11 exits x 2 markets x 2 holding rules,
so a single t of 2.6 is not significant (Bonferroni needs ~3.2). Swap is not counted (it matters for the multi-day holds).

Why wins are 0.75R: the stop sits beyond the WHOLE range, the target is 1x the range, so the target is only ~0.74R (median).

| Exit | EURUSD short (held until stop/target) | USDJPY long (held until stop/target) |
|---|---|---|
| current: 50% at 0.75R + BE | 56% win, +0.75 / -1.00, **-0.026R** | 58% win, **+0.011R** |
| fixed 1R / 2R | -0.046R / -0.076R | +0.020R / +0.046R |
| BE at 1R, target 2R | -0.057R | +0.064R |
| 25% every 0.5R, trail 1 step | 64% win, -0.045R | 66% win, +0.009R |
| 25% every 0.75R, trail 1 step | -0.025R | +0.039R |
| 25% every 1R, trail 1 step | -0.048R | +0.070R (t 2.65) |
| no target | -0.062R | +0.242R |

Closed the same day at 23:55 server instead, every exit loses on both pairs (-0.003R to -0.032R).
Baseline: USDJPY long EVERY day at 17:15 with no breakout signal: no target +0.265R, 25%-every-1R +0.018R, BE/2R +0.021R.
So the USDJPY "profit" is mostly the 2012-2026 yen slide (USDJPY ~78 -> ~150), not the ORB signal; the direction was chosen
after seeing that data. Changing the exit moves win rate against win size, but leaves the average about the same.
