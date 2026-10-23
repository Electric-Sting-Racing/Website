from django.apps import AppConfig
from django.db.models.signals import post_migrate


class SecurityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "security"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_login_failed

        from . import signals

        user_login_failed.connect(signals.on_login_failed, dispatch_uid="security.login_failed")
        user_logged_in.connect(signals.on_logged_in, dispatch_uid="security.logged_in")
        post_migrate.connect(signals.sync_editor_group, dispatch_uid="security.editor_group")
