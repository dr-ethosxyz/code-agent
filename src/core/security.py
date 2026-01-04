"""Shared security utilities for webhook signature verification."""

import hashlib
import hmac
import time

from src.config import settings
from src.core.exceptions import SignatureVerificationError
from src.core.logging import get_logger

logger = get_logger("security")


def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256.

    Args:
        payload: Raw request body bytes
        signature: X-Hub-Signature-256 header value

    Returns:
        True if valid, False otherwise
    """
    if not settings.github_webhook_secret:
        logger.warning("No GitHub webhook secret configured, skipping verification")
        return True

    expected = hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    expected_signature = f"sha256={expected}"
    return hmac.compare_digest(expected_signature, signature)


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack request signature using HMAC-SHA256.

    Args:
        body: Raw request body bytes
        timestamp: X-Slack-Request-Timestamp header value
        signature: X-Slack-Signature header value

    Returns:
        True if valid, False otherwise
    """
    if not settings.slack_signing_secret:
        logger.warning("No Slack signing secret configured, skipping verification")
        return True

    # Check timestamp to prevent replay attacks
    current_time = int(time.time())
    try:
        request_time = int(timestamp)
    except (ValueError, TypeError):
        logger.warning("Invalid Slack timestamp format")
        return False

    if abs(current_time - request_time) > 300:
        logger.warning("Slack request timestamp too old")
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected = (
        "v0="
        + hmac.new(
            settings.slack_signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(expected, signature)


def require_github_signature(payload: bytes, signature: str) -> None:
    """Verify GitHub signature or raise exception.

    Args:
        payload: Raw request body bytes
        signature: X-Hub-Signature-256 header value

    Raises:
        SignatureVerificationError: If signature is invalid
    """
    if not verify_github_signature(payload, signature):
        logger.warning("Invalid GitHub webhook signature")
        raise SignatureVerificationError("GitHub webhook")


def require_slack_signature(body: bytes, timestamp: str, signature: str) -> None:
    """Verify Slack signature or raise exception.

    Args:
        body: Raw request body bytes
        timestamp: X-Slack-Request-Timestamp header value
        signature: X-Slack-Signature header value

    Raises:
        SignatureVerificationError: If signature is invalid
    """
    if not verify_slack_signature(body, timestamp, signature):
        logger.warning("Invalid Slack signature")
        raise SignatureVerificationError("Slack request")
