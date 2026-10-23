from django.apps import apps
from django.contrib.auth.models import Group, Permission

from . import lockout

EDITOR_GROUP = "Content editors"
# Site content apps whose models editors may manage in the admin.
EDITOR_APPS = ("team", "news")
# Models editors can read and update but never create or delete (they are visitor messages).
EDITOR_UPDATE_ONLY = {"inquiry"}


def on_login_failed(sender, credentials, request=None, **kwargs):
    username = credentials.get("username", "")
    # Failures during a lockout are not counted, so retrying cannot extend it.
    if not lockout.is_locked(username, request):
        lockout.record_failure(username, request)


def on_logged_in(sender, request, user, **kwargs):
    lockout.clear_failures(user.get_username())


def sync_editor_group(sender=None, **kwargs):
    """Keep a 'Content editors' group with rights over site content only (no users, no groups).

    Runs after every migrate and is idempotent, so models added by later releases are picked up.
    """
    wanted = []
    for app_label in EDITOR_APPS:
        try:
            models = apps.get_app_config(app_label).get_models()
        except LookupError:
            continue
        for model in models:
            name = model._meta.model_name
            if name in EDITOR_UPDATE_ONLY:
                actions = ["view", "change"]
            else:
                actions = ["add", "change", "delete", "view"]
            wanted += [f"{action}_{name}" for action in actions]
    permissions = Permission.objects.filter(
        content_type__app_label__in=EDITOR_APPS, codename__in=wanted
    )
    group, _ = Group.objects.get_or_create(name=EDITOR_GROUP)
    group.permissions.set(permissions)
