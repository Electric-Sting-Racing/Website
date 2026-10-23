from django.contrib import admin

from .models import LoginFailure


@admin.register(LoginFailure)
class LoginFailureAdmin(admin.ModelAdmin):
    """Read-only record of recent failed sign-ins, for spotting password guessing."""

    list_display = ("created_at", "username")
    search_fields = ("username",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
