"""Fullscreen display server for the TV.

Serves a black kiosk page that always shows the newest generated image,
polling for changes and crossfading when a new artwork appears. Also
exposes a manual-trigger endpoint (tap the bottom-right corner of the
TV page, or POST /api/trigger) that asks the orchestrator to run now.

Run it:
    python -m artframe.display_server
Then open http://localhost:8800 (Edge kiosk mode does this at boot).
"""

from __future__ import annotations

import json

from flask import Flask, jsonify, send_from_directory

from artframe.config import load_config
from artframe.log_setup import get_logger

cfg = load_config()
log = get_logger("display", cfg)
app = Flask(__name__)

IMAGES_DIR = cfg.path("paths", "images_dir")

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Art Frame</title>
<style>
  html, body { margin:0; height:100%; background:#000; overflow:hidden; cursor:none; }
  .art { position:absolute; inset:0; width:100%; height:100%;
         object-fit:__FIT__; opacity:0; transition:opacity 2.5s ease; }
  .art.visible { opacity:1; }
  #msg { position:absolute; inset:0; display:flex; align-items:center;
         justify-content:center; color:#333; font:24px Georgia, serif; }
  #corner { position:absolute; right:0; bottom:0; width:120px; height:120px; }
  #toast { position:absolute; left:50%; bottom:40px; transform:translateX(-50%);
           color:#888; font:18px Georgia, serif; background:rgba(0,0,0,.7);
           padding:10px 24px; border-radius:24px; opacity:0; transition:opacity .5s; }
</style>
</head>
<body>
  <div id="msg">Waiting for the first artwork&hellip;</div>
  <img id="a" class="art" alt="">
  <img id="b" class="art" alt="">
  <div id="corner"></div>
  <div id="toast"></div>
<script>
  const imgs = [document.getElementById('a'), document.getElementById('b')];
  let front = 0, current = null;

  async function poll() {
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
    } catch (e) { /* server restarting — keep showing current art */ }
  }
  poll();
  setInterval(poll, __REFRESH__ * 1000);

  // Hidden manual trigger: tap the bottom-right corner.
  document.getElementById('corner').addEventListener('click', async () => {
    await fetch('/api/trigger', {method:'POST'});
    const t = document.getElementById('toast');
    t.textContent = 'New artwork requested \\u2014 painting takes a while\\u2026';
    t.style.opacity = 1;
    setTimeout(() => t.style.opacity = 0, 6000);
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
    """Small debugging aid: last prompt + gallery size."""
    history_file = cfg.path("paths", "history_file")
    last = None
    if history_file.exists():
        try:
            entries = json.loads(history_file.read_text(encoding="utf-8"))
            last = entries[-1] if entries else None
        except json.JSONDecodeError:
            pass
    img = latest_image()
    return jsonify({
        "latest_image": img.name if img else None,
        "last_prompt": last,
        "gallery_count": len(list(IMAGES_DIR.glob("*.png")))
                         + len(list(IMAGES_DIR.glob("*.jpg"))),
    })


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
