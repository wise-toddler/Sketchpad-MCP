import { describe, it, expect, vi, beforeEach } from 'vitest';
import request from 'supertest';

// Mock node-fetch so we can drive canvas-sync success/failure deterministically.
vi.mock('node-fetch', () => ({ default: vi.fn() }));
import fetch from 'node-fetch';
import { createElementOnCanvas, batchCreateElementsOnCanvas } from '../tools/sync.js';
import { expandLabelPosition, computeGroupsFromElements } from '../helpers.js';
import app from '../server.js';

const mockFetch = fetch as unknown as ReturnType<typeof vi.fn>;

// ── Fix 1: create/batch must report failure (null), not echo the input as success ──
describe('Fix 1: create/batch report canvas-sync failure', () => {
  beforeEach(() => mockFetch.mockReset());

  it('createElementOnCanvas returns null when the canvas sync fails', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, statusText: 'Server Error', json: async () => ({ error: 'boom' }) });
    const res = await createElementOnCanvas({ id: 'x', type: 'rectangle', x: 0, y: 0 } as any);
    expect(res).toBeNull();
  });

  it('createElementOnCanvas returns the element on success', async () => {
    const el = { id: 'x', type: 'rectangle', x: 0, y: 0 };
    mockFetch.mockResolvedValue({ ok: true, status: 200, statusText: 'OK', json: async () => ({ success: true, element: el }) });
    const res = await createElementOnCanvas(el as any);
    expect(res).toEqual(el);
  });

  it('batchCreateElementsOnCanvas returns null when the canvas sync fails', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, statusText: 'Server Error', json: async () => ({ error: 'boom' }) });
    const res = await batchCreateElementsOnCanvas([{ id: 'x', type: 'rectangle', x: 0, y: 0 }] as any);
    expect(res).toBeNull();
  });

  it('batchCreateElementsOnCanvas returns the elements on success', async () => {
    const els = [{ id: 'x', type: 'rectangle', x: 0, y: 0 }];
    mockFetch.mockResolvedValue({ ok: true, status: 200, statusText: 'OK', json: async () => ({ success: true, elements: els }) });
    const res = await batchCreateElementsOnCanvas(els as any);
    expect(res).toEqual(els);
  });
});

// ── Fix 3: single shared labelPosition expansion (create_element + batch) ──
describe('Fix 3: shared labelPosition expansion', () => {
  it('expands a non-center labeled shape into [shape, free-standing text]', () => {
    const out = expandLabelPosition({ id: 's1', type: 'rectangle', x: 100, y: 100, width: 200, height: 80, text: 'Hello', labelPosition: 'top-left' } as any);
    expect(out).toHaveLength(2);
    expect(out[0]!.type).toBe('rectangle');
    expect((out[0] as any).text).toBeUndefined();
    expect((out[0] as any).labelPosition).toBeUndefined();
    expect(out[1]!.type).toBe('text');
    expect(out[1]!.text).toBe('Hello');
  });

  it('keeps a center label as a single element (labelPosition stripped)', () => {
    const out = expandLabelPosition({ id: 's2', type: 'rectangle', x: 0, y: 0, text: 'Hi', labelPosition: 'center' } as any);
    expect(out).toHaveLength(1);
    expect((out[0] as any).labelPosition).toBeUndefined();
    expect((out[0] as any).text).toBe('Hi');
  });

  it('does not expand arrows or lines', () => {
    const arrow = expandLabelPosition({ id: 'a1', type: 'arrow', x: 0, y: 0, text: 'label', labelPosition: 'top-left' } as any);
    expect(arrow).toHaveLength(1);
    const line = expandLabelPosition({ id: 'l1', type: 'line', x: 0, y: 0, text: 'label', labelPosition: 'top-left' } as any);
    expect(line).toHaveLength(1);
  });
});

// ── Fix 2: group/scene state derived from element.groupIds on the canvas server ──
describe('Fix 2: stateless-safe group + scene state', () => {
  it('computeGroupsFromElements groups elements by their groupIds', () => {
    const groups = computeGroupsFromElements([
      { id: 'a', type: 'rectangle', x: 0, y: 0, groupIds: ['g1'] },
      { id: 'b', type: 'rectangle', x: 0, y: 0, groupIds: ['g1'] },
      { id: 'c', type: 'rectangle', x: 0, y: 0, groupIds: ['g2'] },
      { id: 'd', type: 'rectangle', x: 0, y: 0 },
    ] as any);
    expect(groups['g1']).toEqual(['a', 'b']);
    expect(groups['g2']).toEqual(['c']);
    expect(Object.keys(groups)).toHaveLength(2);
  });

  it('GET /api/scene derives groups live from element.groupIds', async () => {
    const cid = 'scene-test-canvas';
    await request(app).post('/api/elements').query({ canvasId: cid })
      .send({ id: 'e1', type: 'rectangle', x: 0, y: 0, width: 10, height: 10, groupIds: ['grp'] });
    await request(app).post('/api/elements').query({ canvasId: cid })
      .send({ id: 'e2', type: 'rectangle', x: 20, y: 0, width: 10, height: 10, groupIds: ['grp'] });

    const res = await request(app).get('/api/scene').query({ canvasId: cid });
    expect(res.status).toBe(200);
    expect(res.body.groups.grp.sort()).toEqual(['e1', 'e2']);
    expect(res.body.theme).toBe('light');
    expect(res.body.viewport).toEqual({ x: 0, y: 0, zoom: 1 });
  });
});
