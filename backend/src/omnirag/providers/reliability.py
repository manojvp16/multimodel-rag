"""Bounded retries and safe diagnostics for external model operations."""
import logging
import random
import time
from uuid import uuid4

import httpx
from google.genai.errors import APIError

try:
    import httpx2
    TRANSPORT_ERRORS = (httpx.TransportError, httpx2.TransportError, TimeoutError, ConnectionError)
except ImportError:
    TRANSPORT_ERRORS = (httpx.TransportError, TimeoutError, ConnectionError)

logger = logging.getLogger(__name__)


class InvalidModelResponse(ValueError):
    """The model returned missing or malformed structured output."""


class ProviderFailure(RuntimeError):
    def __init__(self, operation, code, message, status, retryable, attempts, retry_after=None):
        super().__init__(message)
        self.operation = operation
        self.code = code
        self.status = status
        self.retryable = retryable
        self.attempts = attempts
        self.retry_after = retry_after
        self.reference = uuid4().hex[:12]


def classify_failure(exc):
    if isinstance(exc, InvalidModelResponse):
        return ('invalid_model_response', 'Gemini returned an empty or invalid answer. Please retry.', 502, True)
    if isinstance(exc, APIError):
        if exc.code == 429:
            return ('provider_rate_limit', 'Gemini request limits or quota were reached. Wait before retrying; if this persists, check your Gemini quota.', 429, True)
        if exc.code in {500, 502, 503, 504, 408}:
            return ('provider_unavailable', 'Gemini is temporarily unavailable or timed out. Please retry shortly.', 503, True)
        if exc.code in {401, 403}:
            return ('provider_access_denied', 'Gemini rejected access. Check the API key and model permissions in backend/.env.', 503, False)
        if exc.code in {400, 404}:
            return ('provider_configuration', 'Gemini rejected the configured model or request. Check model availability and backend settings.', 503, False)
        return ('provider_error', 'Gemini could not complete this request. Check the server log using the error reference.', 502, False)
    if isinstance(exc, TRANSPORT_ERRORS):
        return ('provider_connection', 'The server could not reach Gemini or the connection timed out. Check its network connection and retry.', 503, True)
    return None


def retry_delay(exc):
    headers = getattr(getattr(exc, 'response', None), 'headers', {}) or {}
    try:
        value = float(headers.get('retry-after', 0))
        return max(0, value) if value < float('inf') else 0
    except (TypeError, ValueError):
        return 0


def call_provider(operation, callback):
    """Three total attempts; at most two for invalid structured output.

    Long Retry-After values are returned to the caller instead of blocking a
    worker or sending requests before the provider allows them.
    """
    for attempt in range(1, 4):
        try:
            return callback()
        except Exception as exc:
            category = classify_failure(exc)
            if category is None:
                raise
            code, message, status, retryable = category
            retry_after = retry_delay(exc)
            limit = 2 if isinstance(exc, InvalidModelResponse) else 3
            if not retryable or attempt >= limit or retry_after > 8:
                failure = ProviderFailure(operation, code, message, status, retryable, attempt, retry_after or None)
                logger.warning('Provider failure reference=%s operation=%s category=%s attempts=%s status=%s',
                               failure.reference, operation, code, attempt, getattr(exc, 'code', None))
                raise failure from exc
            delay = max(retry_after, min(2 ** (attempt - 1) + random.uniform(0, .25), 8))
            logger.info('Retrying provider operation=%s category=%s attempt=%s delay=%.2f', operation, code, attempt, delay)
            time.sleep(delay)
