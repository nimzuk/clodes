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

const VIEWS = ["front", "sleeveL", "back", "sleeveR"];
const createDetail = () => ({
  previewUrl: null,
  transform: { scale: 1, tx: 0, ty: 0 },
  tile: { enabled: false },
});

const useStore = create((set, get) => ({
  // состояние
  model: "MT",
  view: "front",
  active: "front",
  details: VIEWS.reduce((acc, view) => ({ ...acc, [view]: createDetail() }), {}),
  uploadedPath: null,
  uploadedUrl: null,
  busy: false,
  lastPreviewUrls: null,
  lastOrderInfo: null,

  // сеттеры
  setModel: (model) => set({ model }),
  setView: (view) => set({ view, active: view }),
  setActive: (active) => set({ active, view: active }),
  setScale: (scale) =>
    set((state) => {
      const active = state.active;
      const detail = state.details[active] ?? createDetail();
      return {
        details: {
          ...state.details,
          [active]: {
            ...detail,
            transform: { ...detail.transform, scale },
          },
        },
      };
    }),
  setTx: (tx) =>
    set((state) => {
      const active = state.active;
      const detail = state.details[active] ?? createDetail();
      return {
        details: {
          ...state.details,
          [active]: {
            ...detail,
            transform: { ...detail.transform, tx },
          },
        },
      };
    }),
  setTy: (ty) =>
    set((state) => {
      const active = state.active;
      const detail = state.details[active] ?? createDetail();
      return {
        details: {
          ...state.details,
          [active]: {
            ...detail,
            transform: { ...detail.transform, ty },
          },
        },
      };
    }),
  toggleTile: () =>
    set((state) => {
      const active = state.active;
      const detail = state.details[active] ?? createDetail();
      return {
        details: {
          ...state.details,
          [active]: {
            ...detail,
            tile: { ...detail.tile, enabled: !detail.tile.enabled },
          },
        },
      };
    }),

  // 1) загрузка принта
  async upload(file) {
    set({ busy: true });
    try {
      const { path, url } = await postFile("/api/upload", file);
      set({ uploadedPath: path, uploadedUrl: url });
      return path;
    } finally {
      set({ busy: false });
    }
  },

  // 2) построение превью из текущих контролов
  async spread() {
    const state = get();
    const { model, active, uploadedPath } = state;
    const detail = state.details[active];
    if (!uploadedPath) throw new Error("Сначала загрузите принт");

    set({ busy: true });
    try {
      const payload = {
        model,
        view: active,
        src: uploadedPath,
        tile: detail.tile.enabled,
        offset_x: detail.transform.tx,
        offset_y: detail.transform.ty,
        scale: detail.transform.scale,
      };
      const data = await postJSON("/api/preview", payload);
      const activeView = active;
      set((prev) => {
        const prevDetail = prev.details[activeView] ?? createDetail();
        const previewsMap =
          data.previews ??
          (data.url
            ? { ...(prev.lastPreviewUrls ?? {}), [activeView]: data.url }
            : prev.lastPreviewUrls);
        return {
          details: {
            ...prev.details,
            [activeView]: {
              ...prevDetail,
              previewUrl: data.url ?? prevDetail.previewUrl,
            },
          },
          lastPreviewUrls: previewsMap ?? null,
        };
      });
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
    const state = get();
    const { model, active, uploadedPath } = state;
    const detail = state.details[active];
    if (!uploadedPath) throw new Error("Сначала загрузите принт");

    set({ busy: true });
    try {
      const payload = {
        model,
        view: active,
        src: uploadedPath,
        tile: detail.tile.enabled,
        offset_x: detail.transform.tx,
        offset_y: detail.transform.ty,
        scale: detail.transform.scale,
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
