import hashlib
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginFailure

KEEP_FAILURES_FOR = timedelta(days=1)


def client_ip(request):
    """Client address. Only trust a proxy header when SECURITY_CLIENT_IP_HEADER names one."""
    if request is None:
        return ""
    header = settings.SECURITY_CLIENT_IP_HEADER
    if header:
        value = request.META.get("HTTP_" + header.upper().replace("-", "_"), "")
        # The last entry is the one our own proxy appended; earlier ones are client-supplied.
        if value:
            return value.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def ip_hash(request):
    return hashlib.sha256(f"{settings.SECRET_KEY}:{client_ip(request)}".encode()).hexdigest()


def normalize(username):
    return (username or "").strip().lower()[:150]


def _recent(**filters):
    since = timezone.now() - timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    return LoginFailure.objects.filter(created_at__gte=since, **filters)


def is_locked(username, request):
    """True when this username or this client has failed too often recently."""
    username = normalize(username)
    if username and _recent(username=username).count() >= settings.LOGIN_MAX_FAILURES_PER_USER:
        return True
    return _recent(ip_hash=ip_hash(request)).count() >= settings.LOGIN_MAX_FAILURES_PER_IP


def purge_old_failures():
    """Drop records past the retention period. Runs on every sign-in attempt, successful or not."""
    LoginFailure.objects.filter(created_at__lt=timezone.now() - KEEP_FAILURES_FOR).delete()


def record_failure(username, request):
    LoginFailure.objects.create(username=normalize(username), ip_hash=ip_hash(request))


def clear_failures(username):
    LoginFailure.objects.filter(username=normalize(username)).delete()
