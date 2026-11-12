# Rebbe Videos widget for Chabad Display: implementation spec

This document is for the Chabad Display coder agent. It describes a widget that plays a continuous, timely stream of the Lubavitcher Rebbe's videos from Chabad.org on a display, picked by today's Hebrew date, this week's parsha and upcoming holidays and Chabad special days. Everything hard (finding the videos, mapping them to dates, parshiyos and holidays) is already done and lives in a prebuilt index. The widget only reads that index, picks videos, looks up each video's stream URL at play time, and plays it with hls.js.

Nothing here needs a Chabad.org login or API key. The index was built from public Chabad.org pages and endpoints, and the stream lookup is the same public endpoint Chabad.org's own embed player uses.


## 1. What the user sees and chooses

The widget is a full-bleed video player that keeps playing one video after another. In the widget settings the user picks a **mode**:

| Mode | Label in settings | What plays |
|---|---|---|
| `timely` (default) | "What's timely" | Today's matches first (videos from this Hebrew date in any year, then current or upcoming holidays and special days, then this week's parsha), and when those run out, anything. |
| `parsha` | "This week's parsha" | Videos tagged with this week's parsha, then videos that originally aired the week of this parsha. |
| `holiday` | "Holidays & special days" | Videos for whatever holiday or Chabad date is current or coming up (Chanukah, Yud-Tes Kislev, Yud Shevat, Gimmel Tammuz, etc.). If nothing is coming up, falls back to `timely`. |
| `onthisday` | "On this day" | Videos recorded on today's Hebrew date (any year), widening to the coming days if today has nothing. |
| `livingtorah` | "Living Torah" | Any Living Torah episode segment, shuffled. |
| `random` | "Anything" | Any of the ~3,480 videos, shuffled. |

Optional settings worth exposing (all cheap given the index):

- **Shuffle** on/off inside each tier (default on). Off means oldest-to-newest by event date within a tier.
- **Segment type filter** for Living Torah videos: `Talk` (the Rebbe speaking), `Eye to Eye`, `Timeless Moment`, `My Encounter` (first-person stories), `Soul Strings` (nigunim). Field `sec` in the catalog.
- **Max video length** (e.g. skip anything over 15 minutes for lobby screens). Field `len` is `"m:ss"` or `"h:mm:ss"`.
- **Show caption overlay**: title plus a small "why it's playing" line (the tier label, e.g. "On this day, 19 Kislev 5747" or "Chanukah"), and the credit line "Video: JEM / Chabad.org".
- **Sound**: muted by default (browsers block unmuted autoplay); the TV app can allow sound.
- **Israel schedule** toggle (parsha schedule differs from the diaspora some weeks). Default diaspora.


## 2. The data

Hosted (CORS open, cached 1h) at `https://chabad-player.shneur.workers.dev/data/<file>` and committed in GitHub repo `ShneurNovack/chabad-player` under `public/data/`.

**Recommended:** copy these JSON files into the Chabad Display repo (or its R2/KV) instead of fetching them from that URL. The chabad-player Worker lives on Zami's personal Cloudflare account, and Chabad Display should not depend on it. Re-copy whenever the index is rebuilt (section 7).

| File | Size | What it is |
|---|---|---|
| `catalog.json` | ~1.2 MB (≈300 KB gzipped) | Every unique, playable Rebbe video. **The widget's main file.** |
| `calendar.json` | 7 KB | Definitions: the 54 parshiyos and ~37 holidays / special days with their Hebrew date windows. |
| `parsha.json` | 29 KB | Parsha index 0-53 → video ids. |
| `special.json` | 26 KB | Special day id → video ids. |
| `onthisday.json` | 67 KB | `"hMonth-hDay"` → videos recorded on that Hebrew date. |
| `pools.json` | 94 KB | Video ids per mode (`all`, `livingtorah`, `parsha`, `holiday`, `onthisday`). |
| `build.json` | tiny | When the index was built and counts. |
| `videos.json` | ~5 MB | Full raw index (descriptions, keywords, disc/program, paths). Not needed by the widget; for debugging and rebuilding. |

