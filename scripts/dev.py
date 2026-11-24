"""Cross-platform one-command dev launcher for Farmacia Lumen BI & Operations."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "farmacia.db"
ARCHIVE_PATH = ROOT_DIR / "problema2_database.sql.tar.gz"
FRONTEND_DIR = ROOT_DIR / "frontend"


def resolve_python() -> str:
    """Prefer project .venv interpreter if available, otherwise sys.executable."""
    candidates = (
        [ROOT_DIR / ".venv" / "Scripts" / "python.exe"]
        if os.name == "nt"
        else [ROOT_DIR / ".venv" / "bin" / "python"]
    )
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return sys.executable


def resolve_npm() -> str:
    """Use npm.cmd on Windows to avoid PowerShell execution policy errors."""
    name = "npm.cmd" if os.name == "nt" else "npm"
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"'{name}' not found in PATH. Install Node.js (v18+).")
    return found


def ensure_database(python_bin: str) -> None:
    """Build and index data/farmacia.db automatically if missing."""
    if DB_PATH.exists():
        return
    if not ARCHIVE_PATH.exists():
        print(
            f"[ERROR] Database missing at {DB_PATH} and archive not found at {ARCHIVE_PATH}.\n"
            "        Place 'problema2_database.sql.tar.gz' in the repository root and re-run."
        )
        sys.exit(1)
    print(f"Database not found at {DB_PATH}. Running scripts/setup_db.py...")
    subprocess.run([python_bin, str(ROOT_DIR / "scripts" / "setup_db.py")], check=True)


def terminate_process(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            proc.terminate()
            proc.wait(timeout=5)
    except Exception:
        proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Farmacia Lumen backend and frontend.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate environment (DB, Python, npm, node_modules) without starting servers.",
    )
    args = parser.parse_args()

    python_bin = resolve_python()
    npm_bin = resolve_npm()
    ensure_database(python_bin)

    if not (FRONTEND_DIR / "node_modules").exists():
        print(
            f"[ERROR] frontend/node_modules not found. Run: cd frontend && {Path(npm_bin).name} install"
        )
        sys.exit(1)

    if args.check:
        print(f"[OK] Python:   {python_bin}")
        print(f"[OK] npm:      {npm_bin}")
        print(f"[OK] Database: {DB_PATH} ({DB_PATH.stat().st_size:,} bytes)")
        print(f"[OK] Frontend: {FRONTEND_DIR}")
        return

    backend_cmd = [
        python_bin,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    frontend_cmd = [npm_bin, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"]

    print("Starting Farmacia Lumen BI & Operations...")
    print("  Dashboard UI : http://127.0.0.1:5173")
    print("  FastAPI Docs : http://127.0.0.1:8000/docs")
    print("  Press Ctrl+C to stop both servers.\n")

    backend_proc: subprocess.Popen[bytes] | None = None
    frontend_proc: subprocess.Popen[bytes] | None = None
    try:
        backend_proc = subprocess.Popen(backend_cmd, cwd=str(ROOT_DIR))
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=str(FRONTEND_DIR))

        while True:
            b_code = backend_proc.poll()
            f_code = frontend_proc.poll()
            if b_code is not None:
                print(f"\nBackend process exited with code {b_code}. Stopping frontend...")
                break
            if f_code is not None:
                print(f"\nFrontend process exited with code {f_code}. Stopping backend...")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nShutting down servers...")
    finally:
        terminate_process(frontend_proc)
        terminate_process(backend_proc)
        print("Stopped cleanly.")


if __name__ == "__main__":
    main()
