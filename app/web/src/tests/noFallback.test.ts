import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import fs from 'fs';
import path from 'path';
import { api, setDevmockOverride, ApiError } from '../api/client';

describe('Wave 10: No Silent DevMock Fallback Verification', () => {
  beforeEach(() => {
    setDevmockOverride(false);
  });

  afterEach(() => {
    setDevmockOverride(null);
    vi.restoreAllMocks();
  });

  it('asserts no non-devmock module imports or calls devmock outside a devmock-enabled branch', () => {
    const srcDir = path.resolve(__dirname, '..');
    const allFiles: string[] = [];

    function scan(dir: string) {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (entry.name !== 'devmock' && entry.name !== 'tests') {
            scan(full);
          }
        } else if (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) {
          allFiles.push(full);
        }
      }
    }

    scan(srcDir);

    for (const file of allFiles) {
      const content = fs.readFileSync(file, 'utf-8');
      const relPath = path.relative(srcDir, file).replace(/\\/g, '/');

      if (relPath !== 'api/client.ts') {
        expect(
          content.includes('from "../devmock"') ||
            content.includes("from '../devmock'") ||
            content.includes('devMockService')
        ).toBe(false);
      } else {
        // In client.ts, devMockService must never be referenced in any catch block
        const catchBlocks = content.match(/catch\s*(\([^\)]*\))?\s*\{([^}]*)\}/gs) || [];
        for (const block of catchBlocks) {
          expect(block.includes('devMockService')).toBe(false);
        }

        // Must not contain hardcoded mock ID bypasses like caseId.startsWith('CASE-00')
        expect(content.includes("caseId.startsWith('CASE-00')")).toBe(false);
      }
    }
  });

  it('asserts that fixtureData contains no external placeholder video (e.g. flower.webm)', () => {
    const fixturePath = path.resolve(__dirname, '../devmock/fixtureData.ts');
    const content = fs.readFileSync(fixturePath, 'utf-8');
    expect(content.includes('flower.webm')).toBe(false);
    expect(content.includes('mozilla.net')).toBe(false);
  });

  it('fails loudly when getCase receives an API error without returning fixture data', async () => {
    setDevmockOverride(false);

    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ code: 'CASE_NOT_FOUND', user_message: 'Case does not exist in store ledger' }),
          { status: 404, statusText: 'Not Found', headers: { 'Content-Type': 'application/json' } }
        )
      )
    );

    await expect(api.getCase('CASE-NONEXISTENT')).rejects.toThrow(ApiError);
  });

  it('fails loudly when getOrders receives an API error without returning mock orders', async () => {
    setDevmockOverride(false);

    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ code: 'INTERNAL_ERROR', user_message: 'Database query failed' }),
          { status: 500, statusText: 'Internal Server Error', headers: { 'Content-Type': 'application/json' } }
        )
      )
    );

    await expect(api.getOrders('CUS-01')).rejects.toThrow(ApiError);
  });

  it('fails loudly when getSellerCases receives an API error without returning mock cases', async () => {
    setDevmockOverride(false);

    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ code: 'UNAUTHORIZED', user_message: 'Session expired' }),
          { status: 401, statusText: 'Unauthorized', headers: { 'Content-Type': 'application/json' } }
        )
      )
    );

    await expect(api.getSellerCases()).rejects.toThrow(ApiError);
  });

  it('correctly maps evidence storage_key to live /api/media/{evidence_id} endpoint', async () => {
    setDevmockOverride(false);

    vi.spyOn(globalThis, 'fetch').mockImplementation((input: any) => {
      const url = String(input);
      if (url.includes('/events')) {
        return Promise.resolve(
          new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } })
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            case_id: 'CASE-LIVE-1',
            case_type: 'MISMATCH',
            state: 'WAITING_SELLER',
            evidence: [
              {
                evidence_id: 'EVI-LIVE-99',
                media_type: 'video',
                filename: 'stock_black_headphones_pexels_9130360.mp4',
              },
            ],
            observations: [],
            unknowns: [],
            messages: [],
            proposals: [],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      );
    });

    const detail = await api.getCase('CASE-LIVE-1');
    expect(detail.evidence[0].url).toBe('/api/media/EVI-LIVE-99');
    expect(detail.evidence[0].url.includes('flower.webm')).toBe(false);
  });
});