**Hebrew month numbering everywhere is Hebcal's:** Nisan=1, Iyar=2, Sivan=3, Tammuz=4, Av=5, Elul=6, Tishrei=7, Cheshvan=8, Kislev=9, Teves=10, Shevat=11, Adar (or Adar I in a leap year)=12, Adar II=13. This matches `@hebcal/core`'s `HDate.getMonth()` and `months.*` constants exactly.

### catalog.json

Keyed by Chabad.org article id (string):

```json
"4192713": {
  "t": "The Story of Rosh Chodesh Kislev 5738 (1977)",
  "len": "12:49",
  "img": "https://w2.chabad.org/media/images/1069/yoOi10699618.jpg",
  "sec": "Inspiration",
  "src": "hub",
  "pub": "2018-11-09",
  "ev": null,
  "d": "The inside story of the horror and pain felt by Chasidim after the Rebbe's heart attack ..."
}
```

- `t` title, `len` duration, `img` poster image, `d` description (first 200 chars).
- `sec` segment/section: for Living Torah videos one of `Talk`, `Eye to Eye`, `Timeless Moment`, `My Encounter`, `Soul Strings`; for other videos the Chabad.org category name (e.g. `Wisdom from the Rebbe`, `Selected Talks`, `Short Stories of the Rebbe`).
- `src` `livingtorah` or `hub` (TheRebbe.org Video hub categories).
- `pub` date Chabad.org published it. `ev` `[hYear, hMonth, hDay]` when the video's footage is from a known Hebrew date (e.g. `[5743, 11, 10]` = 10 Shevat 5743), else null.

### calendar.json

```json
{
  "parshiyot": [ { "index": 5, "hebcal": "Toldot", "name": "Toldot", "kid": 904, "book": 0 }, ... 54 entries ],
  "specialDays": [
    { "id": "chanukah", "name": "Chanukah", "month": 9, "day": 25, "to": 2, "toMonth": 10, "lead": 10, "kids": [134, 8669, 1367, 2314, 13214] },
    { "id": "purim", "name": "Purim", "month": 12, "day": 14, "to": 15, "adar": "last", "lead": 7, "kids": [...] },
    { "id": "hakhel", "name": "Hakhel year", "hakhelYearOnly": true, "kids": [14375] },
    ...
  ]
}
```

- `parshiyot[i].hebcal` is exactly Hebcal's English parsha name (verified against `@hebcal/core`'s `parshiot` list, all 54 match), and `index` = Hebcal's 1-based `num` minus 1.
- A special day's window runs from `month/day` to `toMonth/to` (`toMonth` defaults to `month`, `to` defaults to `day`). `lead` = how many days **before** the window starts that it begins showing (so Chanukah videos start 10 days early, Yud Shevat 7 days early).
- `adar`: `"last"` means Adar II in a leap year and Adar in a regular year (Purim, 7 Adar, 27 Adar, the month of Adar). `"first"` means Adar I and only exists in leap years (Purim Katan). No `adar` field means the month number is used as-is.
- `hakhelYearOnly`: active for the whole Hebrew year when `hYear % 7 === 1` (5783, 5790, ...). 5787 is not a Hakhel year.
- `kids` are the Chabad.org keyword ids used to build the lists; the widget doesn't need them.

### parsha.json and special.json

```json
"5": { "hebcal": "Toldot", "name": "Toldot", "kid": 904, "aids": [], "aired": [96319, 219309, ...75 ids] }
"chanukah": { "name": "Chanukah", "aids": [235109, 335495, ...53 ids], "aired": [96325, ...157 ids] }
```

Two tiers per entry, always play `aids` before `aired`:

- `aids`: videos Chabad.org explicitly tagged with that parsha or holiday. Highest confidence.
- `aired`: videos that **originally aired** that parsha week / in the days around that holiday. Living Torah was a weekly program (2003-2020) produced for the calendar, so this is a strong "this is when it was meant to be watched" signal, but an individual segment isn't necessarily *about* the parsha. Present it as "Aired the week of Parshas Toldos", not "About Parshas Toldos".

