from types import SimpleNamespace

import httpx
import pytest
from google.genai.errors import APIError

from omnirag.providers import reliability as provider


@pytest.fixture
def delays(monkeypatch):
    values = []
    monkeypatch.setattr(provider.time, 'sleep', values.append)
    monkeypatch.setattr(provider.random, 'uniform', lambda *args: 0)
    return values


def test_transient_failure_recovers_with_bounded_backoff(delays):
    calls = []
    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise APIError(503, {'error': {'message': 'busy'}})
        return 'answer'
    assert provider.call_provider('answer_generation', operation) == 'answer'
    assert len(calls) == 3 and delays == [1, 2]


def test_rate_limit_reports_safe_diagnostics_after_three_attempts(delays, caplog):
    def operation():
        raise APIError(429, {'error': {'message': 'sensitive provider body'}})
    with pytest.raises(provider.ProviderFailure) as result:
        provider.call_provider('query_embedding', operation)
    error = result.value
    assert error.code == 'provider_rate_limit' and error.status == 429
    assert error.attempts == 3 and error.retryable
    assert error.reference in caplog.text
    assert 'sensitive provider body' not in caplog.text
    assert delays == [1, 2]


@pytest.mark.parametrize('status,code', [(401, 'provider_access_denied'), (403, 'provider_access_denied'), (400, 'provider_configuration'), (404, 'provider_configuration')])
def test_permanent_errors_are_not_retried(delays, status, code):
    def operation():
        raise APIError(status, {'error': {'message': 'rejected'}})
    with pytest.raises(provider.ProviderFailure) as result:
        provider.call_provider('answer_generation', operation)
    assert result.value.code == code
    assert not result.value.retryable and result.value.attempts == 1
    assert delays == []


def test_long_retry_after_does_not_retry_prematurely(delays):
    def operation():
        error = APIError(429, {'error': {'message': 'busy'}})
        error.response = SimpleNamespace(headers={'retry-after': '60'})
        raise error
    with pytest.raises(provider.ProviderFailure) as result:
        provider.call_provider('answer_generation', operation)
    assert result.value.retry_after == 60 and result.value.attempts == 1
    assert delays == []


def test_malformed_answers_retry_only_once(delays):
    def operation():
        raise provider.InvalidModelResponse('invalid JSON')
    with pytest.raises(provider.ProviderFailure) as result:
        provider.call_provider('answer_generation', operation)
    assert result.value.code == 'invalid_model_response'
    assert result.value.attempts == 2 and delays == [1]


def test_connection_timeout_is_classified(delays):
    def operation():
        raise httpx.ReadTimeout('timeout')
    with pytest.raises(provider.ProviderFailure) as result:
        provider.call_provider('query_embedding', operation)
    assert result.value.code == 'provider_connection' and result.value.attempts == 3


def test_programming_errors_are_not_retried(delays):
    def operation():
        raise TypeError('implementation bug')
    with pytest.raises(TypeError):
        provider.call_provider('answer_generation', operation)
    assert delays == []
