"""HTTP adapter: stdlib threading server, JSON responses, no caching by browsers or proxies."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from team_analytics.service import Service


def make_server(service: Service, host: str, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # access logs come from the proxy in front
            pass

        def _respond(self) -> None:
            url = urlsplit(self.path)
            query = {key: values[-1] for key, values in parse_qs(url.query, keep_blank_values=True).items()}
            status, body = service.handle(self.command, url.path, query, self.headers)  # case-insensitive
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = _respond  # noqa: N815 - http.server API
        do_POST = _respond  # noqa: N815
        do_PUT = _respond  # noqa: N815
        do_DELETE = _respond  # noqa: N815

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
