from __future__ import annotations

import typer

from commander_lab.candidates.cli import app as candidates_app
from commander_lab.engine.verify_cli import engine_verify

app = typer.Typer(no_args_is_help=True, help="Commander Playtest Lab utilities")
app.add_typer(candidates_app, name="candidates")
app.command("engine-verify")(engine_verify)

__all__ = ["app"]
