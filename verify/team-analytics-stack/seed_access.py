# Loaded into the stack's backend with `python manage.py shell` (run.sh seed-access).
# Creates the accounts of the access cases (access_accounts.json, passed in TA_ACCOUNTS); safe to
# run again. Unlike seed_users.py, the global group and the superuser flag are set apart, so an
# administrator by group who is not a superuser exists. Every run makes the membership that the
# removed-member case deletes active again.
import json
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from cvat.apps.organizations.models import Membership, Organization

User = get_user_model()
PASSWORD = os.environ["TA_SEED_PASSWORD"]
ACCOUNTS = json.loads(os.environ["TA_ACCOUNTS"])

for username, spec in ACCOUNTS["users"].items():
    user, _ = User.objects.get_or_create(username=username)
    user.email = f"{username}@example.com"
    user.first_name = username
    user.is_active = True
    user.is_superuser = spec["superuser"]
    user.is_staff = spec["superuser"]
    user.set_password(PASSWORD)
    user.save()
    user.groups.set([Group.objects.get_or_create(name=spec["group"])[0]])
    try:
        from allauth.account.models import EmailAddress

        EmailAddress.objects.update_or_create(
            user=user, email=user.email, defaults={"verified": True, "primary": True}
        )
    except ImportError:
        pass

for slug, spec in ACCOUNTS["organizations"].items():
    members = spec["members"]
    owner = User.objects.get(username=next(u for u, r in members.items() if r == "owner"))
    org, _ = Organization.objects.update_or_create(
        slug=slug, defaults={"name": spec["name"], "owner": owner}
    )
    for username, role in members.items():
        Membership.objects.update_or_create(
            user=User.objects.get(username=username),
            organization=org,
            defaults={"role": role, "is_active": True, "joined_date": timezone.now()},
        )

print("seeded access-case users:", ", ".join(ACCOUNTS["users"]), "| organizations:", ", ".join(ACCOUNTS["organizations"]))
