# Chabad Player (proof of concept)

Plays any Chabad.org video or audio in our own player instead of Chabad's iframe embed.

## How it works

Chabad's embed (`embed.js.asp?aid=…`) drops an iframe whose player reads its metadata from
`https://www.chabad.org/multimedia/mediaplayer/flash_media_player_content.xml.asp?what=json&aid=<id>`.
That endpoint returns JS (`Co.MediaInfo['item<id>'] = {…}`) with no CORS headers. Inside it,
`Media.AdaptableStreamingUrl` is a public HLS playlist on `hls-vod-cdn.chabad.org`
(`access-control-allow-origin: *`, no token).

This project:

- **`GET /api/media?aid=<id>`** (or `?iid=<fileId>`, add `&raw=1` for the untouched upstream object):
  the Worker fetches Chabad's metadata, strips the JS wrapper, and returns clean JSON with CORS on
  (title, publisher, length, poster, `hls`, bitrates, captions, allowEmbed). Cached 5 min.
- **`/`**: demo page. Paste an ID or a chabad.org link and it plays in our player (hls.js, custom controls:
  play/pause, seek, speed, quality, mute, fullscreen, keyboard shortcuts).
- **`/embed?aid=<id>`**: bare player page for iframes. Options: `&autoplay=1` (muted), `&start=<seconds>`.

If `/api/media` is unreachable, the page falls back to loading Chabad's metadata script directly.

## Notes

- Items with `AllowEmbed: false` are refused.
- Each video links back to its Chabad.org article.

## Deploy

GitHub repo connected to Cloudflare Workers Builds; pushes to `main` deploy automatically (`npx wrangler deploy`).
Local: `npm i && npx wrangler dev`.
