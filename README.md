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
