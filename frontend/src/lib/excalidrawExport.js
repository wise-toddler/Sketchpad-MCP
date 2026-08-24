import { exportToBlob, exportToSvg } from "@excalidraw/excalidraw";

const triggerDownload = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

export const exportPng = async (api, name) => {
  const blob = await exportToBlob({
    elements: api.getSceneElements(),
    appState: { ...api.getAppState(), exportBackground: true },
    files: api.getFiles(),
    mimeType: "image/png",
  });
  triggerDownload(blob, `${name}.png`);
};

export const exportSvg = async (api, name) => {
  const svg = await exportToSvg({
    elements: api.getSceneElements(),
    appState: { ...api.getAppState(), exportBackground: true },
    files: api.getFiles(),
  });
  const svgString = new XMLSerializer().serializeToString(svg);
  triggerDownload(new Blob([svgString], { type: "image/svg+xml" }), `${name}.svg`);
};

export const exportJson = (api, name) => {
  const scene = {
    type: "excalidraw",
    version: 2,
    source: "excalidraw-mcp-cloud",
    elements: api.getSceneElements().filter((el) => !el.isDeleted),
    appState: { viewBackgroundColor: "#ffffff", gridSize: null },
    files: api.getFiles(),
  };
  triggerDownload(
    new Blob([JSON.stringify(scene, null, 2)], { type: "application/json" }),
    `${name}.excalidraw`
  );
};
