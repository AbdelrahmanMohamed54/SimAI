# server/api.py

import os
import asyncio
from pathlib import Path # <-- ADD THIS IMPORT
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from server.ws_manager import ws_manager
from pipeline.realtime_pipeline import pipeline_entrypoint as pipeline_main

# -------------------------------------------------
# FASTAPI APP
# -------------------------------------------------
app = FastAPI(title="SimAI Realtime Translation Server")

# Allow browser UI → backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # In production, replace with your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# STATIC FRONTEND MOUNT  <-- MODIFIED SECTION
# -------------------------------------------------

# Use pathlib for robust pathing:
# 1. Path(__file__) is /home/site/wwwroot/server/api.py
# 2. .parent.parent moves up two directories to /home/site/wwwroot (the project root)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Serve frontend files at /static/*
app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static",
)

# Serve index.html at the root (/)
@app.get("/")
async def serve_index():
    # FileResponse requires a string path, so we use str() on the Path object
    return FileResponse(str(FRONTEND_DIR / "index.html"))

# -------------------------------------------------
# WEBSOCKETS
# ... (rest of the file is unchanged)
# -------------------------------------------------
# WEBSOCKETS
# -------------------------------------------------

@app.websocket("/ws/text/{lang}")
async def ws_text(websocket: WebSocket, lang: str):
    """
    Clients subscribe here to receive JSON text segments for a given target language.
    """
    await ws_manager.connect_text(lang, websocket)

    try:
        while True:
            await websocket.receive_text()  # keep open
    except WebSocketDisconnect:
        await ws_manager.disconnect_text(lang, websocket)
    except Exception:
        await ws_manager.disconnect_text(lang, websocket)


@app.websocket("/ws/audio/{lang}")
async def ws_audio(websocket: WebSocket, lang: str):
    """
    Clients subscribe here to receive PCM audio for a given target language.
    """
    await ws_manager.connect_audio(lang, websocket)

    try:
        while True:
            await websocket.receive_bytes()  # keep open
    except WebSocketDisconnect:
        await ws_manager.disconnect_audio(lang, websocket)
    except Exception:
        await ws_manager.disconnect_audio(lang, websocket)


# -------------------------------------------------
# PIPELINE STARTUP
# -------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """
    Start pipeline as a background task on FastAPI's event loop.
    """
    print("[API] Starting real-time pipeline...")
    loop = asyncio.get_running_loop()

    # Import here to avoid circular dependencies
    from pipeline.realtime_pipeline import RealTimePipeline
    
    # Create and store pipeline instance
    app.state.pipeline = RealTimePipeline()
    
    # Store the task so we can cancel it on shutdown
    app.state.pipeline_task = None

    async def pipeline_wrapper():
        try:
            await app.state.pipeline.run()
        except asyncio.CancelledError:
            print("[API] Pipeline task cancelled")
            raise
        except Exception as e:
            print(f"[API] Pipeline error: {e}")

    app.state.pipeline_task = loop.create_task(pipeline_wrapper())


# ADD THIS NEW SHUTDOWN HANDLER
@app.on_event("shutdown")
async def shutdown_event():
    """
    Gracefully shutdown pipeline on server stop.
    """
    print("[API] Shutting down pipeline...")
    
    # Set global shutdown flag
    from pipeline.realtime_pipeline import SHUTDOWN
    import pipeline.realtime_pipeline as pipeline_module
    pipeline_module.SHUTDOWN = True
    
    # Cancel the pipeline task
    if hasattr(app.state, 'pipeline_task') and app.state.pipeline_task:
        app.state.pipeline_task.cancel()
        try:
            await asyncio.wait_for(app.state.pipeline_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    
    print("[API] Pipeline shutdown complete")

