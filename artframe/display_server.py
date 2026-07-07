"""Fullscreen display server for the TV.

Serves a black kiosk page that always shows the newest generated image,
polling for changes and crossfading when a new artwork appears. Moving
the mouse into the top-right corner slides out a control panel showing
the current prompt, the live pipeline stage, and a button to paint a new
image on demand (equivalent to POST /api/trigger).

Run it:
    python -m artframe.display_server
Then open http://localhost:8800 (Edge kiosk mode does this at boot).
"""

from __future__ import annotations

import json
import time

from flask import Flask, jsonify, send_from_directory

from artframe.config import load_config
from artframe.log_setup import get_logger
from artframe.status import read_status

cfg = load_config()
log = get_logger("display", cfg)
app = Flask(__name__)

IMAGES_DIR = cfg.path("paths", "images_dir")

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

  /* small hint tab, only visible while the cursor is showing */
  #hint { position:fixed; top:16px; right:16px; z-index:6;
          color:#bbb; font:14px Georgia, serif; letter-spacing:.04em;
          background:rgba(20,20,24,.72); padding:7px 14px; border-radius:20px;
          opacity:0; transition:opacity .4s; pointer-events:none; }
  body.show-cursor #hint { opacity:.85; }
  body.panel-open #hint { opacity:0; }

  #panel { position:fixed; top:16px; right:16px; z-index:7; width:390px;
           max-width:calc(100vw - 32px);
           background:rgba(16,16,20,.94); color:#e6e6e6;
           font:16px/1.5 Georgia, serif; border-radius:16px;
           padding:20px 22px; box-shadow:0 18px 50px rgba(0,0,0,.6);
           transform:translateX(calc(100% + 40px)); transition:transform .35s ease; }
  body.panel-open #panel { transform:translateX(0); }

  #p-state { display:flex; align-items:center; font-size:19px; margin-bottom:2px; }
  #p-dot { width:11px; height:11px; border-radius:50%; background:#666;
           margin-right:10px; flex:0 0 auto; box-shadow:0 0 10px currentColor; }
  #p-elapsed { color:#9a9a9a; font-size:14px; min-height:18px; margin-bottom:14px; }
  #p-label { text-transform:uppercase; letter-spacing:.12em; font-size:12px;
             color:#8a8a8a; margin-bottom:6px; }
  #p-prompt { font-size:15px; color:#dcdcdc; max-height:34vh; overflow:auto;
              margin-bottom:12px; }
  #p-meta { color:#8a8a8a; font-size:13px; margin-bottom:16px; }
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
  <div id="hint">&#9432; details</div>
  <div id="panel">
    <div id="p-state"><span id="p-dot"></span><span id="p-stage">Loading...</span></div>
    <div id="p-elapsed"></div>
    <div id="p-label">On screen</div>
    <div id="p-prompt">-</div>
    <div id="p-meta"></div>
    <button id="p-btn">Paint a new one now</button>
    <div id="p-note"></div>
  </div>

