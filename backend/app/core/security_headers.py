from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces enterprise defense-in-depth HTTP security headers
    on all API responses to protect against clickjacking, MIME sniffing,
    cross-site scripting, and unauthorized framing.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # 1. Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Prevent clickjacking by disallowing framing
        response.headers["X-Frame-Options"] = "DENY"

        # 3. Modern XSS filter directive
        response.headers["X-XSS-Protection"] = "0"

        # 4. Enforce strict HTTPS transport security
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # 5. Strict referrer policy to prevent URL leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 6. Restrict browser feature permissions
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # 7. Content Security Policy for API JSON endpoints
        if not response.headers.get("Content-Security-Policy"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"

        return response

