# NBRO: can the losses be made smaller? (tighter stop, screened on NBRO's own trades via their worst open loss)

Approximation: a trade whose worst open loss reached -s% is booked at -s% (no slippage or gaps beyond the stop).
| Stop | NAS100 total / avg loss / win % | SPX500 total / avg loss / win % |
|---|---|---|
| 1.0% (current emergency stop) | +98% / -0.39% / 44% | +53% / -0.32% / 44% |
| 0.7% | +106% / -0.38% / 43% | +52% / -0.31% / 43% |
| 0.5% | +105% / -0.34% / 42% | +52% / -0.29% / 42% |
| 0.4% | +105% / -0.31% / 40% | +48% / -0.27% / 40% |
| 0.3% | +104% / -0.26% / 36% | +36% / -0.23% / 38% |
| 0.2% | +72% / -0.19% / 29% | +40% / -0.18% / 33% |
A 0.4-0.7% stop makes the average loss smaller at about the same total (NAS100 +5-8%, within noise for 5 tries);
below 0.4% it cuts too many winners. Sizing up so the tighter stop risks the same 1% (Atlas, NBRO + gold 1%):
1.0% stop 45/74/96%, 4% breached; 0.7% 56/76/91%, 9%; 0.5% 64/77/82%, 18% — faster but more breaches, i.e. more risk.
No change made to NBRO.
