# SPDX-License-Identifier: MIT

"""What the settings actions of the view set accept: the body of `PUT settings` and the query of
`GET settings/users` and `GET project-names`. The rules themselves are in technical_accounts.py."""

from rest_framework import serializers

from . import technical_accounts as rules

# The code of an error whose message is a rule's own sentence (it names what it refuses).
REFUSED = "refused"


def _check(rule, value):
    try:
        return rule(value)
    except rules.Refused as error:
        raise serializers.ValidationError(str(error), code=REFUSED) from error


class TechnicalAccountsWriteSerializer(serializers.Serializer):
    """`{"technical_accounts": [12, 40]}`: the whole list, by user id."""

    technical_accounts = serializers.JSONField()

    def validate_technical_accounts(self, value):
        return _check(rules.clean_account_ids, value)


class UserSearchSerializer(serializers.Serializer):
    """`?search=<text>`: part of a username, first name or last name; absent or empty finds anyone."""

    search = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, default=""
    )

    def validate_search(self, value):
        return _check(rules.clean_search, value)


class ProjectNamesSerializer(serializers.Serializer):
    """`?ids=4,8,9`: project ids separated by commas."""

    ids = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False, default="")

    def validate_ids(self, value):
        return _check(rules.clean_project_ids, value)


def first_error(errors) -> str:
    """One sentence out of a serializer's errors, for the `detail` of a 400 answer: a rule's sentence
    as it is, one of DRF's own after the name of its field."""
    field, error = _first(errors, None)
    if getattr(error, "code", None) == REFUSED or field in (None, "non_field_errors"):
        return str(error)
    return f"{field}: {error}"


def _first(errors, field):
    if isinstance(errors, dict) and errors:
        name, nested = next(iter(errors.items()))
        return _first(nested, name if field is None else field)
    if isinstance(errors, list) and errors:
        return _first(errors[0], field)
    return field, errors
