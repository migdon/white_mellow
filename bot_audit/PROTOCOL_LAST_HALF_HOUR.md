# Protocol — market intraday momentum (last half hour), written BEFORE running

Data: Vantage NAS100.r / SP500.r M5, Sep 2018 - Oct 2026; New York time = server - 7.
Close proxy = price at 15:55 NY (the CFD session ends at 16:00; NBRO also exits at 15:55).
R1 (Gao, Han, Li & Zhou 2018, JFE): sign of the return from yesterday's 15:55 to today's 10:00 -> same-direction position
   from 15:30 to 15:55 NY.
R2 (Baltussen, Da, Lammers & Martens 2021, JFE, futures): sign of the return from yesterday's 15:55 to today's 15:30 ->
   same-direction position from 15:30 to 15:55 NY.
Costs: Atlas spread per round trip in US hours (NAS100 1.87, SPX500 0.8 points, measured). No swap (closed the same day).
PASS (each rule, each index): mean net return > 0 with t >= 2.5 (Bonferroni over 4), both halves > 0, > 0 at 2x spread.
Information only: no cost; only days whose signal is in its top 20% by size (the papers find it stronger on big-move days).
