"""HTTP adapter: stdlib threading server, JSON responses, no caching by browsers or proxies."""

from __future__ import annotations

import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from team_analytics.periods import decimal
from team_analytics.service import Service

# Larger request bodies are not read: the connection is closed after the answer instead. The service
# reads no body (GET only); a body is only consumed so that it is never taken for the next request.
MAX_BODY = 64 * 1024
# After an answer that closes the connection, what the client still sends is read and dropped for at most
# this long (and this much), so that closing does not reset the connection before the answer arrives.
LINGER_S = 1.0
LINGER_BYTES = 1024 * 1024
# A connection that sends nothing for this long (no request, or a request that stops halfway) is closed and
# its thread ends. Kept-alive connections are reused by the proxy in front: ingress-nginx keeps an idle
# upstream connection for 60 s, Traefik for 90 s. The limit is longer than both, so the server never closes
# a connection the proxy may still send a request on. (The test stack's nginx proxy opens one per request.)
IDLE_S = 120.0


def make_server(service: Service, host: str, port: int, idle_s: float = IDLE_S) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = idle_s  # each read and write on the connection; http.server closes it on expiry

        def log_message(self, *args):  # access logs come from the proxy in front
            pass

        def _consume_body(self) -> bool:
            """Reads and drops the request body; False when it cannot be framed or is too large to read."""
            if self.headers.get("Transfer-Encoding") is not None:
                return False
            text = self.headers.get("Content-Length")
            if text is None:
                return True
            length = decimal(text.strip(), 19)
            if length is None or length > MAX_BODY:
                return False
            while length > 0:
                chunk = self.rfile.read(min(length, 65536))
                if not chunk:
                    return False
                length -= len(chunk)
            return True

        def _linger(self) -> None:
            try:
                self.connection.shutdown(socket.SHUT_WR)
                self.connection.settimeout(LINGER_S)
                dropped = 0
                while dropped < LINGER_BYTES and (chunk := self.connection.recv(65536)):
                    dropped += len(chunk)
            except OSError:
                pass

        def _respond(self) -> None:
            # one answer per request: a body is never parsed as a request of its own
            keep_alive = self._consume_body()
            url = urlsplit(self.path)
            query = {key: values[-1] for key, values in parse_qs(url.query, keep_blank_values=True).items()}
            status, body = service.handle(self.command, url.path, query, self.headers)  # case-insensitive
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            if not keep_alive:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            self.wfile.write(data)
            if not keep_alive:
                self.wfile.flush()
                self._linger()

        do_GET = _respond  # noqa: N815 - http.server API
        do_POST = _respond  # noqa: N815
        do_PUT = _respond  # noqa: N815
        do_DELETE = _respond  # noqa: N815

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
