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
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from . import (
    builder,
    card_outcomes,
    data_report,
    games,
    import_all,
    launch,
    queries,
    strength_view,
    universe,
    universe_view,
)
from . import evidence as evidence_model
from .decks import (
    RevisionCard,
    create_revision,
    lab_snapshot,
    list_rows,
    revision_rows,
    validate_rows,
)
from .images import cached_image, cached_image_by_name, public_card
from .launch import MAX_GAMES_PER_JVM, MAX_WORKERS, MIN_GAMES_PER_JVM, MIN_WORKERS
from .sources import source_inventory_payload
from .store import StudioStore, studio_data_dir
from .universe import UnknownUniverseCards

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


class BatchSimulationBody(BaseModel):
    revision_id: str = Field(min_length=1, max_length=200)
    pod: str = Field(default="precon", max_length=50)
    opponent_ids: list[str] | None = None
    games_count: int = Field(default=10, ge=1, le=100)
    base_seed: int = Field(default=1000, ge=0, le=2_000_000_000)
    seed_step: int = Field(default=1, ge=1, le=1000)
    style: float | None = Field(default=None, ge=0.0, le=1.0)
    workers: int | None = Field(default=None, ge=MIN_WORKERS, le=MAX_WORKERS)
    games_per_jvm: int | None = Field(default=None, ge=MIN_GAMES_PER_JVM, le=MAX_GAMES_PER_JVM)


class NamesBody(BaseModel):
    names: list[str] = Field(max_length=2000)


class DiffBody(BaseModel):
    base_revision_id: str
    cards: list[CardEntry]


class PrefilterBody(BaseModel):
    base_revision_id: str
    cards: list[CardEntry]
    trials: int = Field(default=2000, ge=50, le=20000)


class AlternativesBody(BaseModel):
    commander: list[str] = Field(min_length=1, max_length=2)
    in_deck: list[str] = Field(default_factory=list, max_length=300)
    skip: list[str] = Field(default_factory=list, max_length=5000)


class UniverseBody(BaseModel):
    """A universe spec as sent by the browser; absent fields mean "no filter"."""

    model_config = ConfigDict(extra="forbid")
    platforms: list[str] | None = Field(default=None, max_length=50)
    cohorts: list[str] | None = Field(default=None, max_length=100)
    commanders: list[str] | None = Field(default=None, max_length=10)
    date_from: str | None = Field(default=None, max_length=10)
    date_to: str | None = Field(default=None, max_length=10)
    min_main_cards: StrictInt | None = None
    min_universe: StrictInt | None = Field(default=None, ge=1)
    must_contain: list[str] | None = Field(default=None, max_length=20)


class StrengthBody(BaseModel):
    """Compute the strength index of one commander's pool; at most one settings source."""

    model_config = ConfigDict(extra="forbid")
    commander: str = Field(min_length=1, max_length=200)
    preset: str | None = Field(default=None, max_length=80)
    profile: str | None = Field(default=None, max_length=80)
    settings: dict[str, object] | None = None


class StrengthProfileBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: dict[str, object]


def _german(error: ValueError) -> str:
    """The German sentence for the validation errors the page can cause; other messages
    pass through unchanged. Unknown cards arrive as a structured error (a list of names)."""
    if isinstance(error, UnknownUniverseCards):
        return (
            f"Diese Karte kennt das Studio nicht: {', '.join(error.names)}. "
            "Wähle eine Karte aus der Vorschlagsliste."
        )
    return str(error)


