"""Launcher for the Android-FTA Web UI server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("android_fta.web_server:app", host="127.0.0.1", port=8000, reload=True)
