"""
Run the API for development, from the project root:

    .venv\\Scripts\\python -m backend

Serves http://127.0.0.1:8000 and reloads automatically when any file under backend/ changes. Stop with Ctrl+C.
Set LPIP_API_PORT to use another port.
"""
import os
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    os.chdir(ROOT)  # the app resolves data/ and db/ from the project root
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=int(os.environ.get("LPIP_API_PORT", "8000")),
                reload=True, reload_dirs=[str(ROOT / "backend")])
