import { useEffect, useRef, useState, useCallback } from "react";
import { Excalidraw, convertToExcalidrawElements } from "@excalidraw/excalidraw";
import "@excalidraw/excalidraw/index.css";
import { WS_BASE, getShareToken } from "@/lib/apiClient";
import apiClient from "@/lib/apiClient";
import { useTheme } from "@/context/ThemeContext";

const AUTO_SYNC_MS = 500;
const POINTER_MS = 90;

const stripServerMeta = (el) => {
  const { createdAt, updatedAt, version, syncedAt, source, syncTimestamp, ...rest } = el;
  return rest;
};

const validateBindings = (elements) => {
  const map = new Map(elements.map((el) => [el.id, el]));
  return elements.map((el) => {
    const fixed = { ...el };
    if (Array.isArray(fixed.boundElements)) {
      fixed.boundElements = fixed.boundElements.filter(
        (b) => b && b.id && b.type && map.has(b.id) && ["text", "arrow"].includes(b.type)
      );
      if (fixed.boundElements.length === 0) fixed.boundElements = null;
    } else if (fixed.boundElements) {
      fixed.boundElements = null;
    }
    if (fixed.containerId && !map.has(fixed.containerId)) fixed.containerId = null;
    return fixed;
  });
};

const restoreBindings = (converted, originals) => {
  const map = new Map(originals.map((el) => [el.id, el]));
  return converted.map((el) => {
    const orig = map.get(el.id);
    if (!orig) return el;
    const p = { ...el };
    if (orig.startBinding && !el.startBinding) p.startBinding = orig.startBinding;
    if (orig.endBinding && !el.endBinding) p.endBinding = orig.endBinding;
    if (orig.boundElements && (!el.boundElements || el.boundElements.length === 0))
      p.boundElements = orig.boundElements;
    return p;
  });
};

const convertScene = (elements) => {
  if (!elements.length) return [];
  const validated = validateBindings(elements);
  const images = validated.filter((el) => el.type === "image");
  const nonImages = validated.filter((el) => el.type !== "image");
  let converted = [];
  try {
    converted = convertToExcalidrawElements(nonImages, { regenerateIds: false });
    converted = restoreBindings(converted, nonImages);
  } catch (e) {
    converted = nonImages;
  }
  return [...converted, ...images];
};

