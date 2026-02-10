"""URL signature generation and verification for favorite/notes action links."""
import hmac
import hashlib
import os


def generate_signature(content_id: str, date: str, secret_key: str | None = None) -> str:
    """Generate HMAC-SHA256 signature for action URLs.

    Args:
        content_id: Unique content identifier (e.g., "github-torvalds-linux")
        date: Content date string (e.g., "2024-02-10")
        secret_key: Secret key for signing (defaults to SECRET_KEY env var)

    Returns:
        16-character hex signature string

    Example:
        >>> generate_signature("github-torvalds-linux", "2024-02-10", "my-secret")
        'a1b2c3d4e5f67890'
    """
    key = secret_key or os.environ.get("SECRET_KEY", "")
    if not key:
        raise ValueError("Secret key required. Set SECRET_KEY environment variable.")

    message = f"{content_id}:{date}"
    signature = hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:16]

    return signature


def verify_signature(content_id: str, date: str, signature: str, secret_key: str | None = None) -> bool:
    """Verify URL signature.

    Args:
        content_id: Unique content identifier
        date: Content date string
        signature: Signature to verify
        secret_key: Secret key for verification (defaults to SECRET_KEY env var)

    Returns:
        True if signature is valid, False otherwise

    Example:
        >>> verify_signature("github-torvalds-linux", "2024-02-10", "a1b2c3d4e5f67890", "my-secret")
        True
    """
    try:
        expected = generate_signature(content_id, date, secret_key)
        return hmac.compare_digest(expected, signature)
    except ValueError:
        return False


def generate_action_url(
    base_url: str,
    action: str,
    content_id: str,
    title: str,
    url: str,
    content_type: str,
    date: str,
    secret_key: str | None = None,
) -> str:
    """Generate complete action URL with signature.

    Args:
        base_url: Base URL of the web interface (e.g., "https://username.github.io/ai-digest")
        action: Action type ("star" or "note")
        content_id: Unique content identifier
        title: Content title
        url: Original content URL
        content_type: Content type (github, arxiv, huggingface, blog)
        date: Content date
        secret_key: Secret key for signing

    Returns:
        Complete signed URL

    Example:
        >>> generate_action_url(
        ...     "https://user.github.io/ai-digest",
        ...     "star",
        ...     "github-torvalds-linux",
        ...     "linux",
        ...     "https://github.com/torvalds/linux",
        ...     "github",
        ...     "2024-02-10",
        ...     "my-secret"
        ... )
        'https://user.github.io/ai-digest/star?id=...&t=...'
    """
    signature = generate_signature(content_id, date, secret_key)

    # URL encode parameters
    from urllib.parse import quote

    params = {
        "id": content_id,
        "title": quote(title, safe=""),
        "url": quote(url, safe=""),
        "type": content_type,
        "date": date,
        "t": signature,
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{base_url}/{action}?{query_string}"
