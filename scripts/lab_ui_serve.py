"""Startskript der Commander Lab UI (lokal, localhost).

Beispiel:
    python scripts/lab_ui_serve.py --results-root ~/workspace/tmp/992
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from commander_lab.api.lab_ui import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Commander Lab UI starten")
    parser.add_argument("--repo-root", default=".", help="Repo-Wurzel")
    parser.add_argument(
        "--results-root",
        default="lab-ui-runs",
        help="Verzeichnis mit Vergleichs-Reports",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    app = create_app(Path(args.repo_root), Path(args.results_root))
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
