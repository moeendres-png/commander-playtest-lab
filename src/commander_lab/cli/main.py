from __future__ import annotations

from commander_lab.candidates.cli import app as candidates_app
from commander_lab.cli.app import app

app.add_typer(candidates_app, name="candidates")

__all__ = ["app"]
