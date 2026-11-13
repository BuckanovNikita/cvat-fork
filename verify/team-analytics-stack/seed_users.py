# Loaded into the stack's backend with `python manage.py shell` (run.sh seed).
# Creates the accounts, organizations and memberships of accounts.json (passed in
# TA_ACCOUNTS); safe to run again. stack_api.py reads them back through the CVAT API.
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
    is_admin = spec["admin"]
    user, _ = User.objects.get_or_create(username=username)
    user.email = f"{username}@example.com"
    user.first_name = username
    user.is_active = True
    user.is_superuser = is_admin
    user.is_staff = is_admin
    user.set_password(PASSWORD)
    user.save()
    user.groups.set([Group.objects.get_or_create(name="admin" if is_admin else "user")[0]])
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

print("seeded users:", ", ".join(ACCOUNTS["users"]), "| organizations:", ", ".join(ACCOUNTS["organizations"]))
