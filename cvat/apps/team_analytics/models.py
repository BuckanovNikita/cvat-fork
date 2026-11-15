# SPDX-License-Identifier: MIT

"""What Team Analytics keeps in Postgres: the Technical accounts list (technical_accounts.py)."""

from django.db import models


class TechnicalAccount(models.Model):
    """An account that stands for an automated process: its figures are no annotator's.

    Kept by user id with no foreign key to the user table: a user deleted from CVAT stays on the
    list, under its last known name, until someone removes it."""

    user_id = models.PositiveBigIntegerField(primary_key=True)
    # the last known user name; as long as Django's username
    user_name = models.CharField(max_length=150)
    updated_date = models.DateTimeField(auto_now=True)
