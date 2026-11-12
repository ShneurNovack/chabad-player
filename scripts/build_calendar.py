#!/usr/bin/env python3
"""
Stage 3: build the calendar layer and the precomputed lookup files the widget reads.

Inputs:  public/data/videos.json, topics.json, dates.json (from build_index.py + build_hub.py)
Outputs (public/data/):
  calendar.json   parsha + special-day definitions (Hebrew date windows, keyword ids, lead days)
  parsha.json     parsha index 0-53 -> {name, kid, aids[]}
  special.json    special-day id -> {name, aids[]}
  onthisday.json  "hMonth-hDay" -> [{aid, hYear}]  (union of the date index, dated topics and video event dates)
  pools.json      aids per mode: livingtorah, parsha, holiday, onthisday, all
Hebrew month numbering everywhere = Hebcal's: Nisan=1 ... Elul=6, Tishrei=7 ... Shevat=11, Adar/Adar I=12, Adar II=13.
"""
import json, os, re
from pyluach import dates as ldates, parshios  # pip install pyluach (Hebrew dates + diaspora parsha schedule)

D = os.path.join(os.path.dirname(__file__), "..", "public", "data")
load = lambda n: json.load(open(os.path.join(D, n), encoding="utf-8"))
def dump(n, o):
    p = os.path.join(D, n)
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {n} ({os.path.getsize(p)//1024} KB)")

REBBE_KID = 1242

# Index = Hebcal's parsha index (Sedra / parshiot array order, 0 = Bereshit).
# hebcal = Hebcal's English name; name = Chabad.org spelling; kid = Chabad.org keyword id.
PARSHIYOT = [
    ("Bereshit", "Bereishit", 80), ("Noach", "Noach", 81), ("Lech-Lecha", "Lech-Lecha", 82), ("Vayera", "Vayeira", 83),
    ("Chayei Sara", "Chayei Sarah", 550), ("Toldot", "Toldot", 904), ("Vayetzei", "Vayeitzei", 1076), ("Vayishlach", "Vayishlach", 1077),
    ("Vayeshev", "Vayeishev", 1078), ("Miketz", "Mikeitz", 1079), ("Vayigash", "Vayigash", 1099), ("Vayechi", "Vayechi", 1100),
    ("Shemot", "Shemot", 1088), ("Vaera", "Va'eira", 1089), ("Bo", "Bo", 1090), ("Beshalach", "Beshalach", 1091),
    ("Yitro", "Yitro", 1092), ("Mishpatim", "Mishpatim", 1093), ("Terumah", "Terumah", 1094), ("Tetzaveh", "Tetzaveh", 1095),
    ("Ki Tisa", "Ki Tisa", 1096), ("Vayakhel", "Vayak'hel", 1097), ("Pekudei", "Pekudei", 1098), ("Vayikra", "Vayikra", 1101),
    ("Tzav", "Tzav", 1102), ("Shmini", "Shemini", 1103), ("Tazria", "Tazria", 1104), ("Metzora", "Metzora", 1105),
    ("Achrei Mot", "Acharei", 1106), ("Kedoshim", "Kedoshim", 1107), ("Emor", "Emor", 1108), ("Behar", "Behar", 1109),
    ("Bechukotai", "Bechukotai", 1110), ("Bamidbar", "Bamidbar", 1111), ("Nasso", "Naso", 1112), ("Beha'alotcha", "Behaalotecha", 1113),
    ("Sh'lach", "Shlach", 1114), ("Korach", "Korach", 1115), ("Chukat", "Chukat", 1116), ("Balak", "Balak", 1117),
    ("Pinchas", "Pinchas", 1118), ("Matot", "Matot", 1119), ("Masei", "Massei", 1120), ("Devarim", "Devarim", 1121),
    ("Vaetchanan", "Va'etchanan", 1122), ("Eikev", "Eikev", 1123), ("Re'eh", "Re'eh", 1124), ("Shoftim", "Shoftim", 1125),
    ("Ki Teitzei", "Ki Teitzei", 1126), ("Ki Tavo", "Ki Tavo", 1127), ("Nitzavim", "Nitzavim", 1128), ("Vayeilech", "Vayelech", 1129),
    ("Ha'azinu", "Ha'azinu", 1130), ("Vezot Haberakhah", "Vezot Hab'rachah", 1131),
]
# Extra keywords that belong to a combined reading or a whole book, used only as fallbacks.
EXTRA_PARSHA_KIDS = {39: [1581], 38: [1581]}  # Chukat-Balak combined topic
BOOK_OF = lambda i: 0 if i < 12 else 1 if i < 23 else 2 if i < 33 else 3 if i < 43 else 4

# Special days. month/day in Hebcal numbering. "to" = last day of the window (same month unless toMonth given).
# lead = days before the window when it starts showing; kids = Chabad keyword/topic ids.
# adar: "last" means Adar II in leap years, Adar in regular years (Purim, 7 Adar...); "first" = Adar I only.
SPECIAL = [
    # Tishrei
    {"id": "rosh-hashanah", "name": "Rosh Hashanah", "month": 7, "day": 1, "to": 2, "lead": 10, "kids": [123, 2090, 8088, 4234]},
    {"id": "tishrei-6", "name": "6 Tishrei: Yahrzeit of Rebbetzin Chana", "month": 7, "day": 6, "lead": 2, "kids": [20380, 1399]},
    {"id": "yom-kippur", "name": "Yom Kippur", "month": 7, "day": 10, "lead": 5, "kids": [126, 11605]},
    {"id": "sukkos", "name": "Sukkos", "month": 7, "day": 15, "to": 21, "lead": 4, "kids": [127, 2106, 10992, 128]},
    {"id": "simchas-torah", "name": "Shemini Atzeres & Simchas Torah", "month": 7, "day": 22, "to": 23, "lead": 2, "kids": [131]},
    {"id": "hakhel", "name": "Hakhel year", "hakhelYearOnly": True, "kids": [14375]},
    # Cheshvan
    {"id": "cheshvan-7", "name": "7 Cheshvan", "month": 8, "day": 7, "lead": 1, "kids": [2121]},
    # Kislev
    {"id": "rosh-chodesh-kislev", "name": "Rosh Chodesh Kislev", "month": 9, "day": 1, "lead": 3, "kids": [17982, 21870]},
    {"id": "kislev-14", "name": "14 Kislev: The Rebbe's wedding", "month": 9, "day": 14, "lead": 2, "kids": [22992]},
    {"id": "yud-tes-kislev", "name": "Yud-Tes Kislev", "month": 9, "day": 19, "to": 20, "lead": 7, "kids": [133]},
    {"id": "chanukah", "name": "Chanukah", "month": 9, "day": 25, "to": 2, "toMonth": 10, "lead": 10, "kids": [134, 8669, 1367, 2314, 13214]},
    # Teves
    {"id": "hei-teves", "name": "Hei Teves (Didan Notzach)", "month": 10, "day": 5, "lead": 3, "kids": [11884]},
    {"id": "asara-bteves", "name": "10 Teves", "month": 10, "day": 10, "lead": 1, "kids": [137, 15491]},
    {"id": "teves-24", "name": "24 Teves: Yahrzeit of the Alter Rebbe", "month": 10, "day": 24, "lead": 2, "kids": [14731]},
    # Shevat
    {"id": "yud-shevat", "name": "Yud Shevat", "month": 11, "day": 10, "lead": 7, "kids": [138]},
    {"id": "tu-bishvat", "name": "Tu B'Shevat", "month": 11, "day": 15, "lead": 2, "kids": [139]},
    {"id": "shevat-22", "name": "22 Shevat: Yahrzeit of Rebbetzin Chaya Mushka", "month": 11, "day": 22, "lead": 3, "kids": [18176, 1398]},
    # Adar
    {"id": "purim-katan", "name": "Purim Katan", "month": 12, "day": 14, "adar": "first", "lead": 1, "kids": [2699]},
    {"id": "adar", "name": "Month of Adar", "month": 12, "day": 1, "to": 29, "adar": "last", "lead": 0, "kids": [140]},
    {"id": "adar-7", "name": "7 Adar", "month": 12, "day": 7, "adar": "last", "lead": 1, "kids": [1289]},
    {"id": "purim", "name": "Purim", "month": 12, "day": 14, "to": 15, "adar": "last", "lead": 7, "kids": [141, 143, 1314, 11915, 12026]},
    {"id": "adar-27", "name": "27 Adar", "month": 12, "day": 27, "adar": "last", "lead": 2, "kids": [12001]},
    # Nissan
    {"id": "nissan-11", "name": "11 Nissan: The Rebbe's birthday", "month": 1, "day": 11, "lead": 7, "kids": [153, 2045]},
    {"id": "pesach", "name": "Pesach", "month": 1, "day": 15, "to": 22, "lead": 14, "kids": [145, 1380, 2905, 7114, 149, 144]},
    {"id": "sefirah", "name": "Sefiras HaOmer", "month": 1, "day": 16, "to": 5, "toMonth": 3, "lead": 0, "kids": [150, 2600]},
    # Iyar
    {"id": "iyar-2", "name": "2 Iyar: Birthday of the Rebbe Maharash", "month": 2, "day": 2, "lead": 1, "kids": [20704]},
    {"id": "pesach-sheni", "name": "Pesach Sheni", "month": 2, "day": 14, "lead": 1, "kids": [2943]},
    {"id": "lag-baomer", "name": "Lag BaOmer", "month": 2, "day": 18, "lead": 5, "kids": [154, 2734]},
    # Sivan
    {"id": "shavuos", "name": "Shavuos", "month": 3, "day": 6, "to": 7, "lead": 7, "kids": [151]},
    {"id": "sivan-28", "name": "28 Sivan: The Rebbe's arrival in America", "month": 3, "day": 28, "lead": 3, "kids": [16119]},
    # Tammuz / Av
    {"id": "gimmel-tammuz", "name": "Gimmel Tammuz", "month": 4, "day": 3, "lead": 7, "kids": [152, 17746]},
    {"id": "yud-beis-tammuz", "name": "12-13 Tammuz", "month": 4, "day": 12, "to": 13, "lead": 4, "kids": [8971, 21693]},
    {"id": "three-weeks", "name": "The Three Weeks", "month": 4, "day": 17, "to": 9, "toMonth": 5, "lead": 0, "kids": [156, 155, 158, 237, 8400, 12479]},
    {"id": "tu-bav", "name": "15 Av", "month": 5, "day": 15, "lead": 2, "kids": [1685]},
    {"id": "av-20", "name": "20 Av: Yahrzeit of Reb Levi Yitzchak", "month": 5, "day": 20, "lead": 2, "kids": [159]},
    # Elul
    {"id": "elul", "name": "Month of Elul", "month": 6, "day": 1, "to": 29, "lead": 0, "kids": [160]},
    {"id": "chai-elul", "name": "Chai Elul", "month": 6, "day": 18, "lead": 4, "kids": [161]},
]

def main():
    videos = load("videos.json"); topics = load("topics.json"); dates = load("dates.json")
    playable = {k for k, v in videos.items() if v.get("allowEmbed", True) and v.get("hasStream", True)}
    # Collapse duplicates (same video published in Living Torah and in a hub category): same title + length.
    norm = lambda t: re.sub(r"[^a-z0-9]+", " ", (t or "").lower().replace("’", "'")).strip()
    canon = {}
    for k in sorted(videos, key=lambda k: (videos[k].get("source") != "livingtorah", int(k))):
        v = videos[k]
        v.pop("duplicateOf", None)
        key = (norm(v.get("title")), v.get("length"))
        if key[0] and key in canon:
            v["duplicateOf"] = int(canon[key])
            playable.discard(k)
        else:
            canon[key] = k
    print("duplicates collapsed:", sum(1 for v in videos.values() if v.get("duplicateOf")))
    by_kid = {}
    for k, v in videos.items():
        if k not in playable or not v.get("rebbe", True):
            continue
        for kid in set((v.get("keywords") or []) + (v.get("topics") or [])):
            by_kid.setdefault(int(kid), set()).add(int(k))
    pick = lambda kids: sorted(set().union(*[by_kid.get(int(x), set()) for x in kids]) if kids else set())

    # "Aired" tier: Living Torah was a weekly program timed to the calendar, so a video's publication date
    # says which parsha week (next Shabbos, diaspora) and which Hebrew date it originally aired.
    # Days where more than BULK_THRESHOLD videos were published are archive imports, not weekly airings.
    BULK_THRESHOLD = 16
    per_day = {}
    for v in videos.values():
        per_day[v.get("published")] = per_day.get(v.get("published"), 0) + 1
    aired_parsha, aired_heb = {}, {}
    for k, v in videos.items():
        v.pop("airedHebrew", None); v.pop("airedParsha", None)
        if k not in playable or not v.get("rebbe", True) or not v.get("published"):
            continue
        if per_day.get(v["published"], 0) > BULK_THRESHOLD:
            continue
        y, m, d = map(int, v["published"].split("-"))
        g = ldates.GregorianDate(y, m, d)
        h = g.to_heb()
        aired_heb[int(k)] = (h.month, h.day)
        v["airedHebrew"] = {"hMonth": h.month, "hDay": h.day, "hYear": h.year}
        sh = g
        while sh.weekday() != 7:
            sh = sh + 1
        ps = parshios.getparsha(sh) or []
        v["airedParsha"] = ps
        for i in ps:
            aired_parsha.setdefault(i, []).append(int(k))

    parsha = {}
    for i, (heb, name, kid) in enumerate(PARSHIYOT):
        aids = pick([kid] + EXTRA_PARSHA_KIDS.get(i, []))
        aired = sorted(set(aired_parsha.get(i, [])) - set(aids))
        parsha[i] = {"hebcal": heb, "name": name, "kid": kid, "aids": aids, "aired": aired}

    def in_window(sd, hm, hd):
        """Is Hebrew (month, day) inside special day sd's window, widened by its lead days? (approximate: 30-day months)"""
        if sd.get("hakhelYearOnly"):
            return False
        norm = lambda mm: 12 if mm in (12, 13) else mm
        order = lambda mm: (norm(mm) - 7) % 12   # Tishrei = 0 ... Elul = 11
        pos = lambda mm, dd: order(mm) * 30 + dd
        start = pos(sd["month"], sd["day"]) - sd.get("lead", 0)
        end = pos(sd.get("toMonth", sd["month"]), sd.get("to", sd["day"]))
        p = pos(hm, hd)
        return start <= p <= end if start >= 0 else (p >= start + 360 or p <= end)
    special = {}
    for sd in SPECIAL:
        aids = pick(sd["kids"])
        aired = sorted(a for a, (hm, hd) in aired_heb.items() if in_window(sd, hm, hd) and a not in aids) if sd.get("lead", 0) or sd.get("to") else []
        special[sd["id"]] = {"name": sd["name"], "aids": aids, "aired": aired}

    # On this day: date index + dated topics ("19 Kislev 5747") + each video's own event date
    MONTHS = {"Nissan": 1, "Iyar": 2, "Sivan": 3, "Tammuz": 4, "Av": 5, "Elul": 6, "Tishrei": 7, "Cheshvan": 8,
              "Kislev": 9, "Tevet": 10, "Shevat": 11, "Adar": 12, "Adar I": 12, "Adar II": 13}
    otd = {}
    def add(m, d, aid, y):
        if str(aid) in playable:
            e = otd.setdefault(f"{m}-{d}", {})
            e.setdefault(int(aid), y)
    for key, entries in dates.items():
        m, d = key.split("-")
        for e in entries:
            for aid in e["aids"]:
                add(int(m), int(d), aid, e["hYear"])
    for tid, t in topics.items():
        mt = re.fullmatch(r"(\d{1,2}) (Adar II|Adar I|[A-Z][a-z]+) (\d{4})", t["name"])
        if mt and mt.group(2) in MONTHS:
            for aid in t["aids"]:
                add(MONTHS[mt.group(2)], int(mt.group(1)), aid, int(mt.group(3)))
    for k, v in videos.items():
        ev = v.get("event") or {}
        if ev.get("hMonth") and ev.get("hDay"):
            add(ev["hMonth"], ev["hDay"], k, ev.get("hYear"))
    onthisday = {k: [{"aid": a, "hYear": y} for a, y in sorted(v.items(), key=lambda x: (x[1] or 0))]
                 for k, v in sorted(otd.items(), key=lambda kv: tuple(map(int, kv[0].split("-"))))}

    pools = {
        "all": sorted(int(k) for k in playable if videos[k].get("rebbe", True)),
        "livingtorah": sorted(int(k) for k in playable if videos[k].get("source", "livingtorah") == "livingtorah"),
        "parsha": sorted(set().union(*[set(p["aids"]) | set(p["aired"]) for p in parsha.values()])),
        "holiday": sorted(set().union(*[set(s["aids"]) for s in special.values()])),
        "onthisday": sorted({e["aid"] for v in onthisday.values() for e in v}),
    }

    dump("calendar.json", {
        "monthNumbering": "hebcal (Nisan=1 ... Adar/Adar I=12, Adar II=13)",
        "rebbeKeyword": REBBE_KID,
        "parshiyot": [{"index": i, "hebcal": h, "name": n, "kid": k, "book": BOOK_OF(i)} for i, (h, n, k) in enumerate(PARSHIYOT)],
        "specialDays": SPECIAL,
    })
    slim = {}
    for k in sorted(playable, key=int):
        v = videos[k]
        if not v.get("rebbe", True):
            continue
        ev = v.get("event") or {}
        slim[k] = {"t": v.get("title"), "len": v.get("length"), "img": v.get("poster") or v.get("thumb"),
                   "sec": v.get("section") or (v.get("categories") or [None])[0], "src": v.get("source", "livingtorah"),
                   "pub": v.get("published"), "ev": [ev["hYear"], ev["hMonth"], ev["hDay"]] if ev.get("hMonth") else None,
                   "d": (v.get("description") or "")[:200]}
    dump("catalog.json", slim)
    dump("parsha.json", parsha)
    dump("special.json", special)
    dump("onthisday.json", onthisday)
    dump("pools.json", pools)
    print({k: len(v) for k, v in pools.items()})
    b = load("build.json")
    b["final"] = {"uniquePlayableRebbeVideos": len(slim), "duplicatesCollapsed": sum(1 for v in videos.values() if v.get("duplicateOf")),
                  "pools": {k: len(v) for k, v in pools.items()}, "onThisDayKeys": len(onthisday)}
    dump("build.json", b)
    print("parsha coverage (tagged+aired):", {p["name"]: f'{len(p["aids"])}+{len(p["aired"])}' for p in parsha.values()})
    print("special coverage (tagged+aired):", {k: f'{len(v["aids"])}+{len(v["aired"])}' for k, v in special.items()})
    dump("videos.json", videos)
    print("onthisday keys:", len(onthisday))

if __name__ == "__main__":
    main()
