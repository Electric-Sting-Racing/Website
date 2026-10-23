import ipaddress

from django.conf import settings
from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django_otp.admin import OTPAdminAuthenticationForm, OTPAdminSite
from django_otp.plugins.otp_totp.models import TOTPDevice


def client_ip(request):
    """Address used to key sign-in lockouts.

    Gunicorn sits behind Nginx, which overwrites X-Real-IP with $remote_addr; REMOTE_ADDR inside the
    container is only the Docker gateway. X-Forwarded-For is deliberately ignored because a client can
    send it. Anything that is not an IP address falls back to REMOTE_ADDR.
    """
    value = request.META.get("HTTP_X_REAL_IP", "").strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return request.META.get("REMOTE_ADDR")


class OTPLoginForm(OTPAdminAuthenticationForm):
    def _chosen_device(self, user):
        # django-otp 1.7 wants a device picked explicitly. Default to the user's confirmed
        # authenticator so username, password and code go in with one submission.
        device = super()._chosen_device(user)
        if device is None:
            device = TOTPDevice.objects.devices_for_user(user, confirmed=True).first()
        return device


class SiteAdmin(OTPAdminSite):
    """The admin site. Requires an authenticator code unless DJANGO_ADMIN_REQUIRE_OTP is false."""

    def __init__(self, name="admin"):
        # OTPAdminSite defaults to the name "otpadmin"; the URLs and templates expect "admin".
        super().__init__(name)

    @property
    def login_form(self):
        return OTPLoginForm if settings.ADMIN_REQUIRE_OTP else AdminAuthenticationForm

    @property
    def login_template(self):
        return OTPAdminSite.login_template if settings.ADMIN_REQUIRE_OTP else None

    def has_permission(self, request):
        if settings.ADMIN_REQUIRE_OTP:
            return super().has_permission(request)
        return AdminSite.has_permission(self, request)
