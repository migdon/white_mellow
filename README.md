# white_mellow — carry + TSMOM research (FX, D1)

Pagsusuri ng carry at time-series momentum sa 9 na USD pair. Ang resulta at hatol ay nasa
[`reports/carry_tsmom_report.md`](reports/carry_tsmom_report.md).

```
carry_tsmom/
  policy_rates.py   policy-rate history 1999-2025 (approximate, i-verify sa BIS)
  data.py           loaders: Fed H.10 (data/) o MT5 export
  backtest.py       signals, cost model, stats, null test, prop-challenge Monte Carlo
  export_mt5.py     kunin ang D1 + swap specs mula sa MT5 terminal mo
run_research.py     buong run -> reports/carry_tsmom_results.json
tests/test_sanity.py
```

## Patakbuhin

```bash
pip install numpy pandas
python run_research.py                 # Fed H.10 data (kasama sa repo)
python -m tests.test_sanity            # no-edge / planted-edge / look-ahead checks
```

Gamit ang data at swap ng broker mo (sa Windows, kung saan naka-install ang MT5):

```bash
pip install MetaTrader5
python -m carry_tsmom.export_mt5 --out mt5_export --suffix ""   # o ".r", "m", atbp.
python run_research.py --mt5 mt5_export --suffix ""
```

Sa mode na `--mt5`, kinakalkula ang swap markup ng broker mula sa `swap_long` at `swap_short`
(markup ≈ −(long + short)/2), at iyon ang ginagamit sa cost model.

## NBRO → FX (noise_fx/)

Sinusubok kung gagana ang Noise-Area rule ng NBRO sa 9 na FX pair. Ang protocol at pass rule ay isinulat
**bago** makita ang data: [`noise_fx/PROTOCOL.md`](noise_fx/PROTOCOL.md).

```bash
# sa PC na may MT5 (Tools > Options > Charts > Max bars in chart = Unlimited, tapos i-restart ang MT5)
python -m noise_fx.export_m5 --out m5_export --from 2012-01-01
# kahit saan
python -m noise_fx.run_fx --data m5_export
python -m noise_fx.tests.test_sanity
python -m noise_fx.tests.test_equivalence_nbro path/to/nbro_app.py   # parehong trade ba ang ginagawa ng engine at ng NBRO?
```

### Ibang index para sa umaga at hapon (PHT)

Ang protocol ay nasa [`noise_fx/PROTOCOL_INDICES.md`](noise_fx/PROTOCOL_INDICES.md): JPN225, HK50, AUS200, GER40, UK100,
gamit ang parehong NBRO rule. May kasama ring engine check sa NAS100 at SPX500.

```bash
python -m noise_fx.export_m5 --list                                   # hanapin ang pangalan ng mga index sa broker
python -m noise_fx.export_m5 --out m5_export --from 2012-01-01 --only <mga pangalan>
python -m noise_fx.run_indices --data m5_export --names NAS100=<pangalan> SPX500=<pangalan> ...
```

## TradingView indicator (tradingview/)

`tradingview/nbro_noise_area.pine` — the NBRO rule as a Pine v5 indicator for a 1–5 minute NAS100/SPX500 chart.
It draws the noise bands and the session VWAP, and marks entries, exits and the emergency stop. Alerts fire on the first
tick of each check bar. `tradingview/check_pine_logic.py` is a line-by-line Python port of the indicator; on Vantage
NAS100 and SPX500 M5 (2018–2026) it makes exactly the same trades as the validated engine (1,427/1,427 and 1,464/1,464).
