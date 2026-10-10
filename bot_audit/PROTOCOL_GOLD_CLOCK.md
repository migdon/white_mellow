# Protocol — gold "around the clock" pattern (Donati & Jung, Copenhagen Business School thesis), written BEFORE running

Claim: gold rises during eastern (Asian) trading hours and falls for the rest of the day (hat-shaped seasonality).
Data: Vantage XAUUSD M5, Sep 2018 - Oct 2026, server time = New York + 7 (London 08:00 = server 10:00 all year).
G1 (primary): LONG from 01:05 server (gold reopens at 01:00) to 10:00 server (London open) every trading day. Closed the same day: no swap.
G2: SHORT from 10:00 server to 23:50 server (London open to before the daily close) every trading day.
Costs: Atlas spread $0.43 per round trip (measured), shorts pay it at exit.
PASS (each): mean net return per day > 0 with t >= 2.24 (Bonferroni over 2), both halves > 0, > 0 at 2x spread.
Information only: no cost; year by year; the two together.
