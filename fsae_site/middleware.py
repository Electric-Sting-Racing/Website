from django.conf import settings
from django.http import HttpResponse

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=()"
)


def build_csp():
    """Content Security Policy for public pages. The site uses no inline scripts or styles."""
    directives = {
        "default-src": "'self'",
        "script-src": "'self'",
        "style-src": " ".join(["'self'", *settings.CSP_STYLE_HOSTS]),
        "font-src": " ".join(["'self'", *settings.CSP_FONT_HOSTS]),
        # Roster photos, sponsor logos and gallery images are admin-entered https URLs.
        "img-src": "'self' data: https:",
        "connect-src": "'self'",
        "media-src": "'self'",
        "object-src": "'none'",
        "base-uri": "'self'",
        "form-action": "'self'",
        "frame-ancestors": "'none'",
    }
    policy = "; ".join(f"{name} {value}" for name, value in directives.items())
    if not settings.DEBUG:
        policy += "; upgrade-insecure-requests"
    return policy


# Django's admin still ships a few inline styles and scripts, so it only gets the directives
# that cannot break it.
ADMIN_CSP = "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"


class SecurityHeadersMiddleware:
    """Adds Content-Security-Policy and Permissions-Policy to every response, including static files."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # DATA_UPLOAD_MAX_MEMORY_SIZE ignores uploaded file parts, and nothing on this site accepts
        # files, so refuse any body that declares itself larger than the limit.
        try:
            declared = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            declared = 0
        if declared > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
            response = HttpResponse("Request too large.", status=413, content_type="text/plain")
        else:
            response = self.get_response(request)
        if request.path.startswith("/admin/"):
            policy, header = ADMIN_CSP, "Content-Security-Policy"
        else:
            header = (
                "Content-Security-Policy-Report-Only"
                if settings.CSP_REPORT_ONLY
                else "Content-Security-Policy"
            )
            policy = build_csp()
        response.headers.setdefault(header, policy)
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        return response
