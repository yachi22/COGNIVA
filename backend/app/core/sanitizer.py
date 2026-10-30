import re
from typing import Any, Dict, List, Union

# Regex patterns for sensitive credentials and tokens
SENSITIVE_PATTERNS = [
    # Bearer tokens and JWTs
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{15,}"), r"\1[REDACTED]"),
    # OpenAI API Keys
    (re.compile(r"(sk-[A-Za-z0-9_\-]{4})[A-Za-z0-9_\-]{16,}"), r"\1...[REDACTED]"),
    # Database connection passwords in URLs (e.g. postgresql://user:pass@host:5432)
    (re.compile(r"(:\/\/[^:]+:)[^@]+(@)"), r"\1***\2"),
    # URL encoded and query-string passwords
    (re.compile(r"(?i)(password|passwd|pwd|secret|access_token|api_key|apikey|secret_key)(=|:\s*)(?:['\"][^'\"]*['\"]|[^\s,;&'\"]+)"), r"\1\2[REDACTED]"),
    # Authorization header formats
    (re.compile(r"(?i)(authorization:\s*)(basic|bearer|token)\s+(?:['\"][^'\"]*['\"]|[^\s,;&'\"]+)"), r"\1\2 [REDACTED]"),
]

SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "secret_key",
    "access_token",
    "refresh_token",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "openai_api_key",
    "s3_secret_access_key",
    "database_url",
    "async_database_url",
    "sync_database_url",
}


def sanitize_log_message(message: str, max_length: int = 2000) -> str:
    """
    Sanitizes string log messages, redacting sensitive credentials and capping length.
    """
    if not message:
        return ""
    text = str(message)
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    if len(text) > max_length:
        text = text[:max_length] + " ... [TRUNCATED]"
    return text


def sanitize_error_detail(detail: Any, max_length: int = 500) -> str:
    """
    Sanitizes exception messages or error details to guarantee safe bounded reporting.
    """
    if not detail:
        return ""
    text = str(detail).splitlines()[0] if str(detail).splitlines() else str(detail)
    sanitized = sanitize_log_message(text, max_length=max_length)
    return sanitized


def sanitize_dictionary(data: Dict[str, Any], max_depth: int = 3) -> Dict[str, Any]:
    """
    Recursively sanitizes dictionary payloads, replacing sensitive keys and redacting values.
    """
    if max_depth <= 0 or not isinstance(data, dict):
        return {}

    sanitized: Dict[str, Any] = {}
    for key, value in data.items():
        lower_key = str(key).lower()
        if any(s in lower_key for s in SENSITIVE_KEYS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dictionary(value, max_depth=max_depth - 1)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dictionary(item, max_depth=max_depth - 1)
                if isinstance(item, dict)
                else (sanitize_log_message(str(item)) if isinstance(item, str) else item)
                for item in value[:20]  # Bound list items
            ]
        elif isinstance(value, str):
            sanitized[key] = sanitize_log_message(value, max_length=500)
        else:
            sanitized[key] = value

    return sanitized

