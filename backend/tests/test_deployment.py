from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from omnirag.config import settings
from omnirag.main import app
from omnirag.api.access import validate_deployment_settings
from omnirag.storage.file_storage import get_storage_root


@pytest.fixture
def deployment_settings(monkeypatch):
    monkeypatch.setattr(settings, 'DEBUG', False)
    monkeypatch.setattr(settings, 'AUTH_USERNAME', 'test-owner')
    monkeypatch.setattr(settings, 'AUTH_PASSWORD', 'test-password-long-enough')
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', 'test-key-not-a-real-secret')


def test_private_workspace_protects_every_route_except_health(deployment_settings):
    with TestClient(app) as client:
        for route in ('/', '/docs', '/openapi.json', '/api/v1/documents', '/assets/example.js'):
            result = client.get(route)
            assert result.status_code == 401
            assert result.headers['www-authenticate'].startswith('Basic')
        assert client.get('/health').status_code == 200
        assert client.post('/api/v1/documents/upload').status_code == 401
        assert client.post('/api/v1/chat', json={'question': 'private'}).status_code == 401
        assert client.get('/api/v1/documents', auth=('test-owner', 'wrong-password')).status_code == 401
        assert client.get('/api/v1/documents', auth=('wrong-owner', 'test-password-long-enough')).status_code == 401
        assert client.get('/docs', auth=('test-owner', 'test-password-long-enough')).status_code == 200
        assert client.get('/docs', headers={'Authorization': 'Basic malformed'}).status_code == 401


def test_production_rejects_missing_access_control(deployment_settings, monkeypatch):
    monkeypatch.setattr(settings, 'AUTH_USERNAME', '')
    monkeypatch.setattr(settings, 'AUTH_PASSWORD', '')
    with pytest.raises(RuntimeError, match='Production requires AUTH_USERNAME'):
        with TestClient(app):
            pass


@pytest.mark.parametrize('field,value', [
    ('AUTH_PASSWORD', 'short'),
    ('AUTH_PASSWORD', 'replace_with_a_unique_password_at_least_16_characters'),
    ('GEMINI_API_KEY', ''),
    ('GEMINI_API_KEY', 'your_api_key_here'),
])
def test_invalid_production_secrets_fail_startup(deployment_settings, monkeypatch, field, value):
    monkeypatch.setattr(settings, field, value)
    with pytest.raises(RuntimeError):
        validate_deployment_settings()


def test_storage_directory_is_configurable(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'STORAGE_DIR', tmp_path / 'mounted-disk')
    assert get_storage_root() == (tmp_path / 'mounted-disk').resolve()
