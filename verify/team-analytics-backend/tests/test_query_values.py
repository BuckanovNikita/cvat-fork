"""Identifiers, page numbers and months in the query: only ASCII decimal digits are accepted, anything else is 400."""

from tests.support import FakeUser, StackTestCase

API = "/api/team-analytics/"

# Unicode digits: '²' is a digit Python's int() refuses, '٣' (Arabic-Indic three) one it reads as 3.
NOT_ASCII = ("²", "٣", "1٣")


class QueryValuesTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", memberships={"org7": (7, "maintainer", True)}))

    def assertBadRequest(self, endpoint: str, **query) -> None:
        status, body = self.stack.get(API + endpoint, "lead", org="org7", **query)
        self.assertEqual((status, body.get("error")), (400, "bad_request"), (endpoint, query, body))

    def test_filters_with_non_ascii_digits_are_bad_requests_on_every_endpoint(self):
        for endpoint in ("overview", "details", "list?by=annotators", "trends"):
            for key in ("project", "annotator"):
                for value in NOT_ASCII:
                    with self.subTest(endpoint=endpoint, key=key, value=value):
                        path, _, by = endpoint.partition("?by=")
                        self.assertBadRequest(path, **({"by": by} if by else {}), **{key: value})

    def test_pages_and_ids_with_non_ascii_digits_are_bad_requests(self):
        for value in NOT_ASCII:
            with self.subTest(value=value):
                self.assertBadRequest("details", page=value)
                self.assertBadRequest("details", by="projects", ids=f"1,{value}")
                self.assertBadRequest("trends", ids=f"1,{value}")

    def test_a_month_with_non_ascii_digits_or_a_trailing_newline_is_a_bad_request(self):
        for month in ("٢٠٢٦-١١", "2026-1٣", "2026-11\n"):
            with self.subTest(month=month):
                self.assertBadRequest("overview", period="month", month=month)

    def test_ascii_identifiers_are_still_accepted(self):
        for endpoint, query in (("overview", {"project": "0", "annotator": "12"}), ("details", {"page": "2"}),
                                ("details", {"by": "projects", "ids": "1,2"}), ("trends", {"ids": "3"}),
                                ("overview", {"period": "month", "month": "2026-11"})):
            with self.subTest(endpoint=endpoint, query=query):
                status, body = self.stack.get(API + endpoint, "lead", org="org7", **query)
                self.assertEqual(status, 200, body)
