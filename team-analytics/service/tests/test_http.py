"""The HTTP interface: one answer per request, also on a kept-alive connection that carries a request body."""

import socket
from urllib.parse import urlsplit

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
