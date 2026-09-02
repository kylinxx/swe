from __future__ import annotations

import argparse
import socket
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "streamlit_app.py"


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def pick_port(start: int = 8501, limit: int = 20) -> int:
    for port in range(start, start + limit):
        if port_is_free(port):
            return port
    raise RuntimeError(f"No free port found in range {start}-{start + limit - 1}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the Streamlit demo on a free port.")
    parser.add_argument("--port", type=int, help="Use a specific port instead of auto-picking one.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    port = args.port if args.port is not None else pick_port()
    print(f"Launching Streamlit on http://localhost:{port}")

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
    ]
    return subprocess.call(command, cwd=str(REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
