"""Local web application of the Studio deck builder.

It listens on this machine only. The browser gets card data, deck lists and counts from
the Studio store; card images come from the local image cache. Nothing here decides rules:
the data check reads stored facts, the Rules Core stays the binding check for play.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import builder, games, launch
from .decks import (
    RevisionCard,
    create_revision,
    lab_snapshot,
    list_rows,
    revision_rows,
    validate_rows,
)
from .images import cached_image, cached_image_by_name, public_card
from .store import StudioStore, studio_data_dir

STATIC = Path(__file__).resolve().parent / "static"
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "testserver"})
_SLUG = re.compile(r"[^a-z0-9]+")
_CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class CardEntry(BaseModel):
    card_id: str
    quantity: int = Field(default=1, ge=1, le=99)
    zone: str = Field(default="main", pattern="^(commander|main)$")


class ListBody(BaseModel):
    cards: list[CardEntry]
    owned_only: bool = True


class DraftBody(BaseModel):
    cards: list[CardEntry]
    base_revision_id: str | None = None


class RevisionBody(BaseModel):
    cards: list[CardEntry]
    branch: str = Field(default="main", min_length=1, max_length=60)
    note: str = Field(default="", max_length=500)
    parent_revision_id: str | None = None


class DeckBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    commander_card_ids: list[str] = Field(min_length=1, max_length=2)


class MarkBody(BaseModel):
    favorite: bool = False
    excluded: bool = False
    note: str = Field(default="", max_length=2000)


class GameBody(BaseModel):
    revision_id: str = Field(min_length=1, max_length=200)
    opponent_ids: list[str] = Field(min_length=1, max_length=5)
    seed: int = Field(ge=0, le=2_000_000_000)
    style: float | None = Field(default=None, ge=0.0, le=1.0)
    seat_styles: list[float] | None = None


class NamesBody(BaseModel):
    names: list[str] = Field(max_length=2000)


class DiffBody(BaseModel):
    base_revision_id: str
    cards: list[CardEntry]


class PrefilterBody(BaseModel):
    base_revision_id: str
    cards: list[CardEntry]
    trials: int = Field(default=2000, ge=50, le=20000)


def _cards(entries: list[CardEntry]) -> list[RevisionCard]:
    return [RevisionCard(entry.card_id, entry.quantity, entry.zone) for entry in entries]


def create_app(data_folder: str | Path | None = None) -> FastAPI:
    """The Studio application. ``data_folder`` is the Studio data folder (default: from the
    environment)."""
    app = FastAPI(title="Commander Studio", docs_url=None, redoc_url=None, openapi_url=None)

    def open_store() -> StudioStore:
        return StudioStore.open(data_folder)

    @app.middleware("http")
    async def local_only(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = request.headers.get("host", "").rsplit(":", 1)[0]
        if host not in _LOCAL_HOSTS:
            return JSONResponse({"detail": "local use only"}, status_code=403)
        if request.method not in {"GET", "HEAD"} and request.headers.get("x-studio") != "1":
            return JSONResponse({"detail": "missing request marker"}, status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/status")
    def status() -> dict[str, object]:
        store = open_store()
        try:
            sources = [
                dict(row)
                for row in store.connection.execute(
                    "SELECT title, data_class, SUBSTR(sha256, 1, 12) AS sha256, imported_at "
                    "FROM source ORDER BY imported_at"
                )
            ]
            return {
                "cards": store.count("card"),
                "public_cards": store.count("scryfall_card"),
                "source_decks": store.count("corpus_deck"),
                "neutral_board_rows": store.count("neutral_board_row"),
                "simulation_runs": store.count("simulation_run"),
                "decks": store.count("deck"),
                "sources": sources,
            }
        finally:
            store.close()

    @app.get("/api/pool")
    def pool(commander: list[str] = Query(min_length=1, max_length=2)) -> dict[str, object]:
        store = open_store()
        try:
            return builder.pool_cards(store, commander)
        except KeyError as error:
            raise HTTPException(404, f"commander not in the collection: {error}") from error
        finally:
            store.close()

    @app.get("/api/cohorts")
    def cohorts() -> list[dict[str, object]]:
        store = open_store()
        try:
            return builder.cohort_shapes(store)
        finally:
            store.close()

    @app.get("/api/cards/{card_id}")
    def card(card_id: str, cohort: str = builder.ALL_DECKS) -> dict[str, object]:
        store = open_store()
        try:
            return builder.card_detail(store, card_id, cohort=cohort)
        except KeyError as error:
            raise HTTPException(404, "unknown card") from error
        finally:
            store.close()

    @app.get("/api/simulations")
    def simulations() -> list[dict[str, object]]:
        store = open_store()
        try:
            return builder.list_simulations(store)
        finally:
            store.close()

    @app.post("/api/diff")
    def diff(body: DiffBody) -> dict[str, object]:
        store = open_store()
        try:
            base_rows = revision_rows(store, body.base_revision_id)
            base_cards = [
                RevisionCard(str(r["card_id"]), int(r["quantity"]), str(r["zone"]))
                for r in base_rows
            ]
            return builder.diff_lists(store, base_cards, _cards(body.cards))
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.post("/api/prefilter")
    def prefilter(body: PrefilterBody) -> dict[str, object]:
        store = open_store()
        try:
            base_rows = revision_rows(store, body.base_revision_id)
            base_cards = [
                RevisionCard(str(r["card_id"]), int(r["quantity"]), str(r["zone"]))
                for r in base_rows
            ]
            return builder.prefilter_lists(
                store, base_cards, _cards(body.cards), trials=body.trials
            )
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.put("/api/cards/{card_id}/mark")
    def mark(card_id: str, body: MarkBody) -> dict[str, object]:
        store = open_store()
        try:
            builder.set_mark(
                store, card_id, favorite=body.favorite, excluded=body.excluded, note=body.note
            )
            return {"card_id": card_id, **body.model_dump()}
        except KeyError as error:
            raise HTTPException(404, "unknown card") from error
        finally:
            store.close()

    @app.get("/api/decks")
    def decks() -> list[dict[str, object]]:
        store = open_store()
        try:
            return builder.list_decks(store)
        finally:
            store.close()

    @app.post("/api/decks")
    def new_deck(body: DeckBody) -> dict[str, object]:
        store = open_store()
        try:
            base = _SLUG.sub("-", body.name.casefold()).strip("-") or "deck"
            deck_id = base
            number = 2
            while store.connection.execute(
                "SELECT 1 FROM deck WHERE deck_id = ?", (deck_id,)
            ).fetchone():
                deck_id = f"{base}-{number}"
                number += 1
            cards = [RevisionCard(card_id, 1, "commander") for card_id in body.commander_card_ids]
            revision_id = create_revision(store, deck_id=deck_id, name=body.name, cards=cards)
            return {"deck_id": deck_id, "revision_id": revision_id}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.get("/api/decks/{deck_id}/history")
    def deck_history(deck_id: str) -> list[dict[str, object]]:
        store = open_store()
        try:
            return builder.history(store, deck_id)
        finally:
            store.close()

    @app.get("/api/decks/{deck_id}/branches/{branch}/draft")
    def get_draft(deck_id: str, branch: str) -> dict[str, object]:
        store = open_store()
        try:
            return {"draft": builder.read_draft(store, deck_id, branch)}
        finally:
            store.close()

    @app.put("/api/decks/{deck_id}/branches/{branch}/draft")
    def put_draft(deck_id: str, branch: str, body: DraftBody) -> dict[str, object]:
        store = open_store()
        try:
            if not store.connection.execute(
                "SELECT 1 FROM deck WHERE deck_id = ?", (deck_id,)
            ).fetchone():
                raise HTTPException(404, "unknown deck")
            builder.write_draft(store, deck_id, branch, _cards(body.cards), body.base_revision_id)
            return {"saved": True}
        finally:
            store.close()

    @app.delete("/api/decks/{deck_id}/branches/{branch}/draft")
    def delete_draft(deck_id: str, branch: str) -> dict[str, object]:
        store = open_store()
        try:
            builder.drop_draft(store, deck_id, branch)
            return {"dropped": True}
        finally:
            store.close()

    @app.post("/api/decks/{deck_id}/revisions")
    def save_revision(deck_id: str, body: RevisionBody) -> dict[str, object]:
        store = open_store()
        try:
            deck = store.connection.execute(
                "SELECT name FROM deck WHERE deck_id = ?", (deck_id,)
            ).fetchone()
            if deck is None:
                raise HTTPException(404, "unknown deck")
            revision_id = create_revision(
                store,
                deck_id=deck_id,
                name=str(deck["name"]),
                cards=_cards(body.cards),
                parent_revision_id=body.parent_revision_id,
                note=body.note,
                branch=body.branch,
            )
            builder.drop_draft(store, deck_id, body.branch)
            return {"revision_id": revision_id}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.get("/api/revisions/{revision_id}")
    def revision(revision_id: str, owned_only: bool = True) -> dict[str, object]:
        store = open_store()
        try:
            rows = revision_rows(store, revision_id)
            return {
                "revision_id": revision_id,
                "cards": [
                    {"card_id": r["card_id"], "quantity": r["quantity"], "zone": r["zone"]}
                    for r in rows
                ],
                "issues": [asdict(i) for i in validate_rows(rows, owned_only=owned_only)],
                "shape": builder.deck_shape(rows),
                "roles": builder.deck_roles(
                    store, [RevisionCard(r["card_id"], r["quantity"], r["zone"]) for r in rows]
                ),
            }
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.get("/api/revisions/{revision_id}/export")
    def export(revision_id: str, format: str = "txt") -> Response:
        store = open_store()
        try:
            if format == "json":
                return JSONResponse(lab_snapshot(store, revision_id))
            rows = revision_rows(store, revision_id)
            lines = [f"{row['quantity']} {row['engine_name']}" for row in rows]
            return PlainTextResponse("\n".join(lines) + "\n")
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.post("/api/check")
    def check(body: ListBody) -> dict[str, object]:
        store = open_store()
        try:
            rows = list_rows(store, _cards(body.cards))
            return {
                "issues": [asdict(i) for i in validate_rows(rows, owned_only=body.owned_only)],
                "shape": builder.deck_shape(rows),
                "roles": builder.deck_roles(store, _cards(body.cards)),
            }
        finally:
            store.close()

    @app.get("/img/{card_id}")
    def image(card_id: str, face: str = "front") -> Response:
        if face not in {"front", "back"}:
            raise HTTPException(422, "face is front or back")
        store = open_store()
        try:
            path = cached_image(store, card_id, face)
        finally:
            store.close()
        if path is None:
            raise HTTPException(404, "no image")
        return FileResponse(
            path, media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"}
        )

    def games_home() -> Path:
        return Path(data_folder).resolve() if data_folder is not None else studio_data_dir()

    @app.get("/api/games")
    def game_list() -> list[dict[str, object]]:
        return games.list_games(games_home())

    @app.get("/api/table")
    def table() -> dict[str, object]:
        """What a new game can be made of: the engine, the own decks, the other seats."""
        store = open_store()
        try:
            return {
                "engine": launch.engine_state(games_home()),
                "decks": builder.list_decks(store),
                "opponents": launch.opponent_decks(),
                "pods": {k: list(v) for k, v in launch.POD_PRESETS.items()},
            }
        finally:
            store.close()

    @app.post("/api/games")
    def new_game(body: GameBody) -> dict[str, object]:
        store = open_store()
        try:
            game_id = launch.start_game(
                store,
                games_home(),
                revision_id=body.revision_id,
                opponent_ids=body.opponent_ids,
                seed=body.seed,
                style=body.style,
                seat_styles=body.seat_styles,
            )
            return {"game_id": game_id}
        except KeyError as error:
            raise HTTPException(404, "unknown deck") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        finally:
            store.close()

    @app.get("/api/games/{game_id}")
    def game(
        game_id: str,
        start: int = Query(default=0, ge=0),
        count: int = Query(default=200, ge=0, le=1000),
    ) -> dict[str, object]:
        try:
            return games.read_game(games_home(), game_id, start=start, count=count)
        except (KeyError, ValueError) as error:
            raise HTTPException(404, "unknown game") from error

    @app.delete("/api/games/{game_id}")
    def delete_game(game_id: str) -> dict[str, object]:
        try:
            deleted = games.delete_game(games_home(), game_id)
            return {"deleted": deleted, "game_id": game_id}
        except (KeyError, ValueError) as error:
            raise HTTPException(404, "unknown game") from error

    @app.post("/api/public-cards")
    def public_cards(body: NamesBody) -> dict[str, object]:
        store = open_store()
        try:
            found: dict[str, object] = {}
            for name in body.names:
                card = public_card(store, name)
                if card is not None:
                    card.pop("image_front", None)
                    found[name] = card
            return found
        finally:
            store.close()

    @app.get("/img-name")
    def image_by_name(name: str = Query(min_length=1, max_length=200)) -> Response:
        store = open_store()
        try:
            path = cached_image_by_name(store, name)
        finally:
            store.close()
        if path is None:
            raise HTTPException(404, "no image")
        return FileResponse(
            path, media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"}
        )

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
