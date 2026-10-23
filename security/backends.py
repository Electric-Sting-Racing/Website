import logging

from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied

from . import lockout

logger = logging.getLogger(__name__)


class LockoutBackend(ModelBackend):
    """Password sign-in that refuses everyone, even a correct password, while locked out."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(self.UserModel.USERNAME_FIELD)
        lockout.purge_old_failures()
        if lockout.is_locked(username, request):
            logger.warning("Sign-in refused for %r: too many recent failures", lockout.normalize(username))
            # Django treats PermissionDenied as "stop trying other backends".
            raise PermissionDenied("locked out")
        return super().authenticate(request, username=username, password=password, **kwargs)
