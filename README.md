# makefun-gta6-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/zonacryptocoin/makefun-gta6-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/zonacryptocoin/makefun-gta6-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in each hour of its release day (2026-11-19 UTC), from the first hour's viewer count, as five quantiles per hour. The launch day does not spike and decay — it builds into the evening (median peak ~hour 19–20 at ~2.0–2.4× the hour-1 print) — so instead of assuming every hour stays at the hour-1 level, `main.py` pools the empirical log-ratios `ln(viewers_h / viewers_1)` of 30+ past big launches per UTC hour, straight from the case file's own comparables, and forecasts `q_tau(h) = v1 * exp(Q_tau)`. Rolling midnight-local launches only: the four simultaneous-global-unlock launches are excluded by name (their hour-1 print is pre-unlock), as is the GTA VI category's own pre-release history. Validated leave-one-out over 37 past launches: loss 0.396 on the rolling-launch subset vs 0.451 for the house baseline (0.717 vs 0.930 over all 37). Unlock-anchored curves, surge-anchored curves, ensembles, peak-shape medians, channels and pre-launch baselines as level anchors were all tested and killed with numbers. Python 3 stdlib only, deterministic, no network.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=5j9p514c&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
