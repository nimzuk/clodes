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

const createInitialDetail = () => ({
  previewUrl: null,
  transform: { scale: 1, tx: 0, ty: 0 },
  tile: { enabled: false },
});

const useStore = create((set, get) => ({
  // состояние
  model: "MT",
  active: "front",
  details: {
    front: createInitialDetail(),
    sleeveL: createInitialDetail(),
    back: createInitialDetail(),
    sleeveR: createInitialDetail(),
  },
  uploadedPath: null,
  uploadedUrl: null,
  busy: false,
  lastPreviewUrls: null,
  lastOrderInfo: null,

  // сеттеры
  setModel: (model) => set({ model }),
  setActive: (active) => set({ active }),
  setScale: (scale) =>
    set((state) => ({
      details: {
        ...state.details,
        [state.active]: {
          ...state.details[state.active],
          transform: {
            ...state.details[state.active].transform,
            scale,
          },
        },
      },
    })),
  setTx: (tx) =>
    set((state) => ({
      details: {
        ...state.details,
        [state.active]: {
          ...state.details[state.active],
          transform: {
            ...state.details[state.active].transform,
            tx,
          },
        },
      },
    })),
  setTy: (ty) =>
    set((state) => ({
      details: {
        ...state.details,
        [state.active]: {
          ...state.details[state.active],
          transform: {
            ...state.details[state.active].transform,
            ty,
          },
        },
      },
    })),
  toggleTile: () =>
    set((state) => ({
      details: {
        ...state.details,
        [state.active]: {
          ...state.details[state.active],
          tile: {
            enabled: !state.details[state.active].tile.enabled,
          },
        },
      },
    })),

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
    const { model, active, details, uploadedPath } = get();
    const detail = details[active];
    if (!uploadedPath) throw new Error("Сначала загрузите принт");

    set({ busy: true });
    try {
      const payload = {
        model,
        view: active,
        details: {
          print_path: uploadedPath,
          tile: detail.tile.enabled,
          offset_x: detail.transform.tx,
          offset_y: detail.transform.ty,
          scale: detail.transform.scale,
        },
      };
      const data = await postJSON("/api/preview", payload);
      const urls =
        data.previews ||
        (data.preview_url ? { [active]: data.preview_url } : null);
      if (urls) {
        set((state) => {
          const updatedDetails = { ...state.details };
          for (const [key, url] of Object.entries(urls)) {
            if (!updatedDetails[key]) continue;
            updatedDetails[key] = {
              ...updatedDetails[key],
              previewUrl: url,
            };
          }
          return { details: updatedDetails, lastPreviewUrls: urls };
        });
      } else {
        set({ lastPreviewUrls: urls });
      }
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
    const { model, active, details, uploadedPath } = get();
    const detail = details[active];
    if (!uploadedPath) throw new Error("Сначала загрузите принт");

    set({ busy: true });
    try {
      const payload = {
        model,
        view: active,
        details: {
          print_path: uploadedPath,
          tile: detail.tile.enabled,
          offset_x: detail.transform.tx,
          offset_y: detail.transform.ty,
          scale: detail.transform.scale,
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