Coverage: every parsha has 29-118 videos combined, except Vezos Habracha (0; it's read on Simchas Torah, so use the `simchas-torah` special day instead). Tagged-only parsha coverage is thin (22 parshiyos have no tagged videos), which is why the `aired` tier exists.

### onthisday.json

```json
"9-19": [ { "aid": 3747190, "hYear": 5716 }, { "aid": 4582974, "hYear": 5718 }, ... 118 entries ]
```

Key is `"hMonth-hDay"`. The value is every video recorded on that Hebrew date, sorted by year. 286 of the year's dates have at least one video (median 4; big days like 19 Kislev, 10 Shevat and 12 Tammuz have 100+). For Adar in a leap year, check both `12-D` and `13-D` for Adar II dates, and `12-D` for Adar I (Chabad.org files Adar I footage under 12).


## 3. Hebrew calendar logic (use `@hebcal/core`)

```js
import { HDate, months, getSedra } from '@hebcal/core';   // npm i @hebcal/core  (tested with 6.16)

function hebrewContext(date = new Date(), { il = false } = {}) {
  const hd = new HDate(date);                      // NOTE: see "day boundary" below
  const sedra = getSedra(hd.getFullYear(), il);
  const s = sedra.lookup(hd);                      // the parsha read on the coming Shabbos
  // s = { parsha: ['Toldot'], chag: false, num: 6 }      num is 1-based, can be an array for doubled parshiyos
  // on a holiday Shabbos: { parsha: ['Pesach Shabbat Chol ha-Moed'], chag: true, num: 0 } -> no parsha tier that week
  const nums = s.chag ? [] : [].concat(s.num).filter(Boolean);
  return {
    hd, hYear: hd.getFullYear(), hMonth: hd.getMonth(), hDay: hd.getDate(),
    leap: HDate.isLeapYear(hd.getFullYear()),
    parshaIndexes: nums.map(n => n - 1),          // indexes into parsha.json / calendar.parshiyot
    hakhel: hd.getFullYear() % 7 === 1,
  };
}
```

**Day boundary.** The Hebrew date changes at nightfall, not midnight. If the display has a location (it should, for zmanim widgets), use Hebcal's `Zmanim` to get tonight's `tzeit()` and treat times after it as the next Hebrew day (`hd.next()`). Without a location, switching at midnight is acceptable.

**Is a special day active?** Build real dates for this Hebrew year and compare:

```js
function resolveMonth(sd, month, hYear) {
  if (month !== 12) return month;
  const leap = HDate.isLeapYear(hYear);
  if (sd.adar === 'last') return leap ? months.ADAR_II : months.ADAR_I;   // Purim etc.
  if (sd.adar === 'first') return leap ? months.ADAR_I : null;           // Purim Katan: leap years only
  return months.ADAR_I;
}

// returns null, or { daysUntil } (0 = inside the window today)
function specialStatus(sd, ctx) {
  if (sd.hakhelYearOnly) return ctx.hakhel ? { daysUntil: 0 } : null;
  for (const y of [ctx.hYear, ctx.hYear + 1]) {          // look at this year's and next year's occurrence
    const m1 = resolveMonth(sd, sd.month, y); if (!m1) continue;
    const start = new HDate(sd.day, m1, y);
    const m2 = resolveMonth(sd, sd.toMonth ?? sd.month, y);
    let end = new HDate(sd.to ?? sd.day, m2, y);
    if (end.abs() < start.abs()) end = new HDate(sd.to ?? sd.day, m2, y + 1); // window crosses into the next Hebrew year
    const today = ctx.hd.abs();
    if (today >= start.abs() && today <= end.abs()) return { daysUntil: 0 };
    const until = start.abs() - today;
    if (until > 0 && until <= (sd.lead ?? 0)) return { daysUntil: until };
  }
  return null;
}
```

Notes: Hebrew years start in Tishrei, so a window like Rosh Hashanah (1 Tishrei) with a 10-day lead seen from late Elul is "next year's" occurrence; the loop over `[hYear, hYear+1]` handles that. Chanukah is defined as 25 Kislev to 2 Teves; in years when Kislev has 29 days it really ends 3 Teves, so either extend `end` by one day when `HDate.daysInMonth(months.KISLEV, y) === 29`, or ignore it (videos just stop a day early).


## 4. Building the playlist

```text
tiers = []   // each tier = { label, ids[] }, played in order

timely mode:
  1. On this day          onthisday[`${hMonth}-${hDay}`]  (label: "On this day")
  2. Active special days  for each active special day, nearest first: special[id].aids   (label: its name, e.g. "Chanukah" or "Yud Shevat in 3 days")
  3. This week's parsha   parsha[i].aids for each i in parshaIndexes                  (label: "Parshas Toldos")
  4. Aired around         special[id].aired for each active special day               (label: "Aired around Chanukah")
  5. Aired this week      parsha[i].aired                                              (label: "Aired the week of Toldos")
  6. Anything             pools.all                                                    (label: "")

parsha mode:     tiers 3, 5, then 6
holiday mode:    tiers 2, 4; if both are empty fall back to timely
onthisday mode:  tier 1, then the same lookup for the next 1..7 Hebrew days ("Coming up: 19 Kislev"), then 6
livingtorah:     pools.livingtorah
random:          pools.all
```

Then:

1. Apply the user's filters (segment type, max length) to every tier using `catalog`.
2. Drop ids not in `catalog` (the catalog only holds playable, embeddable, de-duplicated videos; the other files may reference ids that were filtered out).
3. Shuffle within each tier (or sort by `ev`/`pub` if shuffle is off), and de-duplicate across tiers (first tier wins).
4. **Avoid repeats across days:** keep a per-display history (the last ~300 played ids, in the display's local storage or the backend). Move recently played ids to the end of their tier rather than removing them, so small tiers still play.
5. Rebuild the playlist when the Hebrew day changes, and whenever settings change. Otherwise keep playing down the list and wrap around.

A reference implementation of exactly this logic is `scripts/preview.py` in the repo (Python, using pyluach instead of Hebcal). Run `python3 scripts/preview.py 2026-12-08 --mode holiday` to see what any date should produce.


## 5. Playing a video

Each catalog id is a Chabad.org article id. To play it:

1. **Look up the stream** (server-side; Chabad.org's endpoint has no CORS headers, so the browser can't call it directly):

   ```
   GET https://www.chabad.org/multimedia/mediaplayer/flash_media_player_content.xml.asp?what=json&aid={aid}
   User-Agent: ChabadDisplay/1.0 (+https://github.com/ShneurNovack)     <- an honest UA; a spoofed browser UA gets Cloudflare-challenged (403)
   ```

   The response is JavaScript, not JSON: `Co.MediaInfo['item4192713'] = { ... };`. Strip the wrapper with
   `/Co\.MediaInfo\[['"][^'"]+['"]\]\s*=\s*(\{[\s\S]*\})\s*;?\s*$/` and `JSON.parse` group 1. The fields you need:

   ```json
   { "Title": "...", "Media": { "Type": "video", "Length": "12:49", "AllowEmbed": true,
       "Preview": { "ImagePath": "https://w2.chabad.org/media/images/....jpg" },
       "AdaptableStreamingUrl": "https://hls-vod-cdn.chabad.org/vod/_definst_/smil:.../playlist.m3u8?v=..." } }
   ```

   Put this behind a small Chabad Display API route, e.g. `GET /api/rebbe-videos/media?aid=4192713` → `{ title, length, poster, hls, allowEmbed }`, cached for an hour (the URLs are stable). A working version of this exact route is `src/worker.js` in `ShneurNovack/chabad-player` (`/api/media`), about 40 lines, which can be copied as-is.

2. **Play the HLS URL** with hls.js (`Hls.isSupported()`), or natively where the browser supports HLS (Safari, many TV webviews). The CDN (`hls-vod-cdn.chabad.org`) sends `Access-Control-Allow-Origin: *` and needs no token or referer, so the display loads it directly. Use `capLevelToPlayerSize: true` so small widgets don't pull the 1200k rendition. Renditions are 250k (360p), 600k (480p), 1200k (480p) and a 64k audio-only one.

3. **Preload** the next video's media lookup while the current one plays, so transitions are instant.

4. **On any error** (lookup fails, `AllowEmbed` false, HLS fatal error), skip to the next video and don't retry that id for the rest of the day.

5. Autoplay requires `muted` in browsers. Use `playsinline`. These are 4:3 videos (480×360 / 640×480), so letterbox them (`object-fit: contain` on black) or offer a "fill" option that crops.

A complete working custom player (hls.js, quality menu, error handling) is `public/player.js` in the chabad-player repo, live at https://chabad-player.shneur.workers.dev.


## 6. Ground rules

- **Only play videos Chabad.org marks embeddable** (`AllowEmbed`). The catalog is pre-filtered, but check again at play time; it can change.
- **Credit the source:** show "Video: JEM / Chabad.org" in the caption overlay, at least while the title shows.
- **Be gentle with Chabad.org:** one media lookup per video play, cached; never crawl Chabad.org from the displays. All crawling happens in the index build (section 7), roughly 10,000 small requests once per refresh.
- Always send the honest User-Agent described above.


## 7. Refreshing the index

New Living Torah episodes stopped in 2020, so the index is close to static. Rebuild it monthly or quarterly to pick up new hub videos and re-check what's embeddable:

```bash
pip install pyluach
python3 scripts/build_index.py     # Living Torah catalog, date index, topic index, metadata, media check   (~10 min)
python3 scripts/build_hub.py       # adds the other TheRebbe.org Video hub categories                         (~5 min)
python3 scripts/build_calendar.py  # parsha / special-day / on-this-day lookups, catalog.json, pools.json   (seconds)
python3 scripts/preview.py         # sanity check today's playlist
```

Then commit `public/data/` and re-copy the files into Chabad Display.

How the sources fit together, for whoever maintains this:

- **Living Torah catalog:** `/therebbe/livingtorah/default_cdo/aid/42100/jewish/Living-Torah.htm/page/N` (60 cards per page, 55 pages). Each card has title, description, thumbnail, segment type and the event date in Hebrew and English.
- **Date index:** `/therebbe/livingtorah/default_cdo/index/true/indextype/date` lists 816 dates → `/therebbe/livingtorah/default_cdo/month/{m}/day/{d}/year/{y}`.
- **Topic index:** `/therebbe/livingtorah/default_cdo/index/true/indextype/topic` lists 1,239 topics → `/therebbe/livingtorah/default_cdo/topicid/{id}`. Topic ids are the same as Chabad.org keyword ids.
- **Per-video metadata:** `https://www.chabad.org/api/content/{aid}/metadata` (public; publication date, Disc/Program, keyword ids). Keyword `1242` = the Rebbe.
- **Hub categories:** `https://www.chabad.org/webservices/ContentLoader/Get_Article?aid={folder}&PageSize=40&page=N` (public listing helper; `x-total-records` header; children listed in the leading `LIST_A{id}` comment). Category folder ids are in `scripts/build_hub.py`.
- **Parsha keyword ids:** Bereishis 80, Noach 81, Lech Lecha 82, Vayeira 83, Chayei Sarah 550, Toldos 904, then 1076-1131 in order (with Vayigash at 1099). The full table is in `scripts/build_calendar.py` and `calendar.json`.
- Old `/therebbe/livingtorah/default.aspx?...` URLs 301-redirect to the `default_cdo/...` forms; follow redirects.


## 8. Test vectors

Use these to check the JS port (diaspora schedule):

| Gregorian date | Hebrew date | Parsha index (Hebcal num−1) | Should include |
|---|---|---|---|
| 2026-11-11 | 1 Kislev 5787 | 5 (Toldot) | On this day: Kinus Hashluchim 1987 clips. Special: Rosh Chodesh Kislev (the 1977 heart attack and recovery videos, e.g. aid 4192713). Parsha tier: Toldos `aired` only (no tagged videos). |
| 2026-12-08 | 28 Kislev 5787 | 9 (Miketz) | Special: Chanukah (e.g. "Listen to the Lights" 3877926, "The Chanukah Battle Continues" 603066). |
| 2027-01-17 | 9 Shevat 5787 | 15 (Beshalach) | On this day: 9 Shevat clips. Special: Yud Shevat "in 1 day". |
| 2026-10-03 | 22 Tishrei 5787 | none (`chag: true`) | Special: Shemini Atzeres & Simchas Torah. No parsha tier. |
| 2027-03-23 | 14 Adar II 5787 (leap year) | — | Special: Purim (Adar II in a leap year), not Purim Katan. |
