"""Web UI routes for QuickExpense."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

# Get the absolute path to the templates directory
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"

router = APIRouter(tags=["web-ui"])


@router.get("/", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    """Serve the main web interface."""
    index_path = TEMPLATES_DIR / "index.html"

    try:
        html_content = index_path.read_text(encoding="utf-8")
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Web interface not found") from e


@router.get("/demo", response_class=HTMLResponse)
async def serve_demo() -> HTMLResponse:
    """Serve the web interface at /demo alias."""
    index_path = TEMPLATES_DIR / "index.html"

    try:
        html_content = index_path.read_text(encoding="utf-8")
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Web interface not found") from e
