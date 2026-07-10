"""Fullscreen display server for the TV.

Serves a black kiosk page that shows the artworks: the newest painting
always interrupts and takes the screen, and between generations an
optional slideshow rotates through the gallery (favorites weighted).
Moving the mouse reveals a small opener (top-right); the panel behind it
shows the prompt for what's on screen, the live pipeline stage, component
health, a gallery strip (click to view, star to pin), and a button to
paint a new image on demand.

Run it:
    python -m artframe.display_server
Then open http://localhost:8800 (Edge kiosk mode does this at boot).
"""

from __future__ import annotations

import time

import requests
from flask import Flask, jsonify, request, send_from_directory

from artframe.config import load_config
from artframe.gallery import ensure_thumb, gallery_entries, toggle_favorite
from artframe.log_setup import get_logger
from artframe.status import beat_ages, read_status

cfg = load_config()
log = get_logger("display", cfg)
app = Flask(__name__)

IMAGES_DIR = cfg.path("paths", "images_dir")
THUMBS_DIR = cfg.path("paths", "thumbs_dir")

# Heartbeat age (seconds) beyond which a component counts as down.
# The cycle engine gets a wide window: its slowest silent stretch is an
# Ollama cold-load during prompting (up to a few minutes, no beats).
STALE_AFTER = {"listener": 120, "orchestrator": 360}

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Art Frame</title>
<style>
  html, body { margin:0; height:100%; background:#000; overflow:hidden; cursor:none; }
  body.show-cursor { cursor:default; }
  .art { position:absolute; inset:0; width:100%; height:100%;
         object-fit:__FIT__; opacity:0; transition:opacity 2.5s ease; }
  .art.visible { opacity:1; }
  #msg { position:absolute; inset:0; display:flex; align-items:center;
         justify-content:center; color:#333; font:24px Georgia, serif; }

  /* invisible hover target in the top-right corner */
  #hot { position:fixed; top:0; right:0; width:200px; height:200px; z-index:5; }

  /* the ONLY visible affordance: a subtle round opener, hidden by
     default (pure art) and faded in only while the mouse is moving */
  #opener { position:fixed; top:18px; right:18px; z-index:6;
            width:44px; height:44px; border-radius:50%;
            display:flex; align-items:center; justify-content:center;
            background:rgba(20,20,24,.55); color:#d0d0d0; font:20px Georgia, serif;
            border:1px solid rgba(255,255,255,.12); cursor:pointer;
            opacity:0; transition:opacity .4s; pointer-events:none; }
  body.show-cursor #opener { opacity:.7; pointer-events:auto; }
  body.panel-open  #opener { opacity:0; pointer-events:none; }

  /* "viewing archive" pill, bottom-left, only while holding a past work */
  #livepill { position:fixed; left:18px; bottom:18px; z-index:6;
              color:#ccc; font:14px Georgia, serif;
              background:rgba(20,20,24,.72); border:1px solid rgba(255,255,255,.14);
              padding:8px 16px; border-radius:20px; cursor:pointer;
              opacity:0; pointer-events:none; transition:opacity .4s; }
  body.held.show-cursor #livepill { opacity:.9; pointer-events:auto; }

  #panel { position:fixed; top:16px; right:16px; z-index:7; width:410px;
           max-width:calc(100vw - 32px);
           background:rgba(16,16,20,.94); color:#e6e6e6;
           font:16px/1.5 Georgia, serif; border-radius:16px;
           padding:20px 22px; box-shadow:0 18px 50px rgba(0,0,0,.6);
           transform:translateX(calc(100% + 40px)); transition:transform .35s ease; }
  body.panel-open #panel { transform:translateX(0); }

  #p-state { display:flex; align-items:center; font-size:19px; margin-bottom:2px; }
  #p-dot { width:11px; height:11px; border-radius:50%; background:#666;
           margin-right:10px; flex:0 0 auto; box-shadow:0 0 10px currentColor; }
  #p-elapsed { color:#9a9a9a; font-size:14px; min-height:18px; margin-bottom:12px; }
  .p-label { text-transform:uppercase; letter-spacing:.12em; font-size:12px;
             color:#8a8a8a; margin-bottom:6px; display:flex;
             justify-content:space-between; align-items:center; }
  #p-star { font-size:20px; cursor:pointer; color:#777; line-height:1; }
  #p-star.on { color:#e8c34a; }
  #p-prompt { font-size:15px; color:#dcdcdc; max-height:24vh; overflow:auto;
              margin-bottom:12px; }
  #p-health { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:14px; }
  .h-item { display:flex; align-items:center; font-size:13px; color:#a8a8a8; }
  .h-dot { width:8px; height:8px; border-radius:50%; margin-right:6px;
           background:#666; }
  .h-dot.ok  { background:#5fbf7f; }
  .h-dot.bad { background:#e05a5a; }
  #p-strip { display:flex; gap:8px; overflow-x:auto; padding-bottom:6px;
             margin-bottom:14px; scrollbar-width:thin; }
  #p-strip img { height:58px; border-radius:6px; cursor:pointer; flex:0 0 auto;
                 border:2px solid transparent; opacity:.85; }
  #p-strip img:hover { opacity:1; }
  #p-strip img.current { border-color:#8fa8d0; opacity:1; }
  #p-strip img.fav { border-color:#e8c34a; }
  #p-btn { width:100%; padding:12px 16px; font:16px Georgia, serif; color:#fff;
           background:#3b3b46; border:1px solid #55555f; border-radius:10px;
           cursor:pointer; transition:background .2s; }
  #p-btn:hover { background:#4a4a58; }
  #p-btn:disabled { opacity:.5; cursor:default; }
  #p-note { color:#9ab; font-size:13px; min-height:18px; margin-top:10px; }
</style>
</head>
<body>
  <div id="msg">Waiting for the first artwork...</div>
  <img id="a" class="art" alt="">
  <img id="b" class="art" alt="">

  <div id="hot"></div>
  <div id="opener" title="Show details">&#9432;</div>
  <div id="livepill">&#8617; viewing archive &mdash; back to live</div>
  <div id="panel">
    <div id="p-state"><span id="p-dot"></span><span id="p-stage">Loading...</span></div>
    <div id="p-elapsed"></div>
    <div class="p-label"><span id="p-label-text">On screen</span>
      <span id="p-star" title="Pin this artwork">&#9734;</span></div>
    <div id="p-prompt">-</div>
    <div class="p-label">System</div>
    <div id="p-health"></div>
    <div class="p-label">Gallery</div>
    <div id="p-strip"></div>
    <button id="p-btn">Paint a new one now</button>
    <div id="p-note"></div>
  </div>

<script>
  const REFRESH_S = __REFRESH__;
  const SLIDESHOW_MIN = __SLIDESHOW__;   // 0 = disabled
  const FAV_BOOST = __BOOST__;
  const HOLD_MS = 10 * 60 * 1000;        // archive view returns to live after 10 min

  // ---- crossfading image display ----
  const imgs = [document.getElementById('a'), document.getElementById('b')];
  let front = 0, displayed = null;       // displayed = gallery entry on screen

  function show(entry) {
    if (!entry || (displayed && displayed.key === entry.key)) return;
    displayed = entry;
    const back = 1 - front;
    imgs[back].onload = () => {
      document.getElementById('msg').style.display = 'none';
      imgs[back].classList.add('visible');
      imgs[front].classList.remove('visible');
      front = back;
    };
    imgs[back].src = '/image/' + encodeURIComponent(entry.file) + '?v=' + entry.key;
    updatePanelArt();
  }

  // ---- gallery state + slideshow rotation ----
  let gallery = [], lastNewestKey = null, queue = [];
  let mode = 'auto', heldAt = 0, slideLast = Date.now();

  function buildQueue() {
    let pool = [];
    for (const e of gallery)
      for (let i = 0; i < (e.favorite ? FAV_BOOST : 1); i++) pool.push(e);
    for (let i = pool.length - 1; i > 0; i--) {          // shuffle
      const j = Math.floor(Math.random() * (i + 1));
      [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    queue = pool;
  }

  function nextSlide() {
    if (!queue.length) buildQueue();
    for (let i = 0; i < queue.length; i++) {
      const e = queue.shift();
      if (!displayed || e.key !== displayed.key) return e;
    }
    return null;
  }

  async function tick() {
    try {
      const r = await fetch('/api/gallery', {cache:'no-store'});
      gallery = await r.json();
    } catch (e) { return; }
    if (!gallery.length) return;
    const newest = gallery[0];

    if (lastNewestKey === null) {              // first load: show newest
      lastNewestKey = newest.key;
      show(newest);
      slideLast = Date.now();
    } else if (newest.key !== lastNewestKey) { // fresh painting: interrupt
      lastNewestKey = newest.key;
      mode = 'auto';
      document.body.classList.remove('held');
      buildQueue();
      show(newest);
      slideLast = Date.now();
    } else if (mode === 'held' && Date.now() - heldAt > HOLD_MS) {
      backToLive();
    } else if (mode === 'auto' && SLIDESHOW_MIN > 0 && gallery.length > 1 &&
               Date.now() - slideLast >= SLIDESHOW_MIN * 60000) {
      const e = nextSlide();
      if (e) { show(e); slideLast = Date.now(); }
    }
    if (panelOpen) renderStrip();
  }
  tick();
  setInterval(tick, REFRESH_S * 1000);

  function backToLive() {
    mode = 'auto';
    document.body.classList.remove('held');
    if (gallery.length) { show(gallery[0]); slideLast = Date.now(); }
  }
  document.getElementById('livepill').addEventListener('click', backToLive);

  // ---- cursor reveal on movement (media-player style) ----
  let cursorTimer = null;
  function showCursor() {
    document.body.classList.add('show-cursor');
    clearTimeout(cursorTimer);
    cursorTimer = setTimeout(() => {
      if (!document.body.classList.contains('panel-open'))
        document.body.classList.remove('show-cursor');
    }, 4000);
  }
  document.addEventListener('mousemove', showCursor);

  // ---- slide-out control panel ----
  const STAGES = {
    idle:         {c:'#5fbf7f', t:'Idle'},
    transcribing: {c:'#d7c65a', t:'Listening back'},
    prompting:    {c:'#6aa8e0', t:'Composing a scene'},
    generating:   {c:'#e0955a', t:'Painting'},
    error:        {c:'#e05a5a', t:'Problem - check logs'}
  };
  let statusTimer = null, closeTimer = null, panelOpen = false, lastStatus = null;

  function openPanel() {
    clearTimeout(closeTimer);
    panelOpen = true;
    document.body.classList.add('panel-open', 'show-cursor');
    refreshStatus();
    renderStrip();
    clearInterval(statusTimer);
    statusTimer = setInterval(refreshStatus, 3000);
  }
  function closePanel() {
    panelOpen = false;
    document.body.classList.remove('panel-open');
    clearInterval(statusTimer);
    showCursor();  // restart the hide timer so the opener + cursor fade out
  }
  const hot = document.getElementById('hot');
  const panel = document.getElementById('panel');
  const opener = document.getElementById('opener');
  hot.addEventListener('mouseenter', openPanel);
  opener.addEventListener('click', openPanel);  // click/tap the button
  hot.addEventListener('click', openPanel);      // touch friendly
  panel.addEventListener('mouseenter', () => clearTimeout(closeTimer));
  function scheduleClose() { closeTimer = setTimeout(closePanel, 700); }
  panel.addEventListener('mouseleave', scheduleClose);
  hot.addEventListener('mouseleave', scheduleClose);

  function fmtElapsed(s) {
    const m = Math.floor(s / 60), sec = s % 60;
    return m + 'm ' + String(sec).padStart(2, '0') + 's elapsed';
  }

  function updatePanelArt() {
    if (!panelOpen && !displayed) return;
    const s = lastStatus || {};
    const painting = s.stage === 'generating';
    document.getElementById('p-label-text').textContent =
      painting ? 'Now painting' : 'On screen';
    const prompt = painting ? s.prompt
                 : (displayed && displayed.prompt) || s.prompt;
    document.getElementById('p-prompt').textContent = prompt || '(none yet)';
    const star = document.getElementById('p-star');
    const fav = displayed && displayed.favorite;
    star.textContent = fav ? '\\u2605' : '\\u2606';
    star.classList.toggle('on', !!fav);
  }

  const HEALTH_LABELS = {listener:'Mic', orchestrator:'Cycles',
                         comfyui:'Painter', ollama:'Prompter'};
  function renderHealth(h) {
    const box = document.getElementById('p-health');
    box.innerHTML = '';
    for (const key of Object.keys(HEALTH_LABELS)) {
      if (!h || !(key in h)) continue;
      const item = document.createElement('span');
      item.className = 'h-item';
      const dot = document.createElement('span');
      dot.className = 'h-dot ' + (h[key].ok ? 'ok' : 'bad');
      item.appendChild(dot);
      item.appendChild(document.createTextNode(HEALTH_LABELS[key]));
      box.appendChild(item);
    }
  }

  function renderStrip() {
    const strip = document.getElementById('p-strip');
    strip.innerHTML = '';
    for (const e of gallery.slice(0, 30)) {
      const im = document.createElement('img');
      im.src = '/thumb/' + encodeURIComponent(e.file);
      im.title = e.prompt || e.file;
      if (displayed && e.key === displayed.key) im.classList.add('current');
      if (e.favorite) im.classList.add('fav');
      im.addEventListener('click', () => {
        mode = 'held'; heldAt = Date.now();
        document.body.classList.add('held');
        show(e);
        renderStrip();
      });
      strip.appendChild(im);
    }
  }

  async function refreshStatus() {
    try {
      const r = await fetch('/api/status', {cache:'no-store'});
      const s = await r.json();
      lastStatus = s;
      const meta = STAGES[s.stage] || {c:'#888', t:s.stage || '-'};
      document.getElementById('p-dot').style.color = meta.c;
      document.getElementById('p-dot').style.background = meta.c;
      document.getElementById('p-stage').textContent = s.message || meta.t;

      let el = '';
      if (s.stage === 'generating' && typeof s.elapsed_seconds === 'number')
        el = fmtElapsed(s.elapsed_seconds) + '  (a full painting takes ~15-30 min)';
      document.getElementById('p-elapsed').textContent = el;

      renderHealth(s.health);
      updatePanelArt();
    } catch (e) { /* ignore transient errors */ }
  }

  document.getElementById('p-star').addEventListener('click', async () => {
    if (!displayed) return;
    try {
      const r = await fetch('/api/favorite', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({file: displayed.file})});
      const j = await r.json();
      displayed.favorite = j.favorite;
      const g = gallery.find(e => e.file === displayed.file);
      if (g) g.favorite = j.favorite;
      updatePanelArt();
      renderStrip();
    } catch (e) { }
  });

  const btn = document.getElementById('p-btn');
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    const note = document.getElementById('p-note');
    try {
      await fetch('/api/trigger', {method:'POST'});
      note.textContent = 'Requested - a new painting will begin within ~30 seconds.';
    } catch (e) {
      note.textContent = 'Could not reach the server.';
    }
    setTimeout(() => { btn.disabled = false; note.textContent = ''; }, 8000);
    setTimeout(refreshStatus, 1000);
  });
