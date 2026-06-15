#!/usr/bin/env python3
"""
Root launcher for the Self-Healing HR Ops Platform.

Starts backend (FastAPI), frontend (Vite dev server), and opens browser tabs.
Cross-platform: Windows, macOS, Linux.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("hr_ops.launcher")

BACKEND_PORT = 8000
FRONTEND_PORT = 5173
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"
SWAGGER_URL = f"{BACKEND_URL}/docs"
REDOC_URL = f"{BACKEND_URL}/redoc"

processes: list[subprocess.Popen] = []


def _find_python() -> str:
    if sys.platform == "win32":
        venv_python = Path(".venv/Scripts/python.exe")
        if venv_python.exists():
            return str(venv_python)
        venv_python = Path("venv/Scripts/python.exe")
        if venv_python.exists():
            return str(venv_python)
    else:
        venv_python = Path(".venv/bin/python")
        if venv_python.exists():
            return str(venv_python)
        venv_python = Path("venv/bin/python")
        if venv_python.exists():
            return str(venv_python)
    return sys.executable


def _find_npm() -> str:
    if sys.platform == "win32":
        npm = subprocess.run(
            "where npm", capture_output=True, text=True, shell=True
        )
        if npm.returncode == 0:
            return npm.stdout.strip().split("\n")[0]
    else:
        npm = subprocess.run(
            "which npm", capture_output=True, text=True, shell=True
        )
        if npm.returncode == 0:
            return npm.stdout.strip()
    return "npm"


def _open_browser(url: str, delay: float = 0.5):
    time.sleep(delay)
    try:
        webbrowser.open(url)
        logger.info("Opened browser: %s", url)
    except Exception as e:
        logger.warning("Failed to open browser: %s", e)


def _start_backend(python: str) -> subprocess.Popen:
    logger.info("Starting backend on %s ...", BACKEND_URL)
    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )
    processes.append(proc)
    return proc


def _start_frontend(npm: str) -> subprocess.Popen:
    logger.info("Starting frontend on %s ...", FRONTEND_URL)
    proc = subprocess.Popen(
        [npm, "run", "dev"],
        cwd="frontend",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
    )
    processes.append(proc)
    return proc


def _wait_for_health(url: str, timeout: int = 180) -> bool:
    import urllib.request
    import urllib.error

    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(f"{url}/health", timeout=2)
            if resp.status == 200:
                return True
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(1)
    return False


def _print_ready():
    print("\n" + "=" * 60)
    print("  HR Ops Platform is running!")
    print("=" * 60)
    print(f"  Frontend:     {FRONTEND_URL}")
    print(f"  Backend API:  {BACKEND_URL}")
    print(f"  Swagger Docs: {SWAGGER_URL}")
    print(f"  ReDoc Docs:   {REDOC_URL}")
    print("=" * 60)
    print("  Press Ctrl+C to stop all services\n")


def _stream_output(proc: subprocess.Popen, prefix: str):
    try:
        for line in iter(proc.stdout.readline, ""):
            if line:
                print(f"[{prefix}] {line.rstrip()}")
    except (BrokenPipeError, OSError):
        pass


def _cleanup(signum=None, frame=None):
    logger.info("Shutting down all services...")
    for proc in processes:
        if proc.poll() is None:
            if sys.platform == "win32":
                proc.terminate()
            else:
                proc.send_signal(signal.SIGTERM)
    logger.info("All services stopped.")


def main():
    import threading

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    python = _find_python()
    npm = _find_npm()

    backend_proc = _start_backend(python)
    frontend_proc = _start_frontend(npm)

    threading.Thread(
        target=_stream_output, args=(backend_proc, "backend"), daemon=True
    ).start()
    threading.Thread(
        target=_stream_output, args=(frontend_proc, "frontend"), daemon=True
    ).start()

    logger.info("Waiting for backend to become healthy...")
    if _wait_for_health(BACKEND_URL):
        logger.info("Backend is healthy!")
    else:
        logger.warning("Backend health check timed out.")

    _print_ready()

    _open_browser(FRONTEND_URL, 1.0)
    _open_browser(SWAGGER_URL, 1.5)
    _open_browser(REDOC_URL, 2.0)

    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        _cleanup()


if __name__ == "__main__":
    main()
