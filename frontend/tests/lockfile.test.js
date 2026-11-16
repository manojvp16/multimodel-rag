import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('deployment lockfile contains complete package versions and Linux native binaries', () => {
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
  for (const [name, entry] of Object.entries(lock.packages)) {
    if (name) assert.match(entry.version ?? '', /^\d+\.\d+\.\d+/, `Missing or invalid version: ${name}`);
  }
  for (const name of ['@esbuild/linux-x64', '@rollup/rollup-linux-x64-gnu']) {
    const entry = lock.packages[`node_modules/${name}`];
    assert.ok(entry?.resolved && entry?.integrity, `Missing Linux package metadata: ${name}`);
  }
});
