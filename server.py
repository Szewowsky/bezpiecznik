"""
Bezpiecznik — FastAPI server (nowy UI).

Run:
    uvicorn server:app --host 127.0.0.1 --port 8000 --reload

UI: http://localhost:8000
API: POST /api/redact { "text": "..." } → { detections, redacted_text }
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pii_service import redact_text

WEB_DIR = Path(__file__).parent / "web"

app = FastAPI(
    title="Bezpiecznik",
    description="Lokalny strażnik danych wrażliwych — przed wysłaniem do AI",
    version="0.2.0",
)


class RedactRequest(BaseModel):
    text: str


@app.post("/api/redact")
def api_redact(req: RedactRequest) -> dict:
    """Redact PII from input text. Returns detections + redacted_text."""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    return redact_text(req.text)


# Static assets (CSS, JSX) served z /web/...
app.mount("/web", StaticFiles(directory=str(WEB_DIR)), name="web")


@app.get("/")
def root() -> FileResponse:
    """Serve main HTML."""
    return FileResponse(WEB_DIR / "index.html")


# Aliasy dla plików ładowanych względnie z index.html (np. <script src="app.jsx">)
@app.get("/{filename}")
def static_alias(filename: str) -> FileResponse:
    """Serve files from web/ at root (np. /styles.css, /app.jsx)."""
    file_path = WEB_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Not found: {filename}")
    return FileResponse(file_path)
