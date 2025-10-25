// frontend/src/useStore.js
import { create } from "zustand";

// небольшие хелперы для запросов
const postJSON = async (url, body) => {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

const postFile = async (url, file) => {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(url, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
};

const useStore = create((set, get) => ({
  // состояние
  model: "MT",
  view: "front",
  tile: false,
  offsetX: 0,
  offsetY: 0,
  scale: 1,
  uploadedPath: null,
  busy: false,
  lastPreviewUrls: null,
  lastOrderInfo: null,

  // сеттеры
  setModel: (model) => set({ model }),
  setView: (view) => set({ view }),
  setTile: (tile) => set({ tile }),
  setOffsetX: (offsetX) => set({ offsetX }),
  setOffsetY: (offsetY) => set({ offsetY }),
  setScale: (scale) => set({ scale }),

  // 1) загрузка принта
  async upload(file) {
    set({ busy: true });
    try {
      const { path } = await postFile("/api/upload", file);
      set({ uploadedPath: path });
      return path;
    } finally {
      set({ busy: false });
    }
  },

  // 2) построение превью из текущих контролов
  async spread() {
    const { model, view, tile, offsetX, offsetY, scale, uploadedPath } = get();
    if (!uploadedPath) throw new Error("Сначала загрузите принт");

    set({ busy: true });
    try {
      const payload = {
        model,
        view,
        details: {
          print_path: uploadedPath,
          tile,
          offset_x: offsetX,
          offset_y: offsetY,
          scale,
        },
      };
      const data = await postJSON("/api/preview", payload);
      const urls =
        data.previews ||
        (data.preview_url ? { [view]: data.preview_url } : null);
      set({ lastPreviewUrls: urls });
      return data;
    } finally {
      set({ busy: false });
    }
  },

  // удобный комбинированный экшен под кнопку "Upload / Spread"
  async uploadAndSpread(file) {
    await get().upload(file);
    return get().spread();
  },

  // 3) создание заказа
  async startOrder() {
    const { model, view, tile, offsetX, offsetY, scale, uploadedPath } = get();
    if (!uploadedPath) throw new Error("Сначала загрузите принт");

    set({ busy: true });
    try {
      const payload = {
        model,
        view,
        details: {
          print_path: uploadedPath,
          tile,
          offset_x: offsetX,
          offset_y: offsetY,
          scale,
        },
      };
      const data = await postJSON("/api/order", payload);
      set({ lastOrderInfo: data });
      return data;
    } finally {
      set({ busy: false });
    }
  },
}));

export default useStore;