export default function ExcalidrawCanvasView({ projectId, apiRef, onConnectionChange, canEdit = true, userName = "Guest" }) {
  const { theme } = useTheme();
  const [, setExcalidrawAPI] = useState(null);
  const apiInstance = useRef(null);
  const clientIdRef = useRef(Math.random().toString(36).slice(2));
  const myColorRef = useRef(`hsl(${Math.floor(Math.random() * 360)} 80% 60%)`);
  const wsRef = useRef(null);
  const suppressRef = useRef(0);
  const userInteractedRef = useRef(false);
  const syncTimerRef = useRef(null);
  const lastPointerRef = useRef(0);
  const collaboratorsRef = useRef(new Map());

  const applyRemote = useCallback((elements) => {
    const api = apiInstance.current;
    if (!api) return;
    suppressRef.current += 1;
    api.updateScene({ elements });
    setTimeout(() => { suppressRef.current = Math.max(0, suppressRef.current - 1); }, 0);
  }, []);

  const mergeAndApply = useCallback((incoming) => {
    const api = apiInstance.current;
    if (!api || !incoming.length) return;
    const current = api.getSceneElements();
    const incomingById = new Map(incoming.map((el) => [el.id, el]));
    const merged = current.map((el) => {
      const inc = incomingById.get(el.id);
      if (!inc) return el;
      incomingById.delete(el.id);
      return { ...el, ...inc };
    });
    merged.push(...incomingById.values());
    applyRemote(convertScene(merged));
  }, [applyRemote]);

  const handleMessage = useCallback((data) => {
    const api = apiInstance.current;
    if (!api) return;
    switch (data.type) {
      case "initial_elements":
        if (data.elements?.length) applyRemote(convertScene(data.elements.map(stripServerMeta)));
        if (data.files) api.addFiles(Object.values(data.files));
        break;
      case "element_created":
      case "element_updated":
        if (data.element) mergeAndApply([stripServerMeta(data.element)]);
        break;
      case "elements_batch_created":
        if (data.elements) mergeAndApply(data.elements.map(stripServerMeta));
        break;
      case "elements_synced":
        // Co-editing: another editor pushed the full scene. Replace (ignore our own echo).
        if (data.clientId !== clientIdRef.current && Array.isArray(data.elements)) {
          applyRemote(convertScene(data.elements.map(stripServerMeta)));
        }
        break;
      case "element_deleted":
        if (data.elementId) {
          applyRemote(api.getSceneElements().filter((el) => el.id !== data.elementId));
        }
        break;
      case "canvas_cleared":
        applyRemote([]);
        break;
      case "files_added":
        if (Array.isArray(data.files)) api.addFiles(data.files);
        break;
      case "pointer": {
        // Live collaborator cursors.
        if (data.clientId === clientIdRef.current) break;
        collaboratorsRef.current.set(data.clientId, {
          username: data.name || "Guest",
          pointer: { x: data.x, y: data.y },
          color: { background: data.color || "#6366f1", stroke: data.color || "#6366f1" },
        });
        try { api.updateScene({ collaborators: new Map(collaboratorsRef.current) }); } catch (_) {}
        break;
      }
      case "presence_leave":
        collaboratorsRef.current.delete(data.clientId);
        try { api.updateScene({ collaborators: new Map(collaboratorsRef.current) }); } catch (_) {}
        break;
      default:
        break;
    }
  }, [applyRemote, mergeAndApply]);

  useEffect(() => {
    let closed = false;
    const share = getShareToken();
    const connect = () => {
      const qs = share ? `?share=${encodeURIComponent(share)}` : "";
      const ws = new WebSocket(`${WS_BASE}/canvas/${projectId}${qs}`);
      wsRef.current = ws;
      ws.onopen = () => onConnectionChange?.(true);
      ws.onmessage = (e) => { try { handleMessage(JSON.parse(e.data)); } catch (_) {} };
      ws.onclose = () => {
        onConnectionChange?.(false);
        if (!closed) setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
    };
    connect();
    return () => {
      closed = true;
      try { wsRef.current?.send(JSON.stringify({ type: "presence_leave", clientId: clientIdRef.current })); } catch (_) {}
      wsRef.current?.close();
    };
  }, [projectId, handleMessage, onConnectionChange]);

  const persist = useCallback(async () => {
    const api = apiInstance.current;
    if (!api || !canEdit) return;
    const elements = api.getSceneElements().filter((el) => !el.isDeleted);
    try {
      await apiClient.put(`/projects/${projectId}/scene`, { elements, files: {}, client_id: clientIdRef.current });
    } catch (_) {}
  }, [projectId, canEdit]);

  const scheduleSync = useCallback(() => {
    if (!canEdit || !userInteractedRef.current || suppressRef.current > 0) return;
    if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    syncTimerRef.current = setTimeout(() => {
      syncTimerRef.current = null;
      if (suppressRef.current === 0) persist();
    }, AUTO_SYNC_MS);
  }, [persist, canEdit]);

  const onPointerUpdate = useCallback((payload) => {
    const now = Date.now();
    if (now - lastPointerRef.current < POINTER_MS) return;
    lastPointerRef.current = now;
    const ws = wsRef.current;
    const p = payload?.pointer;
    if (ws && ws.readyState === 1 && p) {
      try {
        ws.send(JSON.stringify({ type: "pointer", clientId: clientIdRef.current, name: userName, color: myColorRef.current, x: p.x, y: p.y }));
      } catch (_) {}
    }
  }, [userName]);

  return (
    <div
      className="w-full h-full"
      data-testid="excalidraw-container"
      onPointerDownCapture={() => { userInteractedRef.current = true; }}
      onKeyDownCapture={() => { userInteractedRef.current = true; }}
    >
      <Excalidraw
        theme={theme}
        viewModeEnabled={!canEdit}
        excalidrawAPI={(api) => {
          apiInstance.current = api;
          setExcalidrawAPI(api);
          if (apiRef) apiRef.current = api;
        }}
        onChange={scheduleSync}
        onPointerUpdate={onPointerUpdate}
      />
    </div>
  );
}
