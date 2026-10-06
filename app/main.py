import base64
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from . import config
from .agent import FitmentAgent
from .rendering import RenderError, render_car_with_wheels
from .wheelsize import WheelSizeClient

STATIC_DIR = Path(__file__).parent / "static"
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    ws = WheelSizeClient()
    app.state.agent = FitmentAgent(ws)
    app.state.sessions = {}
    yield
    await ws.aclose()


app = FastAPI(title="Wheel Fitment Agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/api/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or uuid.uuid4().hex
    history = app.state.sessions.setdefault(session_id, [])
    reply = await app.state.agent.chat(history, req.message)
    return {"session_id": session_id, "reply": reply}


async def _read_image(upload: UploadFile | None) -> tuple[bytes, str] | None:
    if upload is None or not upload.filename:
        return None
    if upload.content_type not in ALLOWED_MIME:
        raise HTTPException(400, "Images must be JPEG, PNG or WebP.")
    data = await upload.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image exceeds 10 MB.")
    return data, upload.content_type


@app.post("/api/render")
async def render(
    car_image: UploadFile | None = File(None),
    wheel_image: UploadFile | None = File(None),
    car_description: str = Form(""),
    wheel_description: str = Form(""),
    stance_notes: str = Form(""),
):
    try:
        png = await render_car_with_wheels(
            car_image=await _read_image(car_image),
            wheel_image=await _read_image(wheel_image),
            car_description=car_description,
            wheel_description=wheel_description,
            stance_notes=stance_notes,
        )
    except RenderError as exc:
        raise HTTPException(400, str(exc))
    return {"image_b64": base64.b64encode(png).decode()}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
