import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { api } from '../src/api.js';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test('provider failures keep the retry decision and diagnostic reference', async () => {
  globalThis.fetch = async () => Response.json({
    detail: 'Gemini request limits reached.', error_code: 'provider_rate_limit',
    retryable: true, reference: 'test-reference',
  }, { status: 429 });
  await assert.rejects(api('/chat'), error => {
    assert.equal(error.message, 'Gemini request limits reached.');
    assert.equal(error.code, 'provider_rate_limit');
    assert.equal(error.retryable, true);
    assert.equal(error.reference, 'test-reference');
    return true;
  });
});

test('configuration failures are not offered as retryable', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'Check model settings.', retryable: false }, { status: 503 });
  await assert.rejects(api('/chat'), error => error.retryable === false);
});

test('non-JSON server failures report a useful connection message', async () => {
  globalThis.fetch = async () => new Response('Bad gateway', { status: 502 });
  await assert.rejects(api('/chat'), /Check that the backend is running/);
});
