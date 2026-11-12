#!/usr/bin/env python3
"""
Stage 2: add every video from TheRebbe.org Video hub (aid 1743851) categories, other than
Living Torah (already indexed by build_index.py), to public/data/videos.json.

Walks folders with the public listing helper:
  GET https://www.chabad.org/webservices/ContentLoader/Get_Article?aid={folder}&PageSize=40&page=N
  (x-total-records header = child count; the first HTML comment lists child ids as LIST_A{aid},...)
A child is a video if the media endpoint returns Media; otherwise it's treated as a folder and walked.

Each video gets: title, description, thumb, length, published, keywords (Chabad keyword ids,
the same ids as Living Torah topic ids), category (top-level hub row), rebbe (has keyword 1242).
"""
import argparse, concurrent.futures as cf, html, json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from build_index import get, fetch_meta, fetch_media, UA, BASE, clean

HUB = 1743851
SKIP = {42100}  # Living Torah: indexed separately
# The hub's category rows ("View all N" links on /multimedia/video_cdo/aid/1743851). Get_Article on the hub
# itself returns the videos it displays, not these folders, so they are listed explicitly.
CATEGORIES = {
    132864: "Inspiration", 523698: "My Encounter", 528155: "The Early Years", 2133920: "Wisdom from the Rebbe",
    629825: "The Rebbetzin", 132922: "Selected Talks", 427553: "High Holidays with the Rebbe", 132863: "Tributes",
    2143121: "Personal Reflections", 2143216: "The Farbrengen Series", 2144357: "Inside Chabad-Lubavitch",
    2261384: "Farbreng: The Chassidic Roundtable", 2872323: "Jewish Holidays", 6528188: "Short Stories of the Rebbe",
}

def list_children(folder):
    ids, page, total = [], 1, None
    cards = {}
    while True:
        url = f"{BASE}/webservices/ContentLoader/Get_Article?aid={folder}&PageSize=40&page={page}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                total = int(r.headers.get("x-total-records") or 0)
                body = html.unescape(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            print("list fail", folder, e, file=sys.stderr)
            break
        tag = re.search(r'Resources\.Tags "([^"]*)"', body)
        got = [int(x) for x in re.findall(r"LIST_A(\d+)", tag.group(1))] if tag else []
        # card details when the listing renders video cards
        for c in re.findall(r'<article class="vs-video-card[^"]*">(.*?)</article>', body, re.S):
            m = re.search(r"_cdo/aid/(\d+)/jewish/", c)
            if not m:
                continue
            g = lambda cls: clean((re.search(r'class="vs-video-card__%s[^"]*"[^>]*>(.*?)</div>' % cls, c, re.S) or [None, ""])[1])
            img = re.search(r'<img[^>]+src="([^"?]+)', c)
            cards[int(m.group(1))] = {"title": g("title"), "description": g("description"),
                                      "thumb": img.group(1) if img else None, "length": g("timestamp") or None}
        ids += [i for i in got if i not in ids]
        if not got or len(ids) >= total or page > 60:
            break
        page += 1
    return ids, cards

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "public", "data"))
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()
    vpath = os.path.join(a.out, "videos.json")
    videos = json.load(open(vpath, encoding="utf-8"))

    rows = list(CATEGORIES)
    found = {}  # aid -> {category, card}
    def walk(folder, category, depth=0):
        kids, cards = list_children(folder)
        with cf.ThreadPoolExecutor(a.workers) as ex:
            media = dict(ex.map(fetch_media, kids))
        sub = []
        for k in kids:
            if (media.get(k) or {}).get("hasStream"):
                found.setdefault(k, {"category": category, **cards.get(k, {}), **media[k]})
            elif depth < 4 and k not in SKIP:
                sub.append(k)
        for s in sub:
            walk(s, category, depth + 1)

    for row in rows:
        if row in SKIP:
            continue
        name = CATEGORIES[row]
        before = len(found)
        walk(row, name)
        print(f"  {name} ({row}): +{len(found) - before}", flush=True)

    new = [k for k in found if str(k) not in videos]
    print("new videos:", len(new), "metadata...", flush=True)
    with cf.ThreadPoolExecutor(a.workers) as ex:
        metas = dict(ex.map(fetch_meta, list(found)))
    added = 0
    for k, info in found.items():
        key = str(k)
        meta = metas.get(k) or {}
        if key in videos:
            videos[key].setdefault("categories", [])
            if info["category"] not in videos[key]["categories"]:
                videos[key]["categories"].append(info["category"])
            continue
        title = info.get("title") or (meta.get("path") or [""])[-1]
        videos[key] = {"aid": k, "title": title, "description": info.get("description", ""),
                       "thumb": info.get("thumb") or info.get("poster"), "source": "hub",
                       "categories": [info["category"]], **{x: info.get(x) for x in ("length", "type", "poster", "allowEmbed", "hasStream")},
                       **meta}
        added += 1
    for v in videos.values():
        v.setdefault("source", "livingtorah")
        v["rebbe"] = 1242 in (v.get("keywords") or []) or v["source"] == "livingtorah"
    json.dump(videos, open(vpath, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("added", added, "total", len(videos))

if __name__ == "__main__":
    main()
