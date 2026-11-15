"""The HTTP interface: one answer per request, also on a kept-alive connection that carries a request body."""

import socket
import threading
import time
from urllib.parse import urlsplit

from team_analytics.http_server import make_server
from tests.support import FakeUser, StackTestCase

PATH = "/team-analytics-api/v1/overview"


class RequestBodyTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.cvat.add_user("attacker", FakeUser(5, "attacker", memberships={"org7": (7, "maintainer", True)}))

    def exchange(self, data: bytes) -> bytes:
        """Sends `data` on one connection and returns everything the service sends back until it closes or idles."""
        address = urlsplit(self.stack.url)
        with socket.create_connection((address.hostname, address.port), timeout=5) as connection:
            connection.sendall(data)
            received = b""
            connection.settimeout(3)
            try:
                while chunk := connection.recv(65536):
                    received += chunk
            except TimeoutError:
                pass
        return received

    @staticmethod
    def hidden_request() -> bytes:
        # answered at once (no such endpoint), so a second answer would arrive well within the wait
        return b"GET /team-analytics-api/v1/no-such-endpoint HTTP/1.1\r\nHost: x\r\nCookie: sessionid=attacker\r\n\r\n"

    def assertOneAnswer(self, received: bytes, status: int) -> None:
        self.assertEqual(received.count(b"HTTP/1.1 "), 1, received[:400])
        self.assertTrue(received.startswith(f"HTTP/1.1 {status} ".encode()), received[:200])

    def test_a_body_that_is_itself_a_request_gets_no_answer_of_its_own(self):
        for method, status in (("POST", 405), ("GET", 401), ("DELETE", 405)):
            with self.subTest(method=method):
                body = self.hidden_request()
                head = f"{method} {PATH}?org=org7 HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\n\r\n"
                self.assertOneAnswer(self.exchange(head.encode() + body), status)

    def test_a_chunked_or_unreadable_body_closes_the_connection_after_one_answer(self):
        body = self.hidden_request()
        for header in ("Transfer-Encoding: chunked", "Content-Length: many", f"Content-Length: {10**9}"):
            with self.subTest(header=header):
                chunked = f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n\r\n"
                head = f"POST {PATH}?org=org7 HTTP/1.1\r\nHost: x\r\n{header}\r\n\r\n".encode()
                self.assertOneAnswer(self.exchange(head + (chunked if "chunked" in header else body)), 405)

    def test_requests_without_a_body_still_share_one_connection(self):
        request = self.hidden_request()
        received = self.exchange(request + request)
        self.assertEqual(received.count(b"HTTP/1.1 404 "), 2, received[:400])


def connection_threads() -> set[threading.Thread]:
    """The threads HTTP servers in this process run, one per open connection."""
    return {thread for thread in threading.enumerate() if "process_request_thread" in thread.name}


class IdleConnectionTest(StackTestCase):
    """A connection that sends nothing, or stops halfway, is closed after the idle limit and its thread ends."""

    IDLE_S = 1.0

    def setUp(self) -> None:
        super().setUp()
        http = make_server(self.stack.service, "127.0.0.1", 0, idle_s=self.IDLE_S)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        self.addCleanup(http.server_close)
        self.addCleanup(http.shutdown)
        self.address = ("127.0.0.1", http.server_address[1])

    def connect(self, data: bytes) -> socket.socket:
        connection = socket.create_connection(self.address, timeout=5)
        self.addCleanup(connection.close)
        connection.sendall(data)
        return connection

    def test_silent_half_sent_and_idle_kept_alive_connections_are_closed_and_their_threads_end(self):
        before = connection_threads()
        request = b"GET /team-analytics-api/v1/no-such-endpoint HTTP/1.1\r\nHost: x\r\n"
        connections = {
            "silent": self.connect(b""),
            "half a request": self.connect(request),
            "idle after an answer": self.connect(request + b"\r\n"),
        }
        time.sleep(0.3)
        mine = connection_threads() - before
        self.assertEqual(len(mine), 3)
        started = time.monotonic()
        for name, connection in connections.items():
            with self.subTest(connection=name):
                received = b""
                while chunk := connection.recv(65536):  # ends when the server closes; times out (5 s) otherwise
                    received += chunk
                if name == "idle after an answer":
                    self.assertTrue(received.startswith(b"HTTP/1.1 404 "), received[:200])
                    self.assertNotIn(b"Connection: close", received)  # kept alive until the limit
                else:
                    self.assertEqual(received, b"")
        self.assertLess(time.monotonic() - started, self.IDLE_S + 2)
        for thread in mine:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive(), thread.name)

    def test_a_connection_in_use_is_not_closed_before_the_idle_limit(self):
        request = b"GET /team-analytics-api/v1/no-such-endpoint HTTP/1.1\r\nHost: x\r\n\r\n"
        connection = self.connect(request)
        for _ in range(3):
            time.sleep(self.IDLE_S / 2)
            connection.sendall(request)
        time.sleep(0.3)
        connection.settimeout(0.5)
        received = b""
        try:
            while chunk := connection.recv(65536):
                received += chunk
        except TimeoutError:
            pass
        self.assertEqual(received.count(b"HTTP/1.1 404 "), 4, received[:600])
