"""Development server entrypoint for the FastAPI communication layer."""

from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run("src.api.app:app", host="127.0.0.1", port=8000, reload=True)
