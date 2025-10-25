import os, uuid, shutil
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image, ImageChops

CWD = Path(__file__).resolve().parent.parent
ASSETS_DIR = Path(os.getenv("ASSETS_DIR", CWD / "mock_assets"))
TMP_DIR = Path(os.getenv("TMP_DIR", CWD / "tmp"))
FRONT_DIR_ENV = os.getenv("FRONT_DIR", str(CWD / "frontend"))
for d in (TMP_DIR / "uploads", TMP_DIR / "previews", TMP_DIR / "orders"):
    d.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = TMP_DIR / "uploads"
PREVIEWS_DIR = TMP_DIR / "previews"
ORDERS_DIR = TMP_DIR / "orders"

app = FastAPI(title="Clodesigner API (restored)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class PreviewInput(BaseModel):
    model: str = "MT"
    view: str = "front"
    src: str | None = None
    tile: bool = False
    offset_x: int = 0
    offset_y: int = 0
    scale: float = 1.0
    details: Dict[str, Any] | None = None


class OrderInput(PreviewInput):
    details: Dict[str, Any] | None = None

def _ensure_rgba(img: Image.Image) -> Image.Image:
    return img.convert("RGBA") if img.mode != "RGBA" else img

def _load_view_assets(model: str, view: str):
    req = ["background.png", "mask.png", "overlay.png"]
    opt = ["mask_s1.png", "mask_s2.png"]
    candidates = [ASSETS_DIR / model / view, ASSETS_DIR / view]
    base = next((p for p in candidates if p.exists()), None)
    if not base:
        tried = " | ".join(map(str, candidates))
        raise HTTPException(400, f"Assets dir not found for view='{view}'. Tried: {tried}")
    missing = [n for n in req if not (base / n).exists()]
    if missing:
        raise HTTPException(400, f"Missing assets in {base}: {', '.join(missing)}")
    files = {n: base/n for n in req}
    for n in opt:
        p = base / n
        if p.exists(): files[n] = p
    return files

def _resolve_print_config(p: PreviewInput):
    details = dict(p.details or {})

    src = details.pop("print_path", None) or details.pop("src", None) or p.src
    tile = details.pop("tile", None)
    offset_x = details.pop("offset_x", None)
    offset_y = details.pop("offset_y", None)
    scale = details.pop("scale", None)

    extras = {}
    extra_payload = details.pop("extras", None)
    if isinstance(extra_payload, dict):
        extras.update(extra_payload)
    extras.update(details)

    if src is None:
        raise HTTPException(400, "No source image specified")

    try:
        tile_flag = bool(tile if tile is not None else p.tile)
    except Exception:
        tile_flag = bool(p.tile)

    def _to_int(value, default):
        if value is None:
            return int(default)
        try:
            return int(value)
        except Exception:
            raise HTTPException(400, f"Invalid integer value: {value!r}")

    def _to_float(value, default):
        if value is None:
            return float(default)
        try:
            return float(value)
        except Exception:
            raise HTTPException(400, f"Invalid float value: {value!r}")

    resolved = {
        "src": src,
        "tile": tile_flag,
        "offset_x": _to_int(offset_x, p.offset_x),
        "offset_y": _to_int(offset_y, p.offset_y),
        "scale": _to_float(scale, p.scale),
        "extras": extras,
    }
    return resolved

def _compose_preview(
    src_img_path: Path,
    assets,
    *,
    scale: float = 1.0,
    offset_x: int = 0,
    offset_y: int = 0,
    tile: bool = False,
    extras: Dict[str, Any] | None = None,
):
    bg = _ensure_rgba(Image.open(assets["background.png"]))
    canvas = Image.new("RGBA", bg.size, (0,0,0,0))
    canvas.alpha_composite(bg)
    extras = dict(extras or {})
    base_mask = Image.open(assets["mask.png"]).convert("L")
    mask_bbox = extras.pop("mask_bbox", None)
    if mask_bbox is not None:
        mask_bbox = tuple(int(v) for v in mask_bbox)
    else:
        mask_bbox = base_mask.getbbox() or (0, 0, canvas.width, canvas.height)

    limit_to_mask = bool(extras.pop("limit_to_mask", True))

    src_img = _ensure_rgba(Image.open(src_img_path))
    area_w = mask_bbox[2] - mask_bbox[0]
    area_h = mask_bbox[3] - mask_bbox[1]
    target_w = max(1, int(round(area_w * float(scale or 1.0))))
    target_h = max(1, int(round(area_h * float(scale or 1.0))))
    user = src_img.resize((target_w, target_h), Image.BICUBIC)

    user_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    if tile:
        step_x = extras.pop("tile_step_x", None)
        step_y = extras.pop("tile_step_y", None)
        if step_x is None:
            step_x = offset_x if offset_x > 0 else user.width
        if step_y is None:
            step_y = offset_y if offset_y > 0 else user.height
        step_x = max(1, int(round(step_x)))
        step_y = max(1, int(round(step_y)))

        shift_x = extras.pop("tile_shift_x", None)
        shift_y = extras.pop("tile_shift_y", None)
        if shift_x is None:
            shift_x = offset_x if offset_x < 0 else 0
        if shift_y is None:
            shift_y = offset_y if offset_y < 0 else 0

        start_x = mask_bbox[0] + int(shift_x)
        start_y = mask_bbox[1] + int(shift_y)

        while start_x + user.width < mask_bbox[0]:
            start_x += step_x
        while start_y + user.height < mask_bbox[1]:
            start_y += step_y
        while start_x > mask_bbox[0]:
            start_x -= step_x
        while start_y > mask_bbox[1]:
            start_y -= step_y

        max_x = mask_bbox[2] + step_x + user.width
        max_y = mask_bbox[3] + step_y + user.height
        for ty in range(start_y, max_y, step_y):
            for tx in range(start_x, max_x, step_x):
                user_layer.paste(user, (tx, ty), user)
    else:
        pos_x = mask_bbox[0] + (area_w - user.width) // 2 + int(offset_x)
        pos_y = mask_bbox[1] + (area_h - user.height) // 2 + int(offset_y)
        user_layer.paste(user, (pos_x, pos_y), user)

    user_alpha = user_layer.split()[-1] if user_layer.getbands()[-1] == "A" else None
    if limit_to_mask:
        final_mask = base_mask
        if user_alpha is not None:
            final_mask = ImageChops.multiply(final_mask, user_alpha)
    else:
        final_mask = user_alpha

    if final_mask is not None:
        canvas.paste(user_layer, (0, 0), final_mask)
    else:
        canvas.alpha_composite(user_layer)

    for s in ("mask_s1.png","mask_s2.png"):
        if s in assets:
            m = Image.open(assets[s]).convert("L")
            extra_layer = Image.new("RGBA", canvas.size, (0,0,0,0))
            extra_layer.alpha_composite(user_layer)
            if limit_to_mask and user_alpha is not None:
                mask_to_use = ImageChops.multiply(m, user_alpha)
            elif limit_to_mask:
                mask_to_use = m
            else:
                mask_to_use = user_alpha or m
            canvas.paste(extra_layer, (0,0), mask_to_use)
    overlay = _ensure_rgba(Image.open(assets["overlay.png"]))
    canvas.alpha_composite(overlay)
    return canvas

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    name = file.filename or "upload.bin"
    data = await file.read()
    if not name.lower().endswith((".png",".jpg",".jpeg")):
        raise HTTPException(400, "Only PNG/JPG allowed")
    if len(data) > 50*1024*1024:
        raise HTTPException(400, "File too large (>50MB)")
    up = UPLOADS_DIR / f"{uuid.uuid4().hex}_{name}"
    up.write_bytes(data)
    rel = up.relative_to(CWD)
    return {"path": str(rel).replace("\\","/"), "url": f"/files/{rel}".replace("\\","/")}

@app.post("/api/preview")
async def preview(p: PreviewInput):
    cfg = _resolve_print_config(p)
    src = Path(cfg["src"])
    if not src.is_absolute():
        src = (CWD / src).resolve()
    if not src.exists():
        raise HTTPException(400, f"Uploaded file not found: {src}")
    img = _compose_preview(
        src,
        _load_view_assets(p.model, p.view),
        scale=cfg["scale"],
        offset_x=cfg["offset_x"],
        offset_y=cfg["offset_y"],
        tile=cfg["tile"],
        extras=cfg["extras"],
    )
    out = PREVIEWS_DIR / f"{uuid.uuid4().hex[:8]}_{p.model}_{p.view}.png"
    img.save(out, "PNG")
    rel = out.relative_to(CWD)
    return {"ok": True, "url": f"/files/{rel}".replace("\\","/")}

@app.post("/api/order")
async def order(p: OrderInput):
    cfg = _resolve_print_config(p)
    src = Path(cfg["src"])
    if not src.is_absolute():
        src = (CWD / src).resolve()
    if not src.exists():
        raise HTTPException(400, f"Uploaded file not found: {src}")
    oid = uuid.uuid4().hex[:8]
    base = (ORDERS_DIR / oid); (base/"mockups").mkdir(parents=True, exist_ok=True); (base/"sources").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, base/"sources"/Path(src.name))
    img = _compose_preview(
        src,
        _load_view_assets(p.model, p.view),
        scale=cfg["scale"],
        offset_x=cfg["offset_x"],
        offset_y=cfg["offset_y"],
        tile=cfg["tile"],
        extras=cfg["extras"],
    )
    out = base/"mockups"/f"{p.model}_{p.view}.png"; img.save(out, "PNG")
    return {"ok": True, "order": oid,
            "mockups": [f"/files/{out.relative_to(CWD)}".replace("\\","/")],
            "mockups_dir": f"/files/{(base/'mockups').relative_to(CWD)}".replace("\\","/")}

front_dir = Path(FRONT_DIR_ENV)
front_dir.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(CWD)), name="files")
app.mount("/", StaticFiles(directory=str(front_dir), html=True), name="app")
