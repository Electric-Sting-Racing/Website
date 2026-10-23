from django.conf import settings
from django.http import HttpResponse

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=()"
)


def build_csp():
    """Content Security Policy for every page, including /admin/.

    Neither the site nor Django's admin uses inline scripts, inline styles or event handlers.
    """
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


# Always enforced on /admin/, even while a policy is being tried in report-only mode.
ADMIN_BASELINE_CSP = "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"


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
        policy = build_csp()
        if settings.CSP_REPORT_ONLY:
            response.headers.setdefault("Content-Security-Policy-Report-Only", policy)
            if request.path.startswith("/admin/"):
                response.headers.setdefault("Content-Security-Policy", ADMIN_BASELINE_CSP)
        else:
            response.headers.setdefault("Content-Security-Policy", policy)
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        return response
