import { Router, Request, Response } from 'express';
import { getCanvas } from '../types.js';
import { getCanvasId, computeGroupsFromElements } from '../helpers.js';

const router = Router();

// Scene state served from the canvas server (source of truth), so group /
// viewport / theme survive the stateless MCP proxy. Groups are derived live
// from each element's `groupIds`.
router.get('/api/scene', (req: Request, res: Response) => {
  const canvas = getCanvas(getCanvasId(req));
  const groups = computeGroupsFromElements(Array.from(canvas.elements.values()));
  res.json({
    success: true,
    theme: canvas.theme,
    viewport: canvas.viewport,
    groups,
    selectedElements: [],
    elementCount: canvas.elements.size,
  });
});

export default router;
