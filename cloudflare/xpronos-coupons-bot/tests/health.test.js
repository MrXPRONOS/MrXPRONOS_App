import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../src/worker.js';

// Le GET /health n'exige pas la signature Telegram. Si GitHub reçoit un 403
// sur cette route, le refus se situe donc avant le gestionnaire applicatif.
const configured = {
  DB: {},
  CF_BOT_TOKEN: 'test-telegram-token',
  CF_BOT_WEBHOOK_SECRET: 'test-webhook-secret',
  CF_BOT_ADMIN_IDS: '123456789',
  CF_BOT_CHANNELS_JSON: '[]',
};

test('GET /health est public et retourne 200 ready si configuré', async () => {
  const response = await worker.fetch(new Request('https://example.invalid/health'), configured);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ready' });
});

test('GET /health retourne 503 quand un secret manque', async () => {
  const response = await worker.fetch(new Request('https://example.invalid/health'), { ...configured, CF_BOT_TOKEN: '' });
  assert.equal(response.status, 503);
});

test('Le webhook Telegram reste protégé par son propre secret', async () => {
  const response = await worker.fetch(new Request('https://example.invalid/telegram', {
    method: 'POST', headers: {'content-type':'application/json'}, body: '{}',
  }), configured);
  assert.equal(response.status, 403);
});

test('Les autres routes restent fermées', async () => {
  const response = await worker.fetch(new Request('https://example.invalid/'), configured);
  assert.equal(response.status, 404);
});
