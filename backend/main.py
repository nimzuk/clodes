import os, uuid, shutil
from pathlib import Path
from typing import Dict, Tuple, Any
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image

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
front_dir = Path(FRONT_DIR_ENV); front_dir.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(front_dir), html=True), name="app")
app.mount("/files", StaticFiles(directory=str(CWD)), name="files")

class PreviewInput(BaseModel):
    model: str = "MT"
    view: str = "front"
    src: str
    tile: bool = False
    offset_x: int = 0
    offset_y: int = 0
    scale: float = 1.0

class OrderInput(PreviewInput):
    details: Dict[str, Any] = {}

def _ensure_rgba(img: Image.Image) -> Image.Image:
    return img.convert("RGBA") if img.mode != "RGBA" else img

def _resize_to(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    return img.resize(size, Image.BICUBIC)

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

def _compose_preview(
    src_img_path: Path,
    assets,
    *,
    tile: bool = False,
    offset_x: int = 0,
    offset_y: int = 0,
    scale: float = 1.0,
):
    bg = _ensure_rgba(Image.open(assets["background.png"]))
    canvas = Image.new("RGBA", bg.size, (0,0,0,0))
    canvas.alpha_composite(bg)
    user = _ensure_rgba(Image.open(src_img_path))
    scale = max(0.01, float(scale or 0))
    scaled_size = (
        max(1, int(round(user.width * scale))),
        max(1, int(round(user.height * scale))),
    )
    user = user.resize(scaled_size, Image.BICUBIC)
    ox = int(offset_x)
    oy = int(offset_y)
    user_on = Image.new("RGBA", canvas.size, (0,0,0,0))
    if tile and user.width > 0 and user.height > 0:
        step_x = max(1, user.width)
        step_y = max(1, user.height)
        pad_x = step_x * 2
        pad_y = step_y * 2
        for ty in range(-pad_y, canvas.height + pad_y, step_y):
            for tx in range(-pad_x, canvas.width + pad_x, step_x):
                user_on.paste(user, (tx + ox, ty + oy), user)
    else:
        x = (canvas.width - user.width)//2 + ox
        y = (canvas.height - user.height)//2 + oy
        user_on.paste(user, (x,y), user)
    base_mask = Image.open(assets["mask.png"]).convert("L")
    canvas.paste(user_on, (0,0), base_mask)
    for s in ("mask_s1.png","mask_s2.png"):
        if s in assets:
            m = Image.open(assets[s]).convert("L")
            canvas.paste(user_on, (0,0), m)
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
    src = (CWD / p.src) if not Path(p.src).is_absolute() else Path(p.src)
    if not src.exists():
        raise HTTPException(400, f"Uploaded file not found: {src}")
    img = _compose_preview(
        src,
        _load_view_assets(p.model, p.view),
        tile=p.tile,
        offset_x=p.offset_x,
        offset_y=p.offset_y,
        scale=p.scale,
    )
    out = PREVIEWS_DIR / f"{uuid.uuid4().hex[:8]}_{p.model}_{p.view}.png"
    img.save(out, "PNG")
    rel = out.relative_to(CWD)
    return {"ok": True, "url": f"/files/{rel}".replace("\\","/")}

@app.post("/api/order")
async def order(p: OrderInput):
    src = (CWD / p.src) if not Path(p.src).is_absolute() else Path(p.src)
    if not src.exists():
        raise HTTPException(400, f"Uploaded file not found: {src}")
    oid = uuid.uuid4().hex[:8]
    base = (ORDERS_DIR / oid); (base/"mockups").mkdir(parents=True, exist_ok=True); (base/"sources").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, base/"sources"/Path(src.name))
    img = _compose_preview(
        src,
        _load_view_assets(p.model, p.view),
        tile=p.tile,
        offset_x=p.offset_x,
        offset_y=p.offset_y,
        scale=p.scale,
    )
    out = base/"mockups"/f"{p.model}_{p.view}.png"; img.save(out, "PNG")
    return {"ok": True, "order": oid,
            "mockups": [f"/files/{out.relative_to(CWD)}".replace("\\","/")],
            "mockups_dir": f"/files/{(base/'mockups').relative_to(CWD)}".replace("\\","/")}
