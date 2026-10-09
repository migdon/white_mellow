# Carry + time-series momentum, 9 FX pairs (D1)

Data: Fed H.10 noon mid rates, 1999-01-04 → 2026-10-02 (EUR, GBP, AUD, NZD, JPY, CHF, CAD, NOK, SEK laban sa USD).
Ang carry ay galing sa sariling talaan ng mga policy rate (`carry_tsmom/policy_rates.py`, **approximate**).
Raw numbers: `carry_tsmom_results.json`. Reproduce: `python run_research.py`.

## Mga rule (itinakda bago tiningnan ang resulta, walang tuning)

| Rule | Ano | Status |
|---|---|---|
| CARRY_XS3 | long 3 pinakamataas ang rate, short 3 pinakamababa | primary |
| TSMOM_12M | sign ng 12-buwang excess return, bawat pair | primary |
| TSMOM_3M / 1M | ganoon din, 3 at 1 buwan | secondary |
| COMBO | 50/50 *risk* ng CARRY_XS3 at TSMOM_12M | primary |

Monthly rebalance. Signal sa month-end close; papasok sa susunod na close. Inverse-vol bawat pair, at 10% portfolio vol target (ex-ante).
Cost: tipikal na retail spread, at swap markup na 1%/taon bawat side sa gross notional.

## Resulta (Sharpe, net of cost)

| Rule | 1999–2008 | 2009–2016 | 2017–2026 | 2013–2026 (post-publication) | Buo (t) |
|---|---|---|---|---|---|
| CARRY_XS3 | +0.26 | +0.30 | −0.09 | −0.03 | +0.15 (t 0.8) |
| TSMOM_12M | +0.58 | −0.33 | −0.18 | −0.19 | +0.07 (t 0.4) |
| TSMOM_3M | +0.43 | +0.13 | −0.76 | −0.46 | −0.09 |
| TSMOM_1M | +0.33 | −0.27 | −0.46 | −0.35 | −0.13 |
| **COMBO** | **+0.84** | +0.03 | −0.20 | −0.14 | +0.23 (t 1.2) |

- **Kung walang cost (interbank), COMBO = 0.51 at carry = 0.45.** May totoong premium ito sa kasaysayan, at tugma ito sa literatura.
- **Pero halos lahat ng kita ay galing sa 1999–2008.** Mula 2009, halos zero ito. Mula 2013 (pagkatapos ma-publish ang mga papel), negatibo na ito net of cost. Ito rin ang nakikita sa mga published na update: humina nang husto ang G10 carry at FX trend pagkatapos ng 2008.
- **Null test** (circular shift; parehong cost at turnover, pero random ang timing): COMBO p = 0.028 kung mag-isa, p = 0.065 kapag tiningnan ang buong family ng 5 rule. Ibig sabihin, may impormasyon ang timing kumpara sa random. Pero ang tanong para sa account mo ay kung positibo ba ang net return, at doon t = 1.2 lang. **Hindi ito significant.**

## Ang nagpapasya: swap markup ng broker

Ang COMBO ay may average na 2.8x gross notional sa 10% vol. Kaya bawat 0.25% na markup ay nagbabawas ng mga 0.07 sa Sharpe:

| Markup bawat side | CARRY_XS3 | COMBO |
|---|---|---|
| 0% (interbank) | +0.45 | +0.50 |
| 0.5% | +0.30 | +0.37 |
| 1.0% | +0.15 | +0.23 |
| 1.5% | 0.00 | +0.10 |

Halos walang epekto ang spread (2x spread: 0.23 → 0.22) at ang pag-delay ng isang araw (0.23 → 0.23), dahil isang beses lang sa isang buwan ang trade.
**Ang swap ng broker mo ang pinakamahalagang input.** Makukuha ito ng `export_mt5.py`, at kinakalkula ng `run_research.py --mt5` ang aktwal na markup mula rito.

## Prop challenge (Monte Carlo, COMBO 2013+)

Mga ipinalagay: +8% target, −5% static max loss, 3% daily limit, close-to-close lang (kaya optimistic ito). Kapag walang edge, ang tsansang pumasa ay 5/(5+8) = **0.38**.

| Vol | Pasado ≤60 araw | Pasado ≤1 taon | Pasado ≤2 taon | Bagsak | Median na araw |
|---|---|---|---|---|---|
| 6% | 0.00 | 0.13 | 0.24 | 0.58 | 243 |
| 10% | 0.07 | 0.28 | 0.32 | 0.68 | 109 |
| 20% | 0.26 | 0.31 | 0.31 | 0.69 | 31 |

Mas mababa pa ito sa coin-flip baseline. Sa mababang vol, umaabot ng taon bago maabot ang target. Sa mataas na vol, nagiging sugal na ito. Sa 1999–2026, mga 1.1% ng mga araw ang mas masama sa −1.8% (sa 10% vol). Ang pinakamasamang araw ng TSMOM_12M ay −14.7% (SNB unpeg, Enero 2015). Ang buong max drawdown ng COMBO ay −50% sa 10% vol.

## Mga limitasyon (basahin bago maniwala)

1. **Ang rate table ay ginawa mula sa memorya**, dahil hindi maabot dito ang BIS at FRED. Sensitibo ang carry sa error nito: kapag dinagdagan ng ±0.5% noise, bumababa ang Sharpe mula 0.15 sa −0.06 hanggang +0.07. Kailangang i-verify laban sa BIS WS_CBPOL bago ito pagkatiwalaan.
2. Policy rate ang ginamit, hindi ang aktwal na tom-next o swap points. Ang tunay na forward points ay may basis (lalo na sa JPY at CHF).
3. Ang H.10 ay noon mid. Ang tunay na fill ay sa broker close, at ang rollover ay sa 17:00 NY.
4. Hindi naka-model ang intraday breach ng prop rules.

## Hatol

Totoo ang premium sa kasaysayan, pero kumikita lang ito sa interbank cost at karamihan ay bago 2009. Sa retail swap markup na ~1% at sa datos pagkatapos ng 2013, **wala itong edge na makikita**, at mas masama pa ito sa coin flip para sa prop challenge.
Para hindi ito ma-reject nang hindi patas, isa na lang ang kailangang test: patakbuhin ito sa sariling data ng broker mo. Kung ang markup ay ≤0.3%/side (bihira sa retail; minsan sa swap-free o institutional account), babalik ang Sharpe sa mga 0.4. Kahit ganoon, mababa pa rin iyon para sa 5% max drawdown.