</script>
</body>
</html>"""


def latest_image():
    files = [p for p in IMAGES_DIR.iterdir()
             if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


@app.route("/")
def index():
    d = cfg["display"]
    slideshow = d["slideshow_minutes"] if d.get("slideshow_enable") else 0
    html = (PAGE.replace("__REFRESH__", str(d["refresh_seconds"]))
                .replace("__FIT__", d["fit"])
                .replace("__SLIDESHOW__", str(slideshow))
                .replace("__BOOST__", str(d.get("slideshow_favorites_boost", 2))))
    return html


@app.route("/api/latest")
def api_latest():
    img = latest_image()
    if not img:
        return jsonify({"file": None, "key": None})
    return jsonify({"file": img.name, "key": f"{img.name}:{int(img.stat().st_mtime)}"})


@app.route("/api/gallery")
def api_gallery():
    return jsonify(gallery_entries(cfg))


@app.route("/image/<path:name>")
def image(name: str):
    return send_from_directory(IMAGES_DIR, name, max_age=0)


@app.route("/thumb/<path:name>")
def thumb(name: str):
    t = ensure_thumb(cfg, name)
    if t is not None:
        return send_from_directory(THUMBS_DIR, t.name, max_age=3600)
    # Fallback (e.g. Pillow not installed): serve the full image; the
    # browser scales it down. Heavier, but the gallery still works.
    if (IMAGES_DIR / name).exists():
        return send_from_directory(IMAGES_DIR, name, max_age=3600)
    return jsonify({"error": "not found"}), 404


@app.route("/api/favorite", methods=["POST"])
def api_favorite():
    name = (request.get_json(silent=True) or {}).get("file", "")
    if not name or not (IMAGES_DIR / name).exists():
        return jsonify({"error": "unknown image"}), 404
    state = toggle_favorite(cfg, name)
    log.info("favorite %s -> %s", name, state)
    return jsonify({"file": name, "favorite": state})


@app.route("/api/trigger", methods=["POST"])
def api_trigger():
    cfg.path("paths", "trigger_flag").write_text("now", encoding="utf-8")
    log.info("manual generation requested via display")
    return jsonify({"ok": True})


# ------------------------------------------------- component health checks
_svc_cache: dict[str, tuple[float, bool]] = {}


def _svc_ok(name: str, url: str) -> bool:
    """HTTP liveness with a 30 s cache so /api/status stays cheap."""
    ts, ok = _svc_cache.get(name, (0.0, False))
    if time.time() - ts < 30:
        return ok
    try:
        requests.get(url, timeout=3)
        ok = True
    except requests.RequestException:
        ok = False
    _svc_cache[name] = (time.time(), ok)
    return ok


def component_health() -> dict:
    ages = beat_ages(cfg)
    health = {}
    for name, stale in STALE_AFTER.items():
        age = ages.get(name)
        health[name] = {"ok": age is not None and age < stale,
                        "age_seconds": None if age is None else int(age)}
    health["comfyui"] = {"ok": _svc_ok(
        "comfyui", f"{cfg['comfyui']['base_url']}/system_stats")}
    health["ollama"] = {"ok": _svc_ok(
        "ollama", f"{cfg['llm']['base_url']}/api/tags")}
    return health


@app.route("/api/status")
def api_status():
    """Live pipeline state for the control panel (and handy for debugging)."""
    st = read_status(cfg)
    img = latest_image()

    resp = {
        "stage": st.get("stage", "idle"),
        "message": st.get("message", ""),
        "prompt": st.get("prompt"),
        "source": st.get("source"),
        "updated": st.get("updated"),
        "latest_image": img.name if img else None,
        "gallery_count": len(list(IMAGES_DIR.glob("*.png")))
                         + len(list(IMAGES_DIR.glob("*.jpg"))),
        "health": component_health(),
    }
    if st.get("stage") == "generating" and st.get("generating_since"):
        resp["elapsed_seconds"] = int(time.time() - st["generating_since"])
    return jsonify(resp)


def main() -> None:
    host, port = cfg["display"]["host"], cfg["display"]["port"]
    log.info("display server on http://%s:%d", host, port)
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=4)
    except ImportError:  # fall back to Flask's dev server
        app.run(host=host, port=port)


if __name__ == "__main__":
    main()
