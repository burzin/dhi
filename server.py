#!/usr/bin/env python3
"""
Local proxy + static server for the OpenRouter Chat tool.

Serves index.html on http://localhost:8765/ and provides a /proxy endpoint
that forwards POST/GET requests to any target URL, bypassing CORS restrictions.

Usage:
    python3 server.py
"""

import http.server
import subprocess
import ssl
import sys
import os
import json
from urllib.parse import urlparse, parse_qs

PORT = 8765
ROOT = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, HTTP-Referer, X-Title, Accept")
        self.send_header("Access-Control-Expose-Headers", "X-Generation-Id, X-Provider-Name")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/proxy":
            self._proxy("GET")
        else:
            self._serve_file()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/proxy":
            self._proxy("POST")
        else:
            self.send_error(404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path == "/proxy":
            self._proxy("PUT")
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path == "/proxy":
            self._proxy("DELETE")
        else:
            self.send_error(404)

    def _serve_file(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/" or path == "":
            path = "/index.html"
        filepath = os.path.join(ROOT, path.lstrip("/"))
        if not os.path.isfile(filepath):
            self.send_error(404, "File not found")
            return
        ext = os.path.splitext(filepath)[1].lower()
        ct_map = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
        }
        ctype = ct_map.get(ext, "application/octet-stream")
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _proxy(self, method):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        target = qs.get("url", [None])[0]
        if not target:
            self._json_error(400, "Missing 'url' query parameter")
            return

        # Read body for non-GET
        body = None
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length)

        # Build curl command — curl handles TLS fingerprinting correctly
        # (Cloudflare blocks Python's urllib TLS stack via JA3 fingerprinting).
        curl_cmd = ["curl", "-s", "-X", method, "-i", "--max-time", "300", target]
        # Forward select headers
        ct = self.headers.get("Content-Type", "application/json")
        curl_cmd += ["-H", "Content-Type: " + ct]
        auth = self.headers.get("Authorization")
        if auth:
            curl_cmd += ["-H", "Authorization: " + auth]
        accept = self.headers.get("Accept")
        if accept:
            curl_cmd += ["-H", "Accept: " + accept]
        referer = self.headers.get("HTTP-Referer")
        if referer:
            curl_cmd += ["-H", "HTTP-Referer: " + referer]
        xtitle = self.headers.get("X-Title")
        if xtitle:
            curl_cmd += ["-H", "X-Title: " + xtitle]
        if body:
            curl_cmd += ["--data-binary", "@-"]

        try:
            proc = subprocess.run(curl_cmd, input=body, capture_output=True, timeout=300)
            raw = proc.stdout
            if not raw:
                err = proc.stderr.decode("utf-8", errors="replace")
                self._json_error(502, "curl error: " + err[:500])
                return
            # Parse curl's -i output: status line + headers + blank line + body
            header_end = raw.find(b"\r\n\r\n")
            if header_end == -1:
                header_end = raw.find(b"\n\n")
                sep_len = 2
            else:
                sep_len = 4
            if header_end == -1:
                self._json_error(502, "Malformed response from curl")
                return
            header_block = raw[:header_end].decode("iso-8859-1")
            resp_body = raw[header_end + sep_len:]
            # Parse status and headers
            lines = header_block.split("\r\n")
            if len(lines) == 1:
                lines = header_block.split("\n")
            status_line = lines[0]
            parts = status_line.split(" ", 2)
            status_code = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 200
            is_stream = False
            self.send_response(status_code)
            for line in lines[1:]:
                if not line.strip():
                    continue
                idx = line.find(":")
                if idx == -1:
                    continue
                h = line[:idx].strip()
                v = line[idx + 1:].strip()
                low = h.lower()
                if low in ("transfer-encoding", "content-encoding", "content-length", "connection"):
                    continue
                self.send_header(h, v)
                if low == "content-type" and "text/event-stream" in v:
                    is_stream = True
            if is_stream:
                self.send_header("Transfer-Encoding", "chunked")
            else:
                self.send_header("Content-Length", str(len(resp_body)))
            self._cors_headers()
            self.end_headers()
            if is_stream:
                # Write body in chunks
                offset = 0
                while offset < len(resp_body):
                    chunk = resp_body[offset:offset + 4096]
                    offset += len(chunk)
                    if chunk:
                        self.wfile.write(("%x\r\n" % len(chunk)).encode() + chunk + b"\r\n")
                        self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            else:
                self.wfile.write(resp_body)
        except subprocess.TimeoutExpired:
            self._json_error(504, "Upstream request timed out")
        except Exception as e:
            self._json_error(500, "Proxy error: " + str(e))

    def _json_error(self, code, msg):
        payload = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

def main():
    server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/  (proxy: http://localhost:{PORT}/proxy?url=...)")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.shutdown()

if __name__ == "__main__":
    main()
