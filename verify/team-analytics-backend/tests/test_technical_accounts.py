"""The rules of the Team Analytics settings (the backend app's technical_accounts.py): what the settings API
accepts for the Technical accounts list, the user search and the project names lookup, and how it answers the
list. Pure functions: no Django, no ClickHouse, no Redis."""

import unittest

from cvat.apps.team_analytics import technical_accounts as rules


class AccountIdsTest(unittest.TestCase):
    def assertRefused(self, value, fragment: str) -> None:
        with self.assertRaises(rules.Refused) as caught:
            rules.clean_account_ids(value)
        self.assertIn(fragment, str(caught.exception))

    def test_a_list_of_positive_ids_is_kept_in_its_order(self):
        self.assertEqual(rules.clean_account_ids([40, 12, rules.MAX_ID]), [40, 12, rules.MAX_ID])

    def test_an_empty_list_empties_the_list(self):
        self.assertEqual(rules.clean_account_ids([]), [])

    def test_anything_but_a_list_is_refused(self):
        for value in (None, 12, "12", "12,40", {"12": True}):
            with self.subTest(value=value):
                self.assertRefused(value, "must be a list")

    def test_every_item_must_be_a_positive_integer(self):
        for item in (0, -1, 1.0, 12.5, "12", None, True, False, [12], rules.MAX_ID + 1):
            with self.subTest(item=item):
                self.assertRefused([12, item], "positive integer")

    def test_an_id_named_twice_is_refused(self):
        self.assertRefused([12, 40, 12], "user 12 is named twice")

    def test_at_most_a_thousand_accounts(self):
        self.assertEqual(len(rules.clean_account_ids(list(range(1, rules.MAX_ACCOUNTS + 1)))), 1000)
        self.assertRefused(list(range(1, rules.MAX_ACCOUNTS + 2)), "at most 1000")


class NewIdsTest(unittest.TestCase):
    def test_an_id_already_listed_is_kept_although_its_user_is_gone(self):
        rules.check_new_ids([12, 40], listed=[40], existing=[12])

    def test_a_new_id_must_be_an_existing_user(self):
        with self.assertRaises(rules.Refused) as caught:
            rules.check_new_ids([12, 77, 78], listed=[], existing=[12])
        self.assertEqual(str(caught.exception), "there is no user 77")

    def test_removing_needs_no_user(self):
        rules.check_new_ids([], listed=[40, 41], existing=[])


class SavingTest(unittest.TestCase):
    def test_changes_name_what_was_added_and_what_was_removed(self):
        self.assertEqual(rules.changes([40, 12, 7], [12, 99, 3]), ([3, 99], [7, 40]))
        self.assertEqual(rules.changes([12], [12]), ([], []))

    def test_a_live_user_is_stored_under_its_current_name_a_gone_one_under_its_last_known(self):
        names = rules.names_to_store([12, 40, 41], stored={12: "old-bot", 40: "gone-bot"},
                                     live={12: "ta-bot", 41: "new-bot"})
        self.assertEqual(names, {12: "ta-bot", 40: "gone-bot", 41: "new-bot"})


class SaveOutcomeTest(unittest.TestCase):
    """A committed save answers 200 only when the step after the commit ran and advanced the generation."""

    def test_advanced(self):
        self.assertEqual(rules.save_outcome(True), rules.SAVE_DONE)

    def test_the_advance_failed(self):
        self.assertEqual(rules.save_outcome(False), rules.SAVE_NOT_ADVANCED)

    def test_the_step_after_the_commit_never_ran(self):
        self.assertEqual(rules.save_outcome(None), rules.SAVE_NOT_ANNOUNCED)

    def test_only_an_advanced_save_is_done(self):
        self.assertEqual({rules.save_outcome(v) == rules.SAVE_DONE for v in (False, None)}, {False})


class ListingTest(unittest.TestCase):
    def test_ordered_by_name_then_id_with_live_names_and_deleted_users_marked(self):
        rows = rules.listing(stored={12: "ta-bot-old", 40: "importer", 41: "importer", 7: "zeta"},
                             live={12: "ta-bot", 41: "importer", 7: "alpha"})
        self.assertEqual(rows, [
            {"user_id": 7, "user_name": "alpha", "deleted": False},
            {"user_id": 40, "user_name": "importer", "deleted": True},
            {"user_id": 41, "user_name": "importer", "deleted": False},
            {"user_id": 12, "user_name": "ta-bot", "deleted": False},
        ])

    def test_an_empty_list(self):
        self.assertEqual(rules.listing({}, {}), [])


class SearchTest(unittest.TestCase):
    def test_absent_or_empty_searches_for_anyone(self):
        self.assertEqual(rules.clean_search(None), "")
        self.assertEqual(rules.clean_search(""), "")

    def test_up_to_150_characters(self):
        self.assertEqual(rules.clean_search("a" * 150), "a" * 150)
        with self.assertRaises(rules.Refused):
            rules.clean_search("a" * 151)


class ProjectIdsTest(unittest.TestCase):
    def test_ids_separated_by_commas_duplicates_once(self):
        self.assertEqual(rules.clean_project_ids("4,8,9,4"), [4, 8, 9])

    def test_absent_or_empty_names_no_project(self):
        self.assertEqual(rules.clean_project_ids(None), [])
        self.assertEqual(rules.clean_project_ids(""), [])

    def test_only_positive_ids_in_ascii_digits(self):
        for value in ("0", "-1", "4,", ",4", "4,,8", "4 ,8", "a", "1.5", "٣", "²", "9" * 20,
                      str(rules.MAX_ID + 1), "1" * 5000):
            with self.subTest(value=value[:30]):
                with self.assertRaises(rules.Refused):
                    rules.clean_project_ids(value)

    def test_at_most_500_ids(self):
        self.assertEqual(len(rules.clean_project_ids(",".join(map(str, range(1, 501))))), 500)
        with self.assertRaises(rules.Refused):
            rules.clean_project_ids(",".join(map(str, range(1, 502))))
