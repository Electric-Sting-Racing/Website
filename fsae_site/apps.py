from django.contrib.admin.apps import AdminConfig


class SiteAdminConfig(AdminConfig):
    """Replaces django.contrib.admin so /admin/ uses the site with sign-in codes (admin_site.py)."""

    default_site = "fsae_site.admin_site.SiteAdmin"
