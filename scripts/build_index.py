#!/usr/bin/env python3
"""
Build the Living Torah index (Rebbe videos) used by the timely-video widget.

Sources (all public, plain GET with an honest User-Agent; spoofing a browser UA trips Cloudflare):
  1. Catalog:  /therebbe/livingtorah/default_cdo/aid/42100/jewish/Living-Torah.htm/page/N   (60 cards/page)
  2. Dates:    /therebbe/livingtorah/default_cdo/index/true/indextype/date  -> /default_cdo/month/M/day/D/year/Y
  3. Topics:   /therebbe/livingtorah/default_cdo/index/true/indextype/topic -> /default_cdo/topicid/ID
  4. Per video metadata: https://www.chabad.org/api/content/{aid}/metadata  (publication date, disc/program, keywords)
  5. Per video media:    https://www.chabad.org/multimedia/mediaplayer/flash_media_player_content.xml.asp?what=json&aid={aid}
                         (length, poster, AllowEmbed; the HLS URL is fetched live at play time, not stored)

Usage: python3 scripts/build_index.py [--out public/data] [--workers 5] [--skip-media]
Writes: videos.json, topics.json, dates.json, build.json  (calendar.json is hand-curated, see build_calendar.py)
"""
import argparse, concurrent.futures as cf, html, json, os, re, sys, time, urllib.request, urllib.error

BASE = "https://www.chabad.org"
UA = "ChabadPlayerIndex/1.0 (+https://github.com/ShneurNovack/chabad-player)"
LT = "/therebbe/livingtorah/default_cdo"

def get(url, tries=4):
    if url.startswith("/"):
        url = BASE + url
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            err = e
        except Exception as e:
            err = e
        time.sleep(1.5 * (i + 1))
    print("FAILED", url, err, file=sys.stderr)
    return None

def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()

CARD = re.compile(r'<article class="vs-video-card[^"]*">(.*?)</article>', re.S)

def parse_cards(page):
    out = []
    for c in CARD.findall(page or ""):
        m = re.search(r'player_cdo/aid/(\d+)/jewish/', c)
        if not m:
            continue
        g = lambda cls: clean((re.search(r'class="vs-video-card__%s[^"]*"[^>]*>(.*?)</div>' % cls, c, re.S) or [None, ""])[1])
        img = re.search(r'<img[^>]+src="([^"?]+)', c)
        out.append({
            "aid": int(m.group(1)),
            "title": g("title"),
            "section": g("sectionname") or None,
            "dateText": g("date") or None,
            "description": g("description"),
            "thumb": img.group(1) if img else None,
        })
    return out

def results_total(page):
    m = re.search(r"Results\s+[\d,]+-[\d,]+\s+of\s+([\d,]+)", page or "")
    return int(m.group(1).replace(",", "")) if m else 0

def crawl_listing(path, per_page=60):
    """Fetch every page of a Living Torah listing. Returns list of cards."""
    first = get(path)
    if first is None:
        return None
    cards = parse_cards(first)
    total = results_total(first)
    pages = (total + per_page - 1) // per_page if total else 1
    for n in range(2, pages + 1):
        p = get(f"{path}/page/{n}")
        cards += parse_cards(p)
    seen, uniq = set(), []
    for c in cards:
        if c["aid"] not in seen:
            seen.add(c["aid"]); uniq.append(c)
    return uniq

HEB_MONTHS = {"Nissan": 1, "Iyar": 2, "Sivan": 3, "Tammuz": 4, "Av": 5, "Elul": 6, "Tishrei": 7,
              "Cheshvan": 8, "Kislev": 9, "Tevet": 10, "Shevat": 11, "Adar": 12, "Adar I": 12, "Adar II": 13}
EN_MONTHS = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

def parse_event_date(text):
    """'26 Adar II, 5749 • Apr. 2, 1989' -> {hDay, hMonth, hMonthName, hYear, gregorian}"""
    if not text:
        return None
    out = {}
    m = re.search(r"(\d{1,2})\s+([A-Za-z' ]+?),\s*(\d{4})", text)
    if m and m.group(2).strip() in HEB_MONTHS:
        out.update(hDay=int(m.group(1)), hMonthName=m.group(2).strip(), hMonth=HEB_MONTHS[m.group(2).strip()], hYear=int(m.group(3)))
    g = re.search(r"([A-Z][a-z]{2})[a-z]*\.?\s+(\d{1,2}),\s*(\d{4})", text.split("•")[-1])
    if g and g.group(1) in EN_MONTHS:
        out["gregorian"] = "%04d-%02d-%02d" % (int(g.group(3)), EN_MONTHS[g.group(1)], int(g.group(2)))
    return out or None

def fetch_meta(aid):
    t = get(f"/api/content/{aid}/metadata")
    if not t:
        return aid, None
    page = re.search(r'"page":(\{.*?\}),"time"', t)
    kw = re.search(r"'keywords':\s*'([^']*)'", t)
    d = {}
    if page:
        try:
            p = json.loads(page.group(1))
            levels = [p.get("contentLevel%d" % i) for i in range(1, 15) if p.get("contentLevel%d" % i)]
            d["published"] = p.get("publicationDate")
            d["comments"] = p.get("numberOfComments")
            d["disc"] = next((int(x.split()[-1]) for x in levels if re.fullmatch(r"Disc \d+", x)), None)
            d["program"] = next((int(x.split()[-1]) for x in levels if re.fullmatch(r"Program \d+", x)), None)
            d["path"] = levels
        except Exception:
            pass
    if kw:
        d["keywords"] = [int(k) for k in re.findall(r"k(\d+)", kw.group(1))]
    return aid, d

