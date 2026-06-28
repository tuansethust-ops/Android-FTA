"""FastAPI server for the Android-FTA Web UI."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import queue
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from android_fta.core.batch_engine import BatchEngine, FilenameParser

# Project root directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _PROJECT_ROOT / "knowledge" / "skills"
_STRATEGIES_DIR = _PROJECT_ROOT / "knowledge" / "strategies"

app = FastAPI(title="Android-FTA Web Dashboard")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class SkillSettings(BaseModel):
    """Payload to update skill thresholds."""

    skill_name: str
    thresholds: dict[str, Any]


# ---------------------------------------------------------------------------
# Helper: Native Desktop Folder Picker
# ---------------------------------------------------------------------------


def _ask_directory() -> str:
    """Helper to open standard Windows folder dialog in a separate GUI thread."""
    import tkinter as tk  # noqa: PLC0415
    from tkinter import filedialog  # noqa: PLC0415

    q: queue.Queue[str] = queue.Queue()

    def worker() -> None:
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            directory = filedialog.askdirectory(parent=root, title="Select Trace Directory")
            root.destroy()
            q.put(directory)
        except Exception as exc:
            logging.getLogger(__name__).error("Tkinter folder picker failed: %s", exc)
            q.put("")

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    return q.get()


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/skills")
def get_skills() -> list[dict[str, Any]]:
    """Load and return all skill configurations."""
    if not _SKILLS_DIR.exists():
        raise HTTPException(status_code=500, detail=f"Skills directory {_SKILLS_DIR} not found.")

    skills = []
    for f in _SKILLS_DIR.glob("*.json"):
        try:
            with open(f, encoding="utf-8") as file:
                skills.append(json.load(file))
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to read skill {f.name}: {exc}"
            ) from exc
    return skills


@app.post("/api/settings")
def update_settings(settings: SkillSettings) -> dict[str, str]:
    """Save updated thresholds back to the skill's JSON file."""
    skill_file = _SKILLS_DIR / f"{settings.skill_name}.json"
    if not skill_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Skill file {settings.skill_name}.json not found."
        )

    try:
        with open(skill_file, "r+", encoding="utf-8") as f:
            data = json.load(f)
            data["thresholds"] = settings.thresholds
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
        return {"status": "success", "message": f"Updated {settings.skill_name} thresholds."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to write settings: {exc}") from exc


@app.post("/api/browse")
def browse_directory() -> dict[str, str]:
    """Trigger OS directory picker dialog on backend machine."""
    path = _ask_directory()
    return {"path": path}


# ---------------------------------------------------------------------------
# WebSocket Logs Handler & Compare Runner
# ---------------------------------------------------------------------------


class WebSocketLogHandler(logging.Handler):
    """Sends log messages to a WebSocket connection."""

    def __init__(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop) -> None:
        """Initialize the WebSocket log handler."""
        super().__init__()
        self.websocket = websocket
        self.loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record by sending it over the WebSocket."""
        msg = self.format(record)
        # Safely schedule the WebSocket send task on the FastAPI main loop thread
        asyncio.run_coroutine_threadsafe(
            self.websocket.send_text(json.dumps({"type": "log", "message": msg})),
            self.loop,
        )


def _resolve_tp_bin() -> str:
    """Find the trace_processor binary in common locations."""
    candidates = [
        _PROJECT_ROOT / "trace_processor.exe",  # Windows
        _PROJECT_ROOT / "trace_processor",  # Unix
        Path("trace_processor.exe"),
        Path("trace_processor"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return ""


@app.websocket("/ws/compare")
async def websocket_compare(websocket: WebSocket) -> None:
    """WebSocket endpoint to run batch comparisons and stream logs."""
    await websocket.accept()
    loop = asyncio.get_running_loop()

    # Create and add WebSocket logger handler to redirect package logs
    package_logger = logging.getLogger("android_fta")
    prev_level = package_logger.level
    package_logger.setLevel(logging.DEBUG)

    handler = WebSocketLogHandler(websocket, loop)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    package_logger.addHandler(handler)

    try:
        # Expecting configuration params payload
        data = await websocket.receive_text()
        params = json.loads(data)

        dut = params.get("dut")
        ref = params.get("ref")
        skill = params.get("skill", "startup_analysis")
        max_workers = int(params.get("max_workers", 4))
        parser_regex = params.get("parser_regex")

        if not dut or not ref:
            await websocket.send_text(
                json.dumps({"type": "error", "message": "Missing 'dut' or 'ref' path."})
            )
            return

        tp_bin = _resolve_tp_bin()
        if not tp_bin:
            await websocket.send_text(
                json.dumps({"type": "error", "message": "trace_processor binary not found."})
            )
            return

        # Run comparison in background thread to avoid blocking FastAPI server loop
        def run() -> Any:
            parser = FilenameParser(pattern=parser_regex)
            batch = BatchEngine(
                tp_bin_path=tp_bin,
                skills_dir=str(_SKILLS_DIR),
                strategies_dir=str(_STRATEGIES_DIR),
                parser=parser,
                max_workers=max_workers,
            )
            return batch.compare(dut, ref, skill_name=skill)

        # Execute on thread executor
        report = await loop.run_in_executor(None, run)

        # Convert report dataclass to dictionary
        report_dict = asdict(report)

        # Send completed results
        await websocket.send_text(json.dumps({"type": "result", "report": report_dict}))

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        package_logger.exception("WebSocket task failed")
        with contextlib.suppress(Exception):
            await websocket.send_text(
                json.dumps({"type": "error", "message": f"Server error: {exc}"})
            )
    finally:
        package_logger.removeHandler(handler)
        package_logger.setLevel(prev_level)


# ---------------------------------------------------------------------------
# Static Files Server (React build client)
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
else:
    # Fallback message for developer setup
    @app.get("/")
    def index() -> dict[str, str]:
        """Return a fallback JSON response if the static UI is not built."""
        return {"message": "Android-FTA Backend is running! Static UI folder not built yet."}
