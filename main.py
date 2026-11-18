#!/usr/bin/env python3
"""Forecast GTA VI launch-day Twitch viewers, hour by hour.

Approach (validated leave-one-out over 37 past big launches): the launch day
does NOT spike and decay, it builds into the evening -- median peak around
hour 19-20 at ~2.0-2.4x the hour-1 print. So instead of assuming every hour
stays at the hour-1 level (the house baseline), this program pools the
empirical log-ratios ln(viewers_h / viewers_1) of past launches, per UTC
hour, and forecasts

    q_tau(h) = v1 * exp(Q_tau[ ln(v_h / v_1) ])

where Q_tau is the empirical quantile of the pooled log-ratios at hour h and
v1 is the case's hour-1 print. Log space is the natural scale here: the score
is pinball loss on the log scale, and the ratio distribution has a ferocious
upper tail (a slow-burn launch can peak 100x+ its hour-1 print), so honest
empirical quantiles -- including a very wide 95% band late in the day -- beat
any fitted Gaussian fan.

Pool rules (what the validation found):
- Pool from the case file's own `comparables`, computed at runtime, so the
  final case (42 comparables, incl. the 4 practice launches) is used as given.
- Exclude the GTA VI category's own pre-release history (name contains
  "Grand Theft Auto VI"): it is not a launch, it has no release day.
- Exclude the 4 simultaneous-global-unlock launches by name (Black Myth:
  Wukong, Hollow Knight: Silksong, 007 First Light, Battlefield 6): their
  hour-1 print is taken before the game unlocks anywhere, so their ratios
  (tiny hour-1, gigantic later peak) do not belong in a rolling-unlock pool.
  GTA VI unlocks at midnight local time, rolling by timezone, like the rest
  of the pool. Identifying them by name -- not by any v1/pre-launch ratio
  rule -- matters: ratio rules drop the wrong launches.
- If the case carries no usable comparables, fall back to the pooled table
  measured during validation (FALLBACK below, pool n=33).

Validation (leave-one-out over the 37 comparable launches):
- rolling-launch subset (the GTA VI analogue, n=7): loss 0.396 vs house
  baseline 0.451, coverage 0.93. All 37: 0.717 vs house 0.930.
- Killed with numbers: unlock-anchored curves, surge-anchored curves,
  ensembles, peak-shape medians, channels as a level anchor, pre-launch
  baseline as a level anchor, trimming low hour-1 launches, spread rescaling.

Stdlib only, deterministic (no randomness, no network, no wall-clock use),
fast: the whole pool is a few dozen launches x 24 hours.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
HOURS = list(range(2, 25))
MAX_VIEWERS = 1_000_000_000

# Simultaneous-global-unlock launches: hour 1 is pre-unlock, ratios unusable.
EXCLUDE_NAMES = {
    "Black Myth: Wukong",
    "Hollow Knight: Silksong",
    "007 First Light",
    "Battlefield 6",
}

# Pooled log-ratio quantiles [q05, q25, q50, q75, q95] per hour, measured
# leave-one-out over the kit's comparables (pool n=33, ex-simultaneous).
# Only a fallback: the live path recomputes these from the case file.
FALLBACK = {
    2: [-0.3641, -0.2573, -0.1376, -0.0047, 0.2811],
    3: [-1.0525, -0.4056, -0.2829, -0.0916, 0.2586],
    4: [-0.8912, -0.6558, -0.3100, -0.1607, 0.2452],
    5: [-1.2187, -0.4864, -0.2727, -0.0743, 0.2400],
    6: [-1.1820, -0.6762, -0.2377, 0.0669, 0.7583],
    7: [-1.0133, -0.5413, -0.2316, 0.1112, 0.9338],
    8: [-0.8808, -0.5937, -0.2032, 0.1463, 1.4296],
    9: [-0.8859, -0.6826, -0.1504, 0.1779, 2.0865],
    10: [-0.8618, -0.6771, -0.1642, 0.1361, 3.2494],
    11: [-0.8661, -0.6929, -0.1230, 0.2547, 3.4482],
    12: [-0.8706, -0.5651, -0.0328, 0.3957, 3.8136],
    13: [-0.6839, -0.4753, 0.0457, 0.6764, 4.0661],
    14: [-0.5614, -0.2996, 0.1274, 0.8443, 4.2660],
    15: [-0.4939, -0.2523, 0.3327, 0.9673, 4.5206],
    16: [-0.4600, -0.0821, 0.4629, 1.0016, 5.2772],
    17: [-0.3891, 0.1803, 0.4658, 1.0171, 5.2692],
    18: [-0.2006, 0.2336, 0.5368, 1.2805, 5.4577],
    19: [-0.1057, 0.2238, 0.7173, 1.7282, 5.5176],
    20: [-0.1393, 0.2122, 0.8087, 1.6450, 5.6345],
    21: [-0.1238, 0.1842, 0.8124, 1.6668, 5.6106],
    22: [-0.1557, 0.1384, 0.7772, 1.6008, 5.6041],
    23: [-0.2643, 0.0530, 0.7410, 1.4508, 5.5438],
    24: [-0.3349, 0.0407, 0.6431, 1.2373, 5.4784],
}


def round2(x):
    """Round to 2 decimals, half up (same convention as the kit's starter)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if float(value).is_integer() else value


def parse_time(text):
    """ISO-8601 UTC timestamp -> aware datetime (accepts trailing Z)."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def hour_index(day_start, when):
    """1-based UTC hour of the release day containing `when`."""
    delta = (when - day_start).total_seconds()
    return int(delta // 3600) + 1


def empirical_quantile(sorted_values, tau):
    """Linear-interpolation quantile of a sorted list (type-7 style)."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    pos = tau * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def pool_log_ratios(case):
    """Per-hour pooled ln(v_h / v_1) across the case's comparables.

    Returns {hour: sorted [log-ratios]}. A comparable contributes a ratio
    for hour h only when it has a positive hour-1 print and a positive
    print at hour h on its own release day.
    """
    pool = {h: [] for h in HOURS}
    for comp in case.get("comparables") or []:
        name = comp.get("name") or ""
        if "Grand Theft Auto VI" in name:
            continue
        if name in EXCLUDE_NAMES:
            continue
        try:
            day_start = parse_time(comp["day_start"])
        except (KeyError, TypeError, ValueError):
            continue
        by_hour = {}
        for row in comp.get("hourly") or []:
            try:
                viewers = float(row["viewers"])
                when = parse_time(row["from"])
            except (KeyError, TypeError, ValueError):
                continue
            if viewers <= 0:
                continue
            h = hour_index(day_start, when)
            if 1 <= h <= 24 and h not in by_hour:
                by_hour[h] = viewers
        v1 = by_hour.get(1)
        if not v1:
            continue
        log_v1 = math.log(v1)
        for h in HOURS:
            vh = by_hour.get(h)
            if vh:
                pool[h].append(math.log(vh) - log_v1)
    for h in HOURS:
        pool[h].sort()
    return pool


def hour1_print(case):
    """The case's hour-1 print, floored at 1 viewer (per the rules)."""
    known = case.get("known") or []
    if known:
        try:
            v = float(known[0]["viewers"])
            if v > 0:
                return v
        except (KeyError, TypeError, ValueError):
            pass
    hourly = case.get("history_hourly") or []
    if hourly:
        try:
            v = float(hourly[-1]["viewers"])
            if v > 0:
                return v
        except (KeyError, TypeError, ValueError):
            pass
    return 1.0


def forecast_case(case):
    """Five quantiles per hour (2..24) for one case dict."""
    v1 = hour1_print(case)
    pool = pool_log_ratios(case)
    rows = []
    for h in HOURS:
        ratios = pool.get(h) or []
        if len(ratios) >= 3:
            log_qs = [empirical_quantile(ratios, tau) for tau in LEVELS]
        else:
            # Too few pool members at this hour: use the measured fallback.
            log_qs = FALLBACK[h]
        qs = []
        prev = 0.0
        for lq in log_qs:
            q = v1 * math.exp(lq)
            q = max(q, 1.0)
            q = min(q, float(MAX_VIEWERS))
            q = max(q, prev)  # keep quantiles non-decreasing after rounding
            q = round2(q)
            prev = q
            qs.append(q)
        rows.append({"hour": h, "q": qs})
    return {"hours": rows}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(n for n in os.listdir(in_dir) if n.endswith(".in"))
    for name in names:
        case_id = name[:-3]
        with open(os.path.join(in_dir, name), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        result = forecast_case(case)
        out_path = os.path.join(out_dir, case_id + ".out")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
