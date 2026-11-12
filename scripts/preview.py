#!/usr/bin/env python3
"""
Reference implementation of the widget's selection logic, for checking the index and for the
Chabad Display agent to port to JS (see IMPLEMENTATION.md).

  python3 scripts/preview.py                 # today
  python3 scripts/preview.py 2026-12-08      # any Gregorian date
  python3 scripts/preview.py 2026-12-08 --mode holiday --n 15
"""
import argparse, datetime, json, os, random
from pyluach import dates as ldates, parshios

D = os.path.join(os.path.dirname(__file__), "..", "public", "data")
load = lambda n: json.load(open(os.path.join(D, n), encoding="utf-8"))

def hebrew_context(g):
    """Everything the widget needs to know about a day. Diaspora schedule."""
    gd = ldates.GregorianDate(g.year, g.month, g.day)
    hd = gd.to_heb()
    shabbos = gd
    while shabbos.weekday() != 7:
        shabbos = shabbos + 1
    return {"hYear": hd.year, "hMonth": hd.month, "hDay": hd.day,
            "parsha": parshios.getparsha(shabbos) or [], "hakhel": hd.year % 7 == 1}

def _leap(y):
    return (7 * y + 1) % 19 < 7

def _resolve_month(sd, month, y):
    if month != 12:
        return month
    if sd.get("adar") == "last":
        return 13 if _leap(y) else 12
    if sd.get("adar") == "first":
        return 12 if _leap(y) else None
    return 12

def active_specials(ctx, calendar):
    """Same logic as specialStatus() in IMPLEMENTATION.md, using real Hebrew dates.
    Returns [(id, daysUntil)] nearest first; 0 = inside the window today."""
    today = ldates.HebrewDate(ctx["hYear"], ctx["hMonth"], ctx["hDay"])
    out = []
    for sd in calendar["specialDays"]:
        if sd.get("hakhelYearOnly"):
            if ctx["hakhel"]:
                out.append((sd["id"], 0))
            continue
        for y in (ctx["hYear"], ctx["hYear"] + 1):
            m1 = _resolve_month(sd, sd["month"], y)
            if not m1:
                continue
            start = ldates.HebrewDate(y, m1, sd["day"])
            m2 = _resolve_month(sd, sd.get("toMonth", sd["month"]), y)
            end = ldates.HebrewDate(y, m2, sd.get("to", sd["day"]))
            if end < start:
                end = ldates.HebrewDate(y + 1, m2, sd.get("to", sd["day"]))
            if start <= today <= end:
                out.append((sd["id"], 0)); break
            until = int(start - today)
            if 0 < until <= sd.get("lead", 0):
                out.append((sd["id"], until)); break
    return sorted(out, key=lambda x: x[1])

def playlist(g, mode="timely", n=20, seed=None):
    cal, parsha, special, otd, pools, videos = (load(x) for x in ("calendar.json", "parsha.json", "special.json", "onthisday.json", "pools.json", "videos.json"))
    ctx = hebrew_context(g)
    rnd = random.Random(seed)
    tiers = []  # (label, [aids]) in priority order

    if mode in ("timely", "onthisday"):
        tiers.append(("On this day", [e["aid"] for e in otd.get(f'{ctx["hMonth"]}-{ctx["hDay"]}', [])]))
    if mode in ("timely", "holiday"):
        for sid, until in active_specials(ctx, cal):
            s = special[sid]
            tiers.append((f'{s["name"]}' + (f" (in {until} day{'s' if until > 1 else ''})" if until else ""), s["aids"]))
        for sid, until in active_specials(ctx, cal):
            tiers.append((f'Aired around {special[sid]["name"]}', special[sid]["aired"]))
    if mode in ("timely", "parsha"):
        for i in ctx["parsha"]:
            p = parsha[str(i)]
            tiers.append((f'Parshas {p["name"]}', p["aids"]))
        for i in ctx["parsha"]:
            p = parsha[str(i)]
            tiers.append((f'Aired the week of {p["name"]}', p["aired"]))
    if mode == "onthisday":  # widen to the coming week when today is empty
        for k in range(1, 8):
            d = ldates.HebrewDate(ctx["hYear"], ctx["hMonth"], ctx["hDay"]) + k
            tiers.append((f"Coming up: {d.day}/{d.month}", [e["aid"] for e in otd.get(f"{d.month}-{d.day}", [])]))
    if mode == "livingtorah":
        tiers.append(("Living Torah", pools["livingtorah"]))
    if mode in ("random", "timely"):
        tiers.append(("Anything", pools["all"]))

    seen, out = set(), []
    for label, aids in tiers:
        aids = [a for a in aids if a not in seen]
        rnd.shuffle(aids)
        for a in aids:
            if len(out) >= n:
                break
            seen.add(a)
            out.append((label, a))
    return ctx, [(l, a, videos[str(a)]["title"], videos[str(a)].get("length")) for l, a in out]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", default=datetime.date.today().isoformat())
    ap.add_argument("--mode", default="timely", choices=["timely", "parsha", "holiday", "onthisday", "livingtorah", "random"])
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    ctx, items = playlist(datetime.date.fromisoformat(a.date), a.mode, a.n, seed=1)
    print(a.date, ctx)
    for label, aid, title, length in items:
        print(f"  [{label}] {title} ({length}) aid={aid}")
