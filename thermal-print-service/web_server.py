"""
Ingress web UI for the Thermal Print Service HA add-on.
Shows printer status and allows editing the base_urls config.
"""

import json
import os
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

import requests

logger = logging.getLogger(__name__)

SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "")
SUPERVISOR_API = "http://supervisor/addons/self"

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thermal Printer</title>
<style>
  :root { --bg: #f5f5f5; --card: #fff; --text: #333; --muted: #888; --accent: #03a9f4; --green: #4caf50; --red: #f44336; --orange: #ff9800; --border: #e0e0e0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 24px; }
  h1 { font-size: 1.4em; margin-bottom: 20px; }
  .card { background: var(--card); border-radius: 12px; padding: 20px; margin-bottom: 16px; border: 1px solid var(--border); }
  .card h2 { font-size: 1em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
  .status-row { display: flex; align-items: center; gap: 10px; }
  .status-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
  .status-dot.online { background: var(--green); }
  .status-dot.offline, .status-dot.disconnected { background: var(--red); }
  .status-dot.unknown { background: var(--orange); }
  .status-text { font-size: 1.1em; font-weight: 500; }
  .status-detail { color: var(--muted); font-size: 0.9em; margin-top: 4px; }
  .url-list { list-style: none; margin-bottom: 12px; }
  .url-list li { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .url-list input[type="text"] { flex: 1; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 0.95em; }
  .btn { padding: 8px 16px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.9em; font-weight: 500; }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-danger { background: transparent; color: var(--red); border: 1px solid var(--red); }
  .btn-secondary { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  .btn:hover { opacity: 0.85; }
  .actions { display: flex; gap: 8px; margin-top: 4px; }
  .toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 20px; border-radius: 8px; color: #fff; font-size: 0.9em; display: none; z-index: 100; }
  .toast.success { background: var(--green); }
  .toast.error { background: var(--red); }
  .meta { color: var(--muted); font-size: 0.85em; margin-top: 8px; }
</style>
</head>
<body>

<h1>Thermal Printer</h1>

<div class="card" id="status-card">
  <h2>Printer Status</h2>
  <div class="status-row">
    <div class="status-dot unknown" id="status-dot"></div>
    <span class="status-text" id="status-text">Checking...</span>
  </div>
  <div class="status-detail" id="status-detail"></div>
  <div class="meta" id="status-meta"></div>
</div>

<div class="card">
  <h2>API URLs</h2>
  <ul class="url-list" id="url-list"></ul>
  <div class="actions">
    <button class="btn btn-secondary" onclick="addUrl()">+ Add URL</button>
    <button class="btn btn-primary" onclick="saveUrls()">Save</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
  function toast(msg, type) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast ' + type;
    el.style.display = 'block';
    setTimeout(() => el.style.display = 'none', 3000);
  }

  function renderUrls(urls) {
    const list = document.getElementById('url-list');
    list.innerHTML = '';
    urls.forEach((url, i) => {
      const li = document.createElement('li');
      li.innerHTML = '<input type="text" value="' + url + '" data-idx="' + i + '">'
        + '<button class="btn btn-danger" onclick="removeUrl(' + i + ')">Remove</button>';
      list.appendChild(li);
    });
  }

  function addUrl() {
    const list = document.getElementById('url-list');
    const li = document.createElement('li');
    const idx = list.children.length;
    li.innerHTML = '<input type="text" value="" placeholder="https://..." data-idx="' + idx + '">'
      + '<button class="btn btn-danger" onclick="removeUrl(' + idx + ')">Remove</button>';
    list.appendChild(li);
  }

  function removeUrl(idx) {
    const inputs = document.querySelectorAll('#url-list input');
    const urls = Array.from(inputs).map(i => i.value).filter((_, i) => i !== idx);
    renderUrls(urls);
  }

  function getUrls() {
    return Array.from(document.querySelectorAll('#url-list input')).map(i => i.value.trim()).filter(Boolean);
  }

  async function saveUrls() {
    const urls = getUrls();
    if (urls.length === 0) { toast('Add at least one URL', 'error'); return; }
    try {
      const res = await fetch('api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_urls: urls })
      });
      const data = await res.json();
      if (data.ok) toast('Saved — restart addon to apply', 'success');
      else toast(data.error || 'Save failed', 'error');
    } catch (e) { toast('Request failed', 'error'); }
  }

  async function loadStatus() {
    try {
      const res = await fetch('api/status');
      const data = await res.json();
      const dot = document.getElementById('status-dot');
      const txt = document.getElementById('status-text');
      const detail = document.getElementById('status-detail');
      const meta = document.getElementById('status-meta');

      dot.className = 'status-dot ' + (data.status === 'online' ? 'online' : data.status === 'unknown' ? 'unknown' : 'offline');
      txt.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1).replace('_', ' ');
      detail.textContent = data.description || '';
      meta.textContent = 'Device: ' + data.device + '  |  Poll: ' + data.poll_interval + 's';
    } catch (e) {
      document.getElementById('status-text').textContent = 'Error loading status';
    }
  }

  async function loadConfig() {
    try {
      const res = await fetch('api/config');
      const data = await res.json();
      renderUrls(data.base_urls || []);
    } catch (e) { console.error(e); }
  }

  loadStatus();
  loadConfig();
  setInterval(loadStatus, 5000);
</script>
</body>
</html>
"""


class JsonResponse:
    @staticmethod
    def send(handler, data, status=200):
        body = json.dumps(data).encode()
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)


class IngressHandler(BaseHTTPRequestHandler):
    service = None  # set externally

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)

    def do_GET(self):
        # Strip ingress prefix — HA forwards /api/hassio_ingress/<token>/...
        path = self.path.rstrip("/")
        # Normalise: remove everything up to and including the last known prefix
        if "/api/hassio_ingress/" in path:
            path = "/" + path.split("/", 5)[-1] if path.count("/") > 4 else "/"
        if not path or path == "/":
            self._serve_html()
        elif path == "/api/status":
            self._get_status()
        elif path == "/api/config":
            self._get_config()
        else:
            self.send_error(404)

    def do_POST(self):
        path = self.path.rstrip("/")
        if "/api/hassio_ingress/" in path:
            path = "/" + path.split("/", 5)[-1] if path.count("/") > 4 else "/"
        if path == "/api/config":
            self._post_config()
        else:
            self.send_error(404)

    def _serve_html(self):
        body = HTML_PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _get_status(self):
        svc = IngressHandler.service
        if svc:
            svc.check_printer_status()
            JsonResponse.send(self, {
                "status": svc.printer_status,
                "description": svc.get_status_description(svc.printer_status),
                "device": os.getenv("PRINTER_DEVICE", "/dev/usb/lp0"),
                "poll_interval": int(os.getenv("POLL_INTERVAL", "10")),
            })
        else:
            JsonResponse.send(self, {"status": "unknown", "description": "Service not started"})

    def _get_config(self):
        try:
            resp = requests.get(
                f"{SUPERVISOR_API}/options/config",
                headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", resp.json())
                JsonResponse.send(self, {"base_urls": data.get("base_urls", [])})
            else:
                JsonResponse.send(self, {"base_urls": [], "error": f"Supervisor HTTP {resp.status_code}"})
        except Exception as e:
            logger.error(f"Failed to read config from Supervisor: {e}")
            # Fallback: return current env
            raw = os.getenv("BASE_URLS", "")
            JsonResponse.send(self, {"base_urls": [u.strip() for u in raw.split(",") if u.strip()]})

    def _post_config(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            new_urls = body.get("base_urls", [])
            if not new_urls:
                JsonResponse.send(self, {"ok": False, "error": "No URLs provided"}, 400)
                return

            # Read current options, merge, write back
            resp = requests.get(
                f"{SUPERVISOR_API}/options/config",
                headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
                timeout=5,
            )
            current = resp.json().get("data", resp.json()) if resp.status_code == 200 else {}
            current["base_urls"] = new_urls

            resp = requests.post(
                f"{SUPERVISOR_API}/options",
                json={"options": current},
                headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
                timeout=5,
            )
            if resp.status_code == 200:
                JsonResponse.send(self, {"ok": True})
            else:
                JsonResponse.send(self, {"ok": False, "error": f"Supervisor HTTP {resp.status_code}"}, 500)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            JsonResponse.send(self, {"ok": False, "error": str(e)}, 500)


def start_ingress_server(service_instance, port=8099):
    IngressHandler.service = service_instance
    server = HTTPServer(("0.0.0.0", port), IngressHandler)
    logger.info(f"Ingress web UI listening on port {port}")
    server.serve_forever()
