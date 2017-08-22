import time
import traceback
import yaml
from prometheus_client import CONTENT_TYPE_LATEST, Summary, Counter, generate_latest
from .collector import collect_pve

try:
    import urlparse
    from BaseHTTPServer import BaseHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
    from SocketServer import ThreadingMixIn
except ImportError:
    # python3 renamed those modules, try new names
    import urllib.parse as urlparse
    from http.server import BaseHTTPRequestHandler
    from http.server import HTTPServer
    from socketserver import ThreadingMixIn


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
  pass

class PveExporterHandler(BaseHTTPRequestHandler):
  def __init__(self, config_path, duration, errors, *args, **kwargs):
    self._config_path = config_path
    self._duration = duration
    self._errors = errors
    BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

  def do_GET(self):
    url = urlparse.urlparse(self.path)

    with open(self._config_path) as f:
      config = yaml.safe_load(f)

    # Initialize metrics.
    for module in config.keys():
      self._errors.labels(module)
      self._duration.labels(module)

    if url.path == '/pve':
      params = urlparse.parse_qs(url.query)
      module = params.get("module", ["default"])[0]
      if module not in config:
        self.send_response(400)
        self.end_headers()
        self.wfile.write(b"Module '{0}' not found in config".format(module))
        return
      try:
        start = time.time()
        target = params.get('target', ['localhost'])[0]
        output = collect_pve(config[module], target)
        self.send_response(200)
        self.send_header('Content-Type', CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(output)
        self._duration.labels(module).observe(time.time() - start)
      except:
        self._errors.labels(module).inc()
        self.send_response(500)
        self.end_headers()
        self.wfile.write(traceback.format_exc().encode('utf-8'))
    elif url.path == '/metrics':
      try:
        output = generate_latest()
        self.send_response(200)
        self.send_header('Content-Type', CONTENT_TYPE_LATEST)
        self.end_headers()
        self.wfile.write(output)
      except:
        self.send_response(500)
        self.end_headers()
        self.wfile.write(traceback.format_exc().encode('utf-8'))

    elif url.path == '/':
      self.send_response(200)
      self.end_headers()
      self.wfile.write(b"""<html>
      <head><title>Proxmox VE Exporter</title></head>
      <body>
      <h1>Proxmox VE Exporter</h1>
      <p>Visit <code>/pve?target=1.2.3.4</code> to use.</p>
      </body>
      </html>""")
    else:
      self.send_response(404)
      self.end_headers()


def start_http_server(config_path, port):
  duration = Summary(
    'pve_collection_duration_seconds',
    'Duration of collections by the PVE exporter',
    ['module'],
  )
  errors = Counter(
    'pve_request_errors_total',
    'Errors in requests to PVE exporter',
    ['module'],
  )

  handler = lambda *args, **kwargs: PveExporterHandler(config_path, duration, errors, *args, **kwargs)
  server = ThreadingHTTPServer(('', port), handler)
  server.serve_forever()
