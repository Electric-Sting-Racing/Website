from django.db import models


class LoginFailure(models.Model):
    """One failed sign-in attempt, kept briefly to lock out password guessing."""

    username = models.CharField(max_length=150, db_index=True)
    # Salted hash of the client address; the address itself is never stored.
    ip_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "failed sign-in"
        verbose_name_plural = "failed sign-ins"

    def __str__(self):
        return f"{self.username} at {self.created_at:%Y-%m-%d %H:%M}"