<script>
  // ---- crossfading image display ----
  const imgs = [document.getElementById('a'), document.getElementById('b')];
  let front = 0, current = null;

  async function pollImage() {
    try {
      const r = await fetch('/api/latest', {cache:'no-store'});
      const j = await r.json();
      if (j.file && j.key !== current) {
        current = j.key;
        const back = 1 - front;
        imgs[back].onload = () => {
          document.getElementById('msg').style.display = 'none';
          imgs[back].classList.add('visible');
          imgs[front].classList.remove('visible');
          front = back;
        };
        imgs[back].src = '/image/' + encodeURIComponent(j.file) + '?v=' + j.key;
      }
    } catch (e) { /* server restarting - keep showing current art */ }
  }
  pollImage();
  setInterval(pollImage, __REFRESH__ * 1000);

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
  let statusTimer = null, closeTimer = null, panelOpen = false;

  function openPanel() {
    clearTimeout(closeTimer);
    panelOpen = true;
    document.body.classList.add('panel-open', 'show-cursor');
    refreshStatus();
    clearInterval(statusTimer);
    statusTimer = setInterval(refreshStatus, 3000);
  }
  function closePanel() {
    panelOpen = false;
    document.body.classList.remove('panel-open');
    clearInterval(statusTimer);
  }
  const hot = document.getElementById('hot');
  const panel = document.getElementById('panel');
  hot.addEventListener('mouseenter', openPanel);
  hot.addEventListener('click', openPanel);   // touch friendly
  panel.addEventListener('mouseenter', () => clearTimeout(closeTimer));
  function scheduleClose() { closeTimer = setTimeout(closePanel, 700); }
  panel.addEventListener('mouseleave', scheduleClose);
  hot.addEventListener('mouseleave', scheduleClose);

  function fmtElapsed(s) {
    const m = Math.floor(s / 60), sec = s % 60;
    return m + 'm ' + String(sec).padStart(2, '0') + 's elapsed';
  }

  async function refreshStatus() {
    try {
      const r = await fetch('/api/status', {cache:'no-store'});
      const s = await r.json();
      const meta = STAGES[s.stage] || {c:'#888', t:s.stage || '-'};
      document.getElementById('p-dot').style.color = meta.c;
      document.getElementById('p-dot').style.background = meta.c;
      document.getElementById('p-stage').textContent = s.message || meta.t;

      let el = '';
      if (s.stage === 'generating' && typeof s.elapsed_seconds === 'number')
        el = fmtElapsed(s.elapsed_seconds) + '  (a full painting takes ~15-30 min)';
      document.getElementById('p-elapsed').textContent = el;

      document.getElementById('p-label').textContent =
        (s.stage === 'generating') ? 'Now painting' : 'On screen';
      document.getElementById('p-prompt').textContent = s.prompt || '(none yet)';

      let m = [];
      if (s.source) m.push('source: ' + s.source);
      if (typeof s.gallery_count === 'number') m.push(s.gallery_count + ' in gallery');
      if (s.updated) m.push('updated ' + s.updated);
      document.getElementById('p-meta').textContent = m.join('  -  ');
    } catch (e) { /* ignore transient errors */ }
  }

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
    html = PAGE.replace("__REFRESH__", str(cfg["display"]["refresh_seconds"]))
    html = html.replace("__FIT__", cfg["display"]["fit"])
    return html


@app.route("/api/latest")
def api_latest():
    img = latest_image()
    if not img:
        return jsonify({"file": None, "key": None})
    return jsonify({"file": img.name, "key": f"{img.name}:{int(img.stat().st_mtime)}"})


@app.route("/image/<path:name>")
def image(name: str):
    return send_from_directory(IMAGES_DIR, name, max_age=0)


@app.route("/api/trigger", methods=["POST"])
def api_trigger():
    cfg.path("paths", "trigger_flag").write_text("now", encoding="utf-8")
    log.info("manual generation requested via display")
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    """Live pipeline state for the control panel (and handy for debugging)."""
    st = read_status(cfg)
    img = latest_image()

    prompt = st.get("prompt")
    if not prompt:  # before the first cycle, fall back to history
        history_file = cfg.path("paths", "history_file")
        if history_file.exists():
            try:
                entries = json.loads(history_file.read_text(encoding="utf-8"))
                if entries:
                    prompt = entries[-1].get("prompt")
            except json.JSONDecodeError:
                pass

    resp = {
        "stage": st.get("stage", "idle"),
        "message": st.get("message", ""),
        "prompt": prompt,
        "source": st.get("source"),
        "updated": st.get("updated"),
        "latest_image": img.name if img else None,
        "gallery_count": len(list(IMAGES_DIR.glob("*.png")))
                         + len(list(IMAGES_DIR.glob("*.jpg"))),
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
