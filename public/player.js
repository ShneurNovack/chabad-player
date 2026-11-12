/* Chabad Player POC: our own HLS player for Chabad.org media.
   loadMedia(id) -> normalized metadata; mountPlayer(el, media, opts) -> custom player. */
(function () {
  const SOURCE = "https://www.chabad.org/multimedia/mediaplayer/flash_media_player_content.xml.asp?what=json";

  // Accepts "4192713", a chabad.org URL with /aid/123 or ?aid=123, or chabad.org/123
  function parseId(input) {
    const s = String(input || "").trim();
    if (/^\d{3,10}$/.test(s)) return s;
    const m =
      s.match(/[?&]aid=(\d+)/i) ||
      s.match(/\/aid\/(\d+)/i) ||
      s.match(/chabad\.org\/(\d{3,10})(?:[/?#]|$)/i);
    return m ? m[1] : null;
  }

  function normalize(raw, aid) {
    const m = raw.Media || {};
    const bitrates = (m.BitRates || []).map((b) => ({
      bitrate: Number(b.BitRate), width: Number(b.Width), height: Number(b.Height), url: b.FileName,
    }));
    return {
      aid, title: raw.Title || "", subtitle: raw.SubTitle || "", publisher: raw.Publisher || "",
      type: m.Type || "video", length: m.Length || null,
      width: Number(m.Width) || null, height: Number(m.Height) || null,
      poster: (m.Preview && m.Preview.ImagePath) || null,
      hls: m.AdaptableStreamingUrl || (bitrates.find((b) => /\.m3u8/.test(b.url || "")) || {}).url || null,
      progressive: bitrates.filter((b) => b.url && !/\.m3u8/.test(b.url)),
      bitrates, captions: m.Captions || [], allowEmbed: m.AllowEmbed !== false,
      articleUrl: "https://www.chabad.org/" + aid,
    };
  }

  // Fallback when our API is unreachable: Chabad's endpoint is a script that sets a global.
  function loadViaScript(aid) {
    return new Promise((resolve, reject) => {
      const tag = document.createElement("script");
      tag.src = SOURCE + "&aid=" + aid;
      tag.onload = () => {
        const raw = window.Co && Co.MediaInfo && Co.MediaInfo["item" + aid];
        raw && raw.Media ? resolve(normalize(raw, aid)) : reject(new Error("No media found for that id"));
        tag.remove();
      };
      tag.onerror = () => reject(new Error("Could not reach Chabad.org"));
      document.head.appendChild(tag);
    });
  }

  async function loadMedia(aid) {
    try {
      const res = await fetch("/api/media?aid=" + encodeURIComponent(aid));
      const data = await res.json();
      if (!res.ok) throw Object.assign(new Error(data.error || "Lookup failed"), { final: res.status === 404 || res.status === 400 });
      return data;
    } catch (e) {
      if (e.final) throw e;
      return loadViaScript(aid);
    }
  }

  function fmt(t) {
    if (!isFinite(t)) return "0:00";
    t = Math.floor(t);
    const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
    const ss = String(s).padStart(2, "0");
    return h ? h + ":" + String(m).padStart(2, "0") + ":" + ss : m + ":" + ss;
  }

  const ICON = {
    play: '<svg viewBox="0 0 24 24"><path d="M7 4v16l13-8z"/></svg>',
    pause: '<svg viewBox="0 0 24 24"><path d="M6 4h4v16H6zM14 4h4v16h-4z"/></svg>',
    vol: '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9zM16 7.5v9a5 5 0 0 0 0-9z"/></svg>',
    mute: '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9zM16.5 9.9l1.4-1.4 2.1 2.1 2.1-2.1 1.4 1.4-2.1 2.1 2.1 2.1-1.4 1.4-2.1-2.1-2.1 2.1-1.4-1.4 2.1-2.1z"/></svg>',
    full: '<svg viewBox="0 0 24 24"><path d="M4 4h6v2H6v4H4zM14 4h6v6h-2V6h-4zM4 14h2v4h4v2H4zM18 14h2v6h-6v-2h4z"/></svg>',
  };

  let hlsLoader = null;
  function needHls() {
    if (window.Hls) return Promise.resolve(window.Hls);
    if (!hlsLoader)
      hlsLoader = new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://cdn.jsdelivr.net/npm/hls.js@1/dist/hls.min.js";
        s.onload = () => resolve(window.Hls);
        s.onerror = () => reject(new Error("Could not load hls.js"));
        document.head.appendChild(s);
      });
    return hlsLoader;
  }

  async function mountPlayer(root, media, opts = {}) {
    if (root._destroy) root._destroy();
    root.innerHTML = `
      <div class="cp">
        <video class="cp-video" playsinline preload="metadata"></video>
        <button class="cp-big" aria-label="Play">${ICON.play}</button>
        <div class="cp-bar">
          <button class="cp-btn cp-play" aria-label="Play">${ICON.play}</button>
          <span class="cp-time"><span class="cp-cur">0:00</span> / <span class="cp-dur">${media.length || "0:00"}</span></span>
          <input class="cp-seek" type="range" min="0" max="1000" value="0" step="1" aria-label="Seek">
          <button class="cp-btn cp-mute" aria-label="Mute">${ICON.vol}</button>
          <select class="cp-sel cp-speed" aria-label="Speed">
            <option value="0.75">0.75x</option><option value="1" selected>1x</option>
            <option value="1.25">1.25x</option><option value="1.5">1.5x</option><option value="2">2x</option>
          </select>
          <select class="cp-sel cp-quality" aria-label="Quality"><option value="-1">Auto</option></select>
          <button class="cp-btn cp-full" aria-label="Fullscreen">${ICON.full}</button>
        </div>
        <div class="cp-msg" hidden></div>
      </div>`;
    const $ = (c) => root.querySelector(c);
    const wrap = $(".cp"), v = $(".cp-video"), big = $(".cp-big"), play = $(".cp-play"),
      seek = $(".cp-seek"), cur = $(".cp-cur"), dur = $(".cp-dur"), mute = $(".cp-mute"),
      speed = $(".cp-speed"), quality = $(".cp-quality"), full = $(".cp-full"), msg = $(".cp-msg");

    const showMsg = (t) => { msg.textContent = t; msg.hidden = false; };
    if (media.poster) v.poster = media.poster;
    if (media.width && media.height) wrap.style.aspectRatio = media.width + " / " + media.height;
    if (media.type === "audio") wrap.classList.add("cp-audio");

    let hls = null;
    const src = media.hls || (media.progressive[0] && media.progressive[0].url);
    const isHls = /\.m3u8/.test(src || "");
    const Hls = isHls ? await needHls().catch(() => null) : null;
    if (!src) showMsg("No playable stream on this item.");
    else if (isHls && !(Hls && Hls.isSupported())) {
      if (v.canPlayType("application/vnd.apple.mpegurl")) v.src = src; // iOS native HLS
      else showMsg("This browser can't play HLS streams.");
      quality.hidden = true;
    } else if (isHls) {
      hls = new Hls({ capLevelToPlayerSize: true });
      hls.loadSource(src);
      hls.attachMedia(v);
      hls.on(Hls.Events.MANIFEST_PARSED, (_, d) => {
        d.levels.forEach((l, i) => {
          const o = document.createElement("option");
          o.value = i;
          const kbps = Math.round(l.bitrate / 1000);
          const known = media.bitrates.find((b) => b.bitrate === kbps);
          const h = l.height || (known && known.height);
          o.textContent = h ? h + "p · " + kbps + "k" : kbps < 100 ? "Audio only" : kbps + "k";
          quality.appendChild(o);
        });
      });
      hls.on(Hls.Events.ERROR, (_, d) => { if (d.fatal) showMsg("Stream error: " + d.details); });
      quality.onchange = () => { hls.currentLevel = Number(quality.value); };
    } else {
      v.src = src;
      quality.hidden = true;
    }

    const toggle = () => (v.paused ? v.play() : v.pause());
    big.onclick = play.onclick = toggle;
    v.onclick = toggle;
    v.onplay = () => { wrap.classList.add("cp-playing"); play.innerHTML = ICON.pause; };
    v.onpause = () => { wrap.classList.remove("cp-playing"); play.innerHTML = ICON.play; };
    v.onloadedmetadata = () => { dur.textContent = fmt(v.duration); if (opts.start) v.currentTime = opts.start; };
    let dragging = false;
    seek.oninput = () => { dragging = true; cur.textContent = fmt((seek.value / 1000) * v.duration); };
    seek.onchange = () => { v.currentTime = (seek.value / 1000) * v.duration; dragging = false; };
    v.ontimeupdate = () => {
      cur.textContent = fmt(v.currentTime);
      if (!dragging && v.duration) seek.value = Math.round((v.currentTime / v.duration) * 1000);
      seek.style.setProperty("--p", (seek.value / 10) + "%");
    };
    mute.onclick = () => { v.muted = !v.muted; mute.innerHTML = v.muted ? ICON.mute : ICON.vol; };
    speed.onchange = () => { v.playbackRate = Number(speed.value); };
    full.onclick = () => {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (wrap.requestFullscreen) wrap.requestFullscreen();
      else if (v.webkitEnterFullscreen) v.webkitEnterFullscreen();
    };
    wrap.tabIndex = 0;
    wrap.onkeydown = (e) => {
      if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT") return;
      if (e.key === " " || e.key === "k") { e.preventDefault(); toggle(); }
      if (e.key === "ArrowRight") v.currentTime += 10;
      if (e.key === "ArrowLeft") v.currentTime -= 10;
      if (e.key === "f") full.onclick();
      if (e.key === "m") mute.onclick();
    };
    if (opts.autoplay) { v.muted = true; mute.innerHTML = ICON.mute; v.play().catch(() => {}); }

    root._destroy = () => { if (hls) hls.destroy(); v.pause(); v.removeAttribute("src"); };
    return { video: v, hls };
  }

  window.ChabadPlayer = { parseId, loadMedia, mountPlayer, fmt };
})();