def fetch_media(aid):
    t = get(f"/multimedia/mediaplayer/flash_media_player_content.xml.asp?what=json&aid={aid}")
    m = re.search(r"Co\.MediaInfo\[['\"][^'\"]+['\"]\]\s*=\s*(\{[\s\S]*\})\s*;?\s*$", t or "")
    if not m:
        return aid, None
    try:
        raw = json.loads(m.group(1))
    except Exception:
        return aid, None
    md = raw.get("Media") or {}
    return aid, {
        "length": md.get("Length"),
        "type": md.get("Type"),
        "poster": (md.get("Preview") or {}).get("ImagePath"),
        "allowEmbed": md.get("AllowEmbed", True) is not False,
        "hasStream": bool(md.get("AdaptableStreamingUrl") or md.get("BitRates")),
    }

def pmap(fn, items, workers, label):
    out, done = {}, 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for k, v in ex.map(fn, items):
            out[k] = v
            done += 1
            if done % 200 == 0 or done == len(items):
                print(f"  {label}: {done}/{len(items)}", flush=True)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "public", "data"))
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--skip-media", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()

    # 1. Catalog
    print("catalog...", flush=True)
    cards = crawl_listing(f"{LT}/aid/42100/jewish/Living-Torah.htm")
    videos = {}
    for c in cards:
        c["event"] = parse_event_date(c.pop("dateText"))
        videos[c["aid"]] = c
    print(f"  {len(videos)} videos", flush=True)

    # 2. Dates index
    print("dates...", flush=True)
    idx = get(f"{LT}/index/true/indextype/date") or ""
    date_links = sorted(set(re.findall(r"month=(\d+)&(?:amp;)?day=(\d+)&(?:amp;)?year=(\d+)", idx) +
                            re.findall(r"default_cdo/month/(\d+)/day/(\d+)/year/(\d+)", idx)), key=lambda x: (int(x[2]), int(x[0]), int(x[1])))
    def date_job(mdy):
        m, d, y = mdy
        cs = crawl_listing(f"{LT}/month/{m}/day/{d}/year/{y}")
        return mdy, cs
    date_res = pmap(date_job, date_links, a.workers, "dates")
    dates = {}
    for (m, d, y), cs in date_res.items():
        key = f"{int(m)}-{int(d)}"
        aids = [c["aid"] for c in (cs or [])]
        for c in cs or []:
            ev = parse_event_date(c.pop("dateText", None))
            videos.setdefault(c["aid"], {**c, "event": ev})
        dates.setdefault(key, []).append({"hYear": int(y), "aids": aids})
    for k in dates:
        dates[k].sort(key=lambda e: e["hYear"])

    # 3. Topic index
    print("topics...", flush=True)
    tidx = get(f"{LT}/index/true/indextype/topic") or ""
    topic_names = {}
    for tid, name in re.findall(r"topicid[=/](\d+)\"[^>]*>([^<]+)<", tidx):
        topic_names.setdefault(int(tid), clean(name))
    def topic_job(tid):
        cs = crawl_listing(f"{LT}/topicid/{tid}")
        return tid, cs
    topic_res = pmap(topic_job, list(topic_names), a.workers, "topics")
    topics = {}
    for tid, cs in topic_res.items():
        for c in cs or []:
            ev = parse_event_date(c.pop("dateText", None))
            videos.setdefault(c["aid"], {**c, "event": ev})
        topics[tid] = {"name": topic_names[tid], "aids": [c["aid"] for c in (cs or [])]}

    # 4. Per-video metadata
    print("metadata...", flush=True)
    metas = pmap(fetch_meta, list(videos), a.workers, "metadata")
    for aid, d in metas.items():
        if d:
            videos[aid].update(d)

    # 5. Per-video media info
    if not a.skip_media:
        print("media...", flush=True)
        media = pmap(fetch_media, list(videos), a.workers, "media")
        for aid, d in media.items():
            if d:
                videos[aid].update(d)

    # topic membership on each video
    for tid, t in topics.items():
        for aid in t["aids"]:
            if aid in videos:
                videos[aid].setdefault("topics", []).append(tid)

    def dump(name, obj):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  wrote {name} ({os.path.getsize(os.path.join(a.out, name))//1024} KB)")

    dump("videos.json", {str(k): v for k, v in sorted(videos.items())})
    dump("topics.json", {str(k): v for k, v in sorted(topics.items())})
    dump("dates.json", dict(sorted(dates.items(), key=lambda kv: tuple(map(int, kv[0].split("-"))))))
    dump("build.json", {
        "builtAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0),
        "counts": {"videos": len(videos), "topics": len(topics), "dateKeys": len(dates), "dateEntries": len(date_links)},
        "source": "https://www.chabad.org/therebbe/livingtorah",
    })

if __name__ == "__main__":
    main()
