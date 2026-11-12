// Chabad Player POC
// /api/media?aid=<articleId>  (or ?iid=<fileId>)
// Wraps Chabad.org's player metadata endpoint, which returns JS
// (Co.MediaInfo['item123'] = {...};) with no CORS, and returns clean JSON.

const SOURCE = "https://www.chabad.org/multimedia/mediaplayer/flash_media_player_content.xml.asp?what=json";

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
};

function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...CORS, ...extra },
  });
}

export function normalize(raw, aid, iid) {
  const m = raw.Media || {};
  const bitrates = (m.BitRates || []).map((b) => ({
    bitrate: Number(b.BitRate),
    width: Number(b.Width),
    height: Number(b.Height),
    mediaId: b.MediaId,
    url: b.FileName,
  }));
  const hls =
    m.AdaptableStreamingUrl ||
    (bitrates.find((b) => /\.m3u8/.test(b.url || "")) || {}).url ||
    null;
  const progressive = bitrates.filter((b) => b.url && !/\.m3u8/.test(b.url));
  return {
    aid: aid || null,
    iid: iid || null,
    title: raw.Title || "",
    subtitle: raw.SubTitle || "",
    publisher: raw.Publisher || "",
    type: m.Type || (raw.Media ? "video" : null),
    isLive: !!(raw.IsLive || m.IsLive),
    length: m.Length || null,
    width: Number(m.Width) || null,
    height: Number(m.Height) || null,
    poster: (m.Preview && m.Preview.ImagePath) || null,
    hls,
    progressive,
    bitrates,
    captions: m.Captions || [],
    allowEmbed: m.AllowEmbed !== false,
    allowDownload: !!m.AllowDownload,
    articleUrl: aid ? `https://www.chabad.org/${aid}` : null,
  };
}

async function getMedia(url) {
  const aid = (url.searchParams.get("aid") || "").trim();
  const iid = (url.searchParams.get("iid") || "").trim();
  if (!/^\d{1,10}$/.test(aid) && !/^\d{1,10}$/.test(iid)) {
    return json({ error: "Pass ?aid=<article id> or ?iid=<file id> (digits only)" }, 400);
  }

  const src = SOURCE + (aid ? `&aid=${aid}` : `&iid=${iid}`);
  const res = await fetch(src, {
    headers: { "user-agent": "Mozilla/5.0 (chabad-player POC)", accept: "*/*" },
    cf: { cacheTtl: 300, cacheEverything: true },
  });
  if (!res.ok) return json({ error: `Upstream returned ${res.status}` }, 502);

  const text = await res.text();
  const match = text.match(/Co\.MediaInfo\[['"]([^'"]+)['"]\]\s*=\s*(\{[\s\S]*\})\s*;?\s*$/);
  if (!match) return json({ error: "No media found for that id" }, 404);

  let raw;
  try {
    raw = JSON.parse(match[2]);
  } catch (e) {
    return json({ error: "Could not parse upstream metadata" }, 502);
  }
  if (!raw.Media) return json({ error: "That article has no media attached" }, 404);

  const data = normalize(raw, aid, iid);
  if (url.searchParams.get("raw") === "1") data.raw = raw;
  return json(data, 200, { "cache-control": "public, max-age=300" });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });

    if (url.pathname === "/api/media") {
      try {
        return await getMedia(url);
      } catch (e) {
        return json({ error: "Fetch failed: " + e.message }, 502);
      }
    }
    if (url.pathname.startsWith("/api/")) return json({ error: "Not found" }, 404);

    return env.ASSETS.fetch(request);
  },
};