def _inventory_summary() -> dict[str, object]:
    """Compact form of the qualified evidence-source inventory for /api/status:
    how many source layers exist and how they split over the review states."""
    inventory = source_inventory_payload()
    return {
        "schema_version": inventory["schema_version"],
        "total_sources": inventory["total_sources"],
        "status_counts": inventory["status_counts"],
    }


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
                # The three counts above are store totals over all commanders; this
                # says how many of them are bound to a commander at all.
                "source_data_binding": store.binding_counts(),
                "decks": store.count("deck"),
                "universe_profiles": store.count("universe_profile"),
                # The qualified evidence-source layers and their review states
                # (register in `sources.py`), so the data state is visible here;
                # the counted detail of every layer is under /api/data-report.
                "source_inventory": _inventory_summary(),
                "sources": sources,
            }
        finally:
            store.close()

    @app.get("/api/data-report")
    def data_report_route() -> dict[str, object]:
        """The counts-only data report (same payload as the CLI command), so the
        state of every data layer — collection, corpus, universes — is readable
        in the tool itself. No card name, deck address or note text leaves here."""
        store = open_store()
        try:
            return data_report.data_report(store)
        finally:
            store.close()

    @app.get("/api/layers")
    def layers(commander: str = Query(min_length=1, max_length=200)) -> dict[str, object]:
        """Per data layer of one commander: rows, pool cards covered, status and the exact
        import call, for the empty-state box of the pages."""
        store = open_store()
        try:
            return import_all.layer_overview(store, commander)
        finally:
            store.close()

    @app.get("/api/pool")
    def pool(
        commander: list[str] = Query(min_length=1, max_length=2),
        profile: str | None = Query(default=None, max_length=80),
    ) -> dict[str, object]:
        store = open_store()
        try:
            return builder.pool_cards(store, commander, profile=profile)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except KeyError as error:
            if profile is not None and str(error).strip("'") == profile:
                raise HTTPException(404, f"unknown universe profile: {error}") from error
            raise HTTPException(404, f"commander not in the collection: {error}") from error
        finally:
            store.close()

    @app.get("/api/commanders")
    def commanders(collection: bool = False) -> list[dict[str, object]]:
        store = open_store()
        try:
            return builder.list_commanders(store, include_collection=collection)
        finally:
            store.close()

    @app.get("/api/cohorts")
    def cohorts(
        commander: list[str] = Query(min_length=1, max_length=2),
    ) -> list[dict[str, object]]:
        store = open_store()
        try:
            return builder.cohort_shapes(store, commander)
        finally:
            store.close()

    @app.get("/api/cards/{card_id}")
    def card(
        card_id: str,
        commander: list[str] = Query(min_length=1, max_length=2),
        cohort: str = builder.ALL_DECKS,
    ) -> dict[str, object]:
        store = open_store()
        try:
            return builder.card_detail(store, card_id, commander, cohort=cohort)
        except KeyError as error:
            raise HTTPException(404, "unknown card") from error
        finally:
            store.close()

    @app.get("/api/evidence")
    def evidence(
        view: str = evidence_model.VIEW_COMMANDER,
        commander: list[str] = Query(default=[], max_length=2),
    ) -> dict[str, object]:
        """Evidence per pool card for the tier list view. Marks are not part of it."""
        if view not in evidence_model.VIEWS:
            raise HTTPException(422, "view must be 'commander' or 'global'")
        if view == evidence_model.VIEW_COMMANDER and not commander:
            raise HTTPException(422, "the commander view needs a commander")
        store = open_store()
        try:
            return evidence_model.pool_evidence(store, commander, view=view)
        except KeyError as error:
            raise HTTPException(404, f"commander not in the collection: {error}") from error
        finally:
            store.close()

    @app.get("/api/cards/{card_id}/evidence")
    def card_evidence(
        card_id: str,
        view: str = evidence_model.VIEW_COMMANDER,
        commander: list[str] = Query(default=[], max_length=2),
    ) -> dict[str, object]:
        if view not in evidence_model.VIEWS:
            raise HTTPException(422, "view must be 'commander' or 'global'")
        if view == evidence_model.VIEW_COMMANDER and not commander:
            raise HTTPException(422, "the commander view needs a commander")
        store = open_store()
        try:
            return evidence_model.card_evidence(store, card_id, commander, view=view)
        except KeyError as error:
            raise HTTPException(404, "unknown card or card outside this view") from error
        finally:
            store.close()

    @app.get("/api/strength/presets")
    def strength_presets() -> dict[str, object]:
        return strength_view.presets()

    @app.post("/api/strength")
    def strength_index(body: StrengthBody) -> dict[str, object]:
        """Strength index per pool card of one commander: an estimate from usage signals,
        not a measured win rate. Marks are not part of it. Needs the X-Studio header
        like every non-GET route, although it changes nothing."""
        store = open_store()
        try:
            settings = strength_view.resolve_settings(
                store, preset=body.preset, profile=body.profile, settings=body.settings
            )
            return dict(
                strength_view.compute(
                    store,
                    body.commander,
                    settings,
                    # a saved profile may point to a universe deleted since: fall back
                    # visibly instead of failing; explicit settings must name a real one
                    dangling_universe_ok=body.profile is not None,
                    notices=(
                        strength_view.profile_notices(store, body.profile)
                        if body.profile is not None
                        else ()
                    ),
                )
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except KeyError as error:
            raise HTTPException(
                404, f"unknown commander, preset, profile or universe profile: {error}"
            ) from error
        finally:
            store.close()

    @app.get("/api/strength/profiles")
    def strength_profiles() -> list[dict[str, object]]:
        store = open_store()
        try:
            return [dict(item) for item in strength_view.list_profiles(store)]
        finally:
            store.close()

    @app.get("/api/strength/profiles/{name}")
    def get_strength_profile(
        name: str = PathParam(min_length=1, max_length=80),
    ) -> dict[str, object]:
        store = open_store()
        try:
            return dict(strength_view.get_profile(store, name))
        except KeyError as error:
            raise HTTPException(404, "unknown strength profile") from error
        finally:
            store.close()

    @app.put("/api/strength/profiles/{name}")
    def save_strength_profile(
        body: StrengthProfileBody, name: str = PathParam(min_length=1, max_length=80)
    ) -> dict[str, object]:
        store = open_store()
        try:
            settings = strength_view.resolve_settings(
                store, preset=None, profile=None, settings=body.settings
            )
            return dict(strength_view.save_profile(store, name, settings))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.delete("/api/strength/profiles/{name}")
    def delete_strength_profile(
        name: str = PathParam(min_length=1, max_length=80),
    ) -> dict[str, object]:
        store = open_store()
        try:
            strength_view.delete_profile(store, name)
            return {"deleted": name}
        except KeyError as error:
            raise HTTPException(404, "unknown strength profile") from error
        finally:
            store.close()

    @app.get("/api/universe/options")
    def universe_options(
        commander: list[str] = Query(min_length=1, max_length=2),
    ) -> dict[str, object]:
        """The spec values the store holds, with deck counts — the only values a
        profile form should offer. The commander is required: the counts cover the decks
        bound to exactly this commander (or pair), never a figure mixed over commanders."""
        store = open_store()
        try:
            return dict(universe.options(store, commander_names=commander))
        finally:
            store.close()

    @app.get("/api/universe/profiles")
    def universe_profiles() -> list[dict[str, object]]:
        store = open_store()
        try:
            return universe.list_profiles(store)
        finally:
            store.close()

    @app.put("/api/universe/profiles/{name}")
    def save_universe_profile(
        body: UniverseBody,
        name: str = PathParam(min_length=1, max_length=80),
        commander: str = Query(min_length=1, max_length=200),
    ) -> dict[str, object]:
        store = open_store()
        try:
            if body.commanders and commander not in body.commanders:
                raise HTTPException(
                    422,
                    f"the universe is defined for {sorted(body.commanders)}, not for {commander}",
                )
            universe.save_profile(store, name, body.model_dump(exclude_none=True))
            return dict(universe_view.profile_summary(store, name, commander_names=[commander]))
        except ValueError as error:
            raise HTTPException(422, _german(error)) from error
        finally:
            store.close()

    @app.delete("/api/universe/profiles/{name}")
    def delete_universe_profile(
        name: str = PathParam(min_length=1, max_length=80),
    ) -> dict[str, object]:
        store = open_store()
        try:
            universe.delete_profile(store, name)
            return {"deleted": name}
        except KeyError as error:
            raise HTTPException(404, "unknown universe profile") from error
        finally:
            store.close()

    @app.get("/api/universe/profiles/{name}/summary")
    def universe_profile_summary(
        name: str, commander: str = Query(min_length=1, max_length=200)
    ) -> dict[str, object]:
        store = open_store()
        try:
            return dict(universe_view.profile_summary(store, name, commander_names=[commander]))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except KeyError as error:
            raise HTTPException(404, "unknown universe profile") from error
        finally:
            store.close()

    @app.get("/api/universe/spread")
    def universe_spread(
        profile: str = Query(min_length=1, max_length=80),
        commander: str = Query(min_length=1, max_length=200),
    ) -> dict[str, object]:
        """Counted spread of every Studio card in one universe. Marks are not part of it."""
        store = open_store()
        try:
            return dict(universe_view.pool_spread(store, profile, commander_names=[commander]))
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except KeyError as error:
            raise HTTPException(404, "unknown universe profile") from error
        finally:
            store.close()

    @app.get("/api/cards/{card_id}/universe")
    def card_universe(
        card_id: str,
        profile: str = Query(min_length=1, max_length=80),
        commander: str = Query(min_length=1, max_length=200),
    ) -> dict[str, object]:
        store = open_store()
        try:
            return dict(
                universe_view.pool_spread(store, profile, [card_id], commander_names=[commander])
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except KeyError as error:
            raise HTTPException(404, "unknown universe profile or card") from error
        finally:
            store.close()

    @app.get("/api/cards/{card_id}/cooccurrence")
    def card_cooccurrence(
        card_id: str,
        profile: str | None = Query(default=None, min_length=1, max_length=80),
        limit: int = Query(default=25, ge=1, le=500),
        commander: str = Query(min_length=1, max_length=200),
        must_contain: list[str] = Query(default=[], max_length=20),
    ) -> dict[str, object]:
        """Cards played with one card: over a stored universe (``profile``) or, without one,
        over the commander's decks that contain every card of ``must_contain``."""
        if profile is None and not must_contain:
            raise HTTPException(422, "Gib ein Universum oder Filterkarten an.")
        store = open_store()
        try:
            spec = (
                universe_view.filtered_spec(
                    store, must_contain, commander_names=[commander], profile=profile
                )
                if must_contain
                else None
            )
            return dict(
                universe_view.card_cooccurrence(
                    store,
                    None if spec is not None else profile,
                    card_id,
                    limit,
                    commander_names=[commander],
                    spec=spec,
                )
            )
        except ValueError as error:
            raise HTTPException(422, _german(error)) from error
        except KeyError as error:
            raise HTTPException(404, "unknown universe profile or card") from error
        finally:
            store.close()

    @app.get("/api/deck-filter")
    def deck_filter(
        commander: str = Query(min_length=1, max_length=200),
        card: list[str] = Query(default=[], max_length=20),
        profile: str | None = Query(default=None, min_length=1, max_length=80),
    ) -> dict[str, object]:
        """Source-deck figures over only the commander's decks that contain ALL chosen
        cards ("Teilmenge: N von M Decks"). Only cards of the commander's pool can be chosen."""
        store = open_store()
        try:
            try:
                pool = queries.legal_pool(store, [commander])
            except KeyError as error:
                raise HTTPException(404, f"commander not in the collection: {error}") from error
            if any(not name.strip() for name in card):
                raise HTTPException(
                    422, "Leerer Kartenname. Wähle eine Karte aus der Vorschlagsliste."
                )
            if any(name.casefold() == commander.casefold() for name in card):
                raise HTTPException(
                    422,
                    f"{commander} ist der Commander und steckt in jedem Deck. "
                    "Wähle eine andere Karte als Filter.",
                )
            pool_names = {str(row["oracle_name"]) for row in pool}
            outside = sorted({name for name in card if name not in pool_names})
            if outside:
                raise HTTPException(
                    422,
                    f"Diese Karte gehört nicht zum Kartenpool von {commander}: "
                    f"{', '.join(outside)}. Wähle eine Karte aus der Vorschlagsliste.",
                )
            return dict(
                universe_view.deck_filter(
                    store,
                    card,
                    commander_names=[commander],
                    profile=profile,
                    card_ids=[str(row["card_id"]) for row in pool],
                )
            )
        except ValueError as error:
            raise HTTPException(422, _german(error)) from error
        except KeyError as error:
            raise HTTPException(404, "unknown universe profile") from error
        finally:
            store.close()

    @app.post("/api/cards/{card_id}/alternatives")
    def alternatives(card_id: str, body: AlternativesBody) -> dict[str, object]:
        """Free cards with a shared role: a comparison of function, never a claimed upgrade."""
        store = open_store()
        try:
            return evidence_model.role_alternatives(
                store, card_id, body.commander, in_deck=body.in_deck, skip=body.skip
            )
        except KeyError as error:
            raise HTTPException(404, "unknown card or commander") from error
        finally:
            store.close()

    @app.get("/api/simulations")
    def simulations(
        commander: list[str] = Query(min_length=1, max_length=2),
    ) -> list[dict[str, object]]:
        store = open_store()
        try:
            return builder.list_simulations(store, commander)
        finally:
            store.close()

    @app.post("/api/simulations/batch")
    def run_simulation_batch(body: BatchSimulationBody) -> dict[str, object]:
        store = open_store()
        try:
            from .simulations import simulation_manager

            batch = simulation_manager.start_batch(
                store,
                games_home(),
                revision_id=body.revision_id,
                pod=body.pod,
                opponent_ids=body.opponent_ids,
                games_count=body.games_count,
                base_seed=body.base_seed,
                seed_step=body.seed_step,
                style=body.style,
                workers=body.workers,
                games_per_jvm=body.games_per_jvm,
            )
            return {
                "batch_id": batch.batch_id,
                "status": batch.status,
                "execution": batch.execution(),
            }
        except KeyError as error:
            raise HTTPException(404, "unknown deck revision") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        finally:
            store.close()

    @app.get("/api/simulations/batch/{batch_id}")
    def get_simulation_batch(batch_id: str) -> dict[str, object]:
        from .simulations import simulation_manager

        batch = simulation_manager.get_batch(batch_id)
        if batch is None:
            raise HTTPException(404, "unknown batch")
        return batch.to_dict()

    @app.post("/api/simulations/batch/{batch_id}/cancel")
    def cancel_simulation_batch(batch_id: str) -> dict[str, object]:
        from .simulations import simulation_manager

        cancelled = simulation_manager.cancel_batch(batch_id)
        if not cancelled:
            raise HTTPException(404, "unknown batch")
        batch = simulation_manager.get_batch(batch_id)
        return batch.to_dict() if batch else {"cancelled": True}

    @app.get("/api/simulations/batches")
    def list_simulation_batches() -> list[dict[str, object]]:
        from .simulations import simulation_manager

        return simulation_manager.list_batches()

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

    @app.get("/api/outcomes")
    def outcomes(
        deck_id: str = Query(min_length=1, max_length=200),
        min_exposed: int = Query(default=card_outcomes.DEFAULT_MIN_EXPOSED, ge=1, le=100_000),
    ) -> dict[str, object]:
        """Per-card win rate with the card in the first dealt hand versus not (simulated)."""
        try:
            table = card_outcomes.outcomes_for_folder(
                games.games_folder(games_home()), deck_id=deck_id, min_exposed=min_exposed
            )
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        return dict(table)

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

    @app.get("/api/engine/missing-cards")
    def engine_missing_cards(revision_id: str | None = None) -> dict[str, object]:
        """Check for cards missing pilot knowledge or unsupported by XMage."""
        store = open_store()
        try:
            if revision_id:
                snapshot = lab_snapshot(store, revision_id)
                return {
                    "revision_id": revision_id,
                    "unknown_to_pilots": launch.cards_unknown_to_pilots(snapshot),
                    "unsupported_by_engine": launch.cards_unsupported_by_engine(snapshot),
                }
            return {
                "collection_unknown_to_pilots": launch.collection_cards_unknown_to_pilots(store),
                "collection_unsupported_by_engine": launch.collection_cards_unsupported_by_engine(
                    store
                ),
            }
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
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
