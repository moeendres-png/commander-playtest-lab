"""Local web application of the Studio deck builder.

It listens on this machine only. The browser gets card data, deck lists and counts from
the Studio store; card images are loaded directly from ``https://cards.scryfall.io`` with
``referrerpolicy="no-referrer"`` (legacy ``/img/...`` routes redirect there with 302).
Nothing here decides rules: the data check reads stored facts, the Rules Core stays the
binding check for play.
"""

from __future__ import annotations

import copy
import json
import re
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi import Path as PathParam
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from . import (
    allocation,
    answer_cache,
    build_list,
    builder,
    cache,
    card_duel,
    card_outcomes,
    card_understanding,
    castability,
    combos,
    cut_lab,
    data_report,
    deck_diff,
    deck_evidence,
    deck_facts,
    deck_modules,
    deck_series,
    engine_check,
    games,
    import_all,
    labels,
    land_advisor,
    launch,
    overall_rating,
    packages,
    paired_comparison,
    paired_series,
    play,
    queries,
    roles,
    signals,
    similar_decks,
    strength,
    strength_view,
    swap,
    tier_snapshot,
    tokens,
    tournament_conversion,
    universe,
    universe_choice,
    universe_view,
)
from . import evidence as evidence_model
from .decks import (
    EXPORT_TEXT_FORMATS,
    MAX_PRIMER_CHARS,
    RevisionCard,
    baseline_decks_for_commander,
    color_set,
    create_revision,
    export_deck_dossier,
    export_text,
    format_primer_comments,
    get_deck_primer,
    lab_snapshot,
    list_rows,
    parse_decklist_text,
    resolve_repo_baseline_cards,
    revision_rows,
    set_deck_primer,
    validate_rows,
)
from .images import image_cache_status, public_card, web_image_url, web_image_url_by_name
from .launch import MAX_GAMES_PER_JVM, MAX_WORKERS, MIN_GAMES_PER_JVM, MIN_WORKERS
from .source_layers import freshness as source_freshness
from .source_layers import recent_dated_sources, source_layers
from .sources import source_inventory_payload
from .store import StudioStore, studio_data_dir
from .universe import UnknownUniverseCards

STATIC = Path(__file__).resolve().parent / "static"
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "testserver"})
_SLUG = re.compile(r"[^a-z0-9]+")
_CSP = (
    "default-src 'self'; img-src 'self' data: https://cards.scryfall.io; style-src 'self'; "
    "script-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


class CardEntry(BaseModel):
    card_id: str
    quantity: int = Field(default=1, ge=1, le=99)
    zone: str = Field(default="main", pattern="^(commander|main)$")


class ListBody(BaseModel):
    cards: list[CardEntry]
    owned_only: bool = True


class DeckEvidenceBody(ListBody):
    cards: list[CardEntry] = Field(max_length=300)
    cohort: str = Field(default="all", min_length=1, max_length=120)


class BuildListBody(ListBody):
    cards: list[CardEntry] = Field(max_length=300)
    deck_id: str | None = Field(default=None, max_length=200)


class LandAdvisorBody(ListBody):
    cohort: str = Field(default="all", min_length=1, max_length=120)
    min_share: float = Field(default=0.20, ge=0.0, le=1.0)


class PlanPackagesBody(BaseModel):
    commander: str | list[str] | None = None
    cards: list[CardEntry]
    cohort: str = Field(default="all", min_length=1, max_length=120)


class DeckDoctorBody(PlanPackagesBody):
    limit: int = Field(default=5, ge=1, le=20)


class SwapBody(BaseModel):
    commander: str | list[str]
    deck_card_ids: list[str] = Field(default_factory=list, max_length=300)
    card_id: str = Field(min_length=1, max_length=200)
    mode: Literal["replace", "cut"] = "replace"
    cohort: str = Field(default="all", min_length=1, max_length=120)
    universe: str | None = Field(default=None, max_length=120)
    exclude_marked: bool = True
    sort_by: Literal["hits", "lift"] = "hits"
    deck_id: str | None = Field(default=None, max_length=200)
    branch: str = Field(default="main", min_length=1, max_length=120)


class DuelBody(BaseModel):
    commander: str | list[str]
    deck_card_ids: list[str] = Field(default_factory=list, max_length=300)
    card_a: str = Field(min_length=1, max_length=200)
    card_b: str = Field(min_length=1, max_length=200)
    cohort: str = Field(default="all", min_length=1, max_length=120)


class DecklistParseBody(BaseModel):
    commander: str | list[str]
    text: str = Field(max_length=100_000)


class SimilarDecksBody(BaseModel):
    commander: str | list[str]
    deck_card_ids: list[str] = Field(default_factory=list, max_length=300)
    revision: str | None = Field(default=None, max_length=120)
    deck_id: str | None = Field(default=None, max_length=120)
    branch: str = Field(default="main", min_length=1, max_length=80)
    cohort: str = Field(default="all", min_length=1, max_length=120)
    n: int = Field(default=20, ge=1, le=100)
    include_unowned: bool = False


class LabelsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    labels: list[str] = Field(max_length=100)


class DraftBody(BaseModel):
    cards: list[CardEntry]
    base_revision_id: str | None = None
    expected_updated_at: str | None = None
    expected_base_revision_id: str | None = None
    check_conflict: bool = False


class FavoriteBody(BaseModel):
    favorite: bool


class DraftCardBody(BaseModel):
    card_id: str = Field(min_length=1, max_length=200)
    delta: Literal[1, -1] = 1


class RevisionBody(BaseModel):
    cards: list[CardEntry]
    branch: str = Field(default="main", min_length=1, max_length=60)
    note: str = Field(default="", max_length=500)
    parent_revision_id: str | None = None


class DeckBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    commander_card_ids: list[str] = Field(min_length=1, max_length=2)


class ModuleSaveBody(BaseModel):
    module_id: str | None = Field(default=None, max_length=200)
    name: str = Field(min_length=1, max_length=80)
    role: Literal["core", "package"] = "package"
    sort_order: int = Field(default=0, ge=-1000, le=1000)
    cards: list[CardEntry] = Field(default_factory=list, max_length=300)


class ModuleSeedBody(BaseModel):
    cards: list[CardEntry] = Field(default_factory=list, max_length=300)
    core_card_ids: list[str] | None = None
    core_name: str = Field(default="Kern", min_length=1, max_length=80)
    package_name: str = Field(default="Paket A", min_length=1, max_length=80)


class ModuleCompileBody(BaseModel):
    module_ids: list[str] = Field(default_factory=list, max_length=50)
    owned_only: bool = True
    save: bool = False
    branch: str | None = Field(default=None, max_length=60)
    note: str = Field(default="", max_length=500)


class PrimerBody(BaseModel):
    content: str = Field(default="", max_length=MAX_PRIMER_CHARS)


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
    human_seats: list[int] | None = None
    decision_timeout_seconds: int = Field(default=0, ge=0, le=86_400)
    ai_delay_ms: int = Field(default=250, ge=0, le=5_000)


class PlayDecisionBody(BaseModel):
    decision_id: str = Field(min_length=1, max_length=200)
    selected_option_ids: list[str] = Field(default_factory=list, max_length=200)
    ordering: list[str] = Field(default_factory=list, max_length=200)
    numeric_choice: int | None = None
    numeric_choices: list[int] | None = None


class PlayConcedeBody(BaseModel):
    seat: int | None = Field(default=None, ge=0, le=5)


class PlaySpeedBody(BaseModel):
    ai_delay_ms: int = Field(ge=0, le=5_000)


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


class PairedSeriesBody(BaseModel):
    base_revision_id: str = Field(min_length=1, max_length=200)
    variant_revision_id: str = Field(min_length=1, max_length=200)
    pod: str = Field(default="precon", max_length=50)
    opponent_ids: list[str] | None = None
    budget_pairs: int = Field(
        default=20,
        ge=paired_comparison.MIN_BUDGET_PAIRS,
        le=paired_comparison.MAX_BUDGET_PAIRS,
    )
    look_every_pairs: int = Field(default=4, ge=1, le=100)
    base_seed: int = Field(default=1000, ge=0, le=2_000_000_000)
    rotate_seats: bool = True
    threshold_pp: float = Field(default=paired_comparison.DEFAULT_THRESHOLD_PP, ge=-50.0, le=50.0)
    significance_level: float = Field(
        default=paired_comparison.DEFAULT_SIGNIFICANCE_LEVEL, gt=0.0, lt=0.5
    )
    workers: int | None = Field(default=None, ge=MIN_WORKERS, le=MAX_WORKERS)
    games_per_jvm: int | None = Field(default=None, ge=MIN_GAMES_PER_JVM, le=MAX_GAMES_PER_JVM)


class ReadinessAuditBody(BaseModel):
    commander: str | list[str]
    cards: list[CardEntry] | None = None
    tiers: list[str] = Field(default_factory=lambda: ["S", "A"], max_length=5)


class NamesBody(BaseModel):
    names: list[str] = Field(max_length=2000)


class CutBody(BaseModel):
    cards: list[CardEntry]
    locked: list[str] = Field(default_factory=list, max_length=200)
    rejected: list[str] = Field(default_factory=list, max_length=400)
    deferred: list[str] = Field(default_factory=list, max_length=400)
    role_minimums: dict[str, int] = Field(default_factory=dict)
    cohort: str = Field(default="all", min_length=1, max_length=120)


class SampleHandBody(BaseModel):
    cards: list[CardEntry]
    seed: int = Field(default=1, ge=0, le=2_000_000_000)
    mulligans: int = Field(default=0, ge=0, le=7)
    draw_steps: int = Field(default=0, ge=0, le=10)
    bottom_indices: list[int] = Field(default_factory=list, max_length=7)


class CutWhatIfBody(BaseModel):
    cards: list[CardEntry]
    cut: str
    add: str
    cohort: str = Field(default="all", min_length=1, max_length=120)


class CutFinishBody(BaseModel):
    start: list[CardEntry]
    cards: list[CardEntry]


class DiffBody(BaseModel):
    base_revision_id: str
    cards: list[CardEntry]
    cohort: str = Field(default="all", min_length=1, max_length=120)


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
    verified_prohibited = sum(
        1
        for source in inventory["sources"]
        if source["status"] == "VERIFIED" and source["access_status"] == "prohibited"
    )
    return {
        "schema_version": inventory["schema_version"],
        "total_sources": inventory["total_sources"],
        "status_counts": inventory["status_counts"],
        "access_status_counts": inventory["access_status_counts"],
        # Data-quality VERIFIED sources whose automated retrieval is prohibited (stock only,
        # usable by Owner decision #1557): shown apart from the plainly verified ones.
        "verified_access_prohibited": verified_prohibited,
    }


def _cards(entries: list[CardEntry]) -> list[RevisionCard]:
    return [RevisionCard(entry.card_id, entry.quantity, entry.zone) for entry in entries]


_warmed = threading.Event()


def _warm_up_once() -> None:
    """Start the one-time card-data load in the background, once per process."""
    if _warmed.is_set():
        return
    _warmed.set()
    threading.Thread(target=builder.warm_up, name="studio-warm-up", daemon=True).start()


def data_report_cached(store: StudioStore) -> dict[str, object]:
    """The data report. Its figures come from the store and the date, so they are remembered per
    store state and UTC day (the report takes tens of seconds over a full corpus). The one part
    that is read from the repository, ``bridge_qualification``, is set fresh on every call, and
    the caller gets its own copy: changing it never changes what is remembered."""
    from commander_lab.bridge_qualification import bridge_qualification

    day = datetime.now(UTC).date()

    def compute() -> dict[str, object]:
        # The sweep over every commander of the store must not push warm entries out.
        with cache.read_only():
            return data_report.data_report(store, today=day)

    report = copy.deepcopy(cache.cached(store, ("data_report", day.isoformat()), compute))
    report["bridge_qualification"] = bridge_qualification()
    return report


def strength_answer(store: StudioStore, body: StrengthBody) -> dict[str, object]:
    """The strength index answer of ``/api/strength``, remembered per store state and request
    (the resolved settings are part of the key; errors are not kept). Also what the start-up
    warm-up of ``serve`` fills, under the same key."""
    settings = strength_view.resolve_settings(
        store, preset=body.preset, profile=body.profile, settings=body.settings
    )

    # The snapshot answer names the profile it belongs to: a preset and the same figures typed in
    # as plain settings are different requests and must not share one remembered answer.
    profile_name = (
        None
        if body.profile is not None
        else (
            body.preset
            if body.preset is not None
            else ("Ausgewogen" if settings == strength.StrengthSettings.recommended() else None)
        )
    )

    def compute() -> dict[str, object]:
        if body.profile is not None:
            return dict(
                strength_view.compute(
                    store,
                    body.commander,
                    settings,
                    # a saved profile may point to a universe deleted since: fall back
                    # visibly instead of failing; explicit settings must name a real one
                    dangling_universe_ok=True,
                    notices=strength_view.profile_notices(store, body.profile),
                    saved_weights=strength_view.profile_saved_weights(store, body.profile),
                )
            )
        return dict(
            strength_view.compute_with_snapshot(
                store, body.commander, settings, profile_name=profile_name
            )
        )

    key = (
        body.commander,
        body.profile,
        profile_name,
        json.dumps(asdict(settings), sort_keys=True, default=str),
    )
    answer = cache.cached(store, ("strength", *key), compute)
    # Additive: the second overall rating (Kartenverständnis) next to the usage index. Added
    # after the snapshot and the remembered answer, so neither of them changes; the data file's
    # stamp is part of the key.
    return cache.cached(
        store,
        ("strength_overall", *key, card_understanding.stamp()),
        lambda: overall_rating.with_overall(store, answer),
    )


def layer_overview_cached(store: StudioStore, commander: str) -> dict[str, object]:
    """``import_all.layer_overview``, remembered per store state and commander. Several pages ask
    at once and every answer counts the whole pool: one shared computation (the pool figures it
    needs are cached as well). Also what the start-up warm-up of ``serve`` fills."""
    return cache.cached(
        store,
        ("layer_overview", commander),
        lambda: import_all.layer_overview(store, commander),
    )


def _status_store_part(store: StudioStore) -> dict[str, object]:
    """The figures of ``/api/status`` that come from the store alone, remembered per store state
    (#1563). The caller gets its own deep copy: changing it never changes what is remembered."""

    def compute() -> dict[str, object]:
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
            "freshness": source_freshness(store.connection),
            "source_layers": source_layers(store.connection),
            # Only the newest dated rows travel with the page load (the full list was 1.7 MB);
            # the per-layer table in ``source_layers`` carries the counts of all of them.
            "sources": recent_dated_sources(store.connection, 25),
        }

    return copy.deepcopy(cache.cached(store, ("status_store_part",), compute))


def create_app(data_folder: str | Path | None = None) -> FastAPI:
    """The Studio application. ``data_folder`` is the Studio data folder (default: from the
    environment)."""
    play_manager = play.InteractivePlayManager()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        play_manager.shutdown_all()

    app = FastAPI(
        title="Commander Studio",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.play_manager = play_manager
    _warm_up_once()

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
        elif "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/status")
    def status() -> dict[str, object]:
        from commander_lab.bridge_qualification import bridge_qualification

        store = open_store()
        try:
            # The store part is remembered per store state (#1563); the bridge state and the
            # image folder are read fresh on every call, and the caller gets its own copy.
            part = _status_store_part(store)
            return {
                "bridge_qualification": bridge_qualification(),
                "cards": part["cards"],
                "public_cards": part["public_cards"],
                "source_decks": part["source_decks"],
                "neutral_board_rows": part["neutral_board_rows"],
                "simulation_runs": part["simulation_runs"],
                "source_data_binding": part["source_data_binding"],
                "decks": part["decks"],
                "universe_profiles": part["universe_profiles"],
                "source_inventory": part["source_inventory"],
                "freshness": part["freshness"],
                "source_layers": part["source_layers"],
                "image_cache": image_cache_status(store),
                "sources": part["sources"],
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
            return data_report_cached(store)
        finally:
            store.close()

    @app.get("/api/layers")
    def layers(commander: str = Query(min_length=1, max_length=200)) -> dict[str, object]:
        """Per data layer of one commander: rows, pool cards covered, status and the exact
        import call, for the empty-state box of the pages."""
        store = open_store()
        try:
            return layer_overview_cached(store, commander)
        finally:
            store.close()

    @app.get("/api/pool")
    def pool(
        commander: list[str] = Query(min_length=1, max_length=2),
        profile: str | None = Query(default=None, max_length=80),
        strength_universe: str | None = Query(default=None, max_length=120),
        strength_bracket: str | None = Query(default=None, max_length=20),
    ) -> Response:
        """The pool. ``strength_universe`` and ``strength_bracket`` are the universe source and
        bracket of the tier list's settings: the builder then shows the same counted universe
        the tier list takes (the recommended settings when they are not given). Remembered per
        store state and parameters (#1563)."""
        store = open_store()

        def compute() -> dict[str, object]:
            overrides: dict[str, object] = {}
            if strength_universe:
                overrides["universe_source"] = strength_universe
            if strength_bracket:
                overrides["bracket"] = strength_bracket
            settings = None
            if overrides:
                try:
                    settings = strength_view.resolve_settings(
                        store, preset=None, profile=None, settings=overrides
                    )
                except ValueError:
                    settings = None  # a stale remembered value must not block the builder
            return builder.pool_cards(store, commander, profile=profile, strength=settings)

        try:
            return answer_cache.json_answer(
                store,
                "pool",
                (tuple(commander), profile, strength_universe, strength_bracket),
                compute,
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except KeyError as error:
            if profile is not None and str(error).strip("'") == profile:
                raise HTTPException(404, f"unknown universe profile: {error}") from error
            raise HTTPException(404, f"commander not in the collection: {error}") from error
        finally:
            store.close()

    @app.get("/api/marks")
    def marks() -> dict[str, dict[str, object]]:
        """The Owner's marks per card id (favourite, excluded, note), without any pool,
        count or figure: the light read for pages that only need to know what is marked."""
        store = open_store()
        try:
            return builder.read_marks(store)
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
    ) -> Response:
        """Evidence per pool card for the tier list view. Marks are not part of it. Remembered
        per store state, parameters and the combo file (#1563)."""
        if view not in evidence_model.VIEWS:
            raise HTTPException(422, "view must be 'commander' or 'global'")
        if view == evidence_model.VIEW_COMMANDER and not commander:
            raise HTTPException(422, "the commander view needs a commander")
        store = open_store()
        try:
            return answer_cache.json_answer(
                store,
                "evidence",
                (view, tuple(commander)),
                lambda: evidence_model.pool_evidence(store, commander, view=view),
                files=evidence_model.ANSWER_FILES,
            )
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

    @app.get("/api/strength/snapshot")
    def strength_snapshot_summary(
        commander: str = Query(min_length=1, max_length=200),
    ) -> dict[str, object]:
        """Lightweight persisted tier snapshot summary (#1420, #1369) without card rows."""
        store = open_store()
        try:
            found = tier_snapshot.latest_snapshot_summary(store, commander)
            if found is None:
                raise HTTPException(404, "no tier snapshot for commander")
            return found
        finally:
            store.close()

    @app.post("/api/strength")
    def strength_index(body: StrengthBody) -> dict[str, object]:
        """Strength index per pool card of one commander: an estimate from usage signals,
        not a measured win rate. Marks are not part of it. Needs the X-Studio header
        like every non-GET route, although it changes nothing."""
        store = open_store()
        try:
            return strength_answer(store, body)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except KeyError as error:
            raise HTTPException(
                404, f"unknown commander, preset, profile or universe profile: {error}"
            ) from error
        finally:
            store.close()

    @app.get("/api/rating-layers")
    def rating_layers(
        commander: str = Query(min_length=1, max_length=200),
        pod_size: int = Query(
            default=strength.DEFAULT_POD_SIZE, ge=strength.POD_SIZE_MIN, le=strength.POD_SIZE_MAX
        ),
    ) -> Response:
        """The rating layers (Bewertungsebenen) of one commander's pool, without the strength
        index: for the card window of the builder. Derived or observed, never a tier.
        Remembered per store state and parameters (#1563)."""
        store = open_store()
        try:
            return answer_cache.json_answer(
                store,
                "rating_layers",
                (commander, pod_size),
                lambda: dict(strength_view.rating_layers(store, commander, pod_size)),
            )
        except KeyError as error:
            raise HTTPException(404, f"commander not in the collection: {error}") from error
        finally:
            store.close()

    @app.get("/api/roles/audit")
    def role_audit_route(
        commander: str | None = Query(default=None, min_length=1, max_length=200),
    ) -> Response:
        """Compare Scryfall tagger claims vs. deterministic Oracle text claims (#1413),
        optionally scoped to one commander's legal collection pool with n/N coverage.
        Remembered per store state and parameters (#1563)."""
        store = open_store()
        try:
            return answer_cache.json_answer(
                store,
                "role_audit",
                (commander,),
                lambda: roles.role_origin_audit(store, commander=commander),
            )
        except KeyError as error:
            raise HTTPException(404, f"commander not in the collection: {error}") from error
        finally:
            store.close()

    @app.get("/api/tournament-conversion")
    def tournament_conversion_route(
        commander: str = Query(min_length=1, max_length=200),
    ) -> Response:
        """TopDeck with-vs-without (mit/ohne) top-cut conversion rates per card (#1412).
        Reads only the TopDeck files: remembered per state of their folder (#1563)."""
        folder = tournament_conversion.research_dir()
        return answer_cache.file_answer(
            "tournament_conversion",
            (commander, str(folder)),
            answer_cache.folder_stamp(folder),
            lambda: dict(tournament_conversion.analyze_commander_conversion(commander, folder)),
        )

    @app.get("/api/strength/profiles")
    def strength_profiles() -> list[dict[str, object]]:
        store = open_store()
        try:
            return [dict(item) for item in strength_view.list_profiles(store)]
        finally:
            store.close()

    @app.get("/api/strength/profiles/{name:path}")
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

    @app.put("/api/strength/profiles/{name:path}")
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

    @app.delete("/api/strength/profiles/{name:path}")
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

    @app.get("/api/universe/counted")
    def universe_counted(
        commander: str = Query(min_length=1, max_length=200),
    ) -> Response:
        """The counted deck-list universes stored for this commander (source, bracket, decks,
        snapshot, label) with the stored rows whose name matches no card of the store
        (``unmatched_rows``, up to ten ``unmatched_examples``, a German ``notice``). Never
        another commander's. Remembered per store state and commander (#1563)."""
        store = open_store()

        def compute() -> list[dict[str, object]]:
            known = signals.known_card_names(store)
            listed: list[dict[str, object]] = []
            for item in universe_choice.counted_universes(store, commander):
                missing = signals.unmatched_universe_names(store, commander, item["signal"], known)
                examples = missing[: signals.UNMATCHED_EXAMPLES]
                listed.append(
                    {
                        **item,
                        "unmatched_rows": len(missing),
                        "unmatched_examples": examples,
                        "notice": signals.unmatched_notice(len(missing), examples),
                    }
                )
            return listed

        try:
            return answer_cache.json_answer(
                store, "universe_counted", (commander,), compute, shape="list"
            )
        finally:
            store.close()

    @app.get("/api/universe/profiles")
    def universe_profiles() -> list[dict[str, object]]:
        store = open_store()
        try:
            return universe.list_profiles(store)
        finally:
            store.close()

    @app.get("/api/universe/profiles/{name:path}/summary")
    def universe_profile_summary(
        name: str = PathParam(min_length=1, max_length=80),
        commander: str = Query(min_length=1, max_length=200),
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

    @app.put("/api/universe/profiles/{name:path}")
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
            cache.invalidate()
            return dict(universe_view.profile_summary(store, name, commander_names=[commander]))
        except ValueError as error:
            raise HTTPException(422, _german(error)) from error
        finally:
            store.close()

    @app.delete("/api/universe/profiles/{name:path}")
    def delete_universe_profile(
        name: str = PathParam(min_length=1, max_length=80),
    ) -> dict[str, object]:
        store = open_store()
        try:
            universe.delete_profile(store, name)
            cache.invalidate()
            return {"deleted": name}
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

    @app.get("/api/simulations/pod-matrix")
    def simulations_pod_matrix(
        commander: list[str] = Query(min_length=1, max_length=2),
    ) -> dict[str, object]:
        """Aggregated simulation matchup matrix by pod with exact n/N games and bridge qualification state (#1404)."""
        store = open_store()
        try:
            return builder.pod_matchup_matrix(store, commander)
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
        from .games import games_folder
        from .simulations import simulation_manager

        batch = simulation_manager.get_batch(batch_id)
        if batch is not None:
            return batch.to_dict()
        series_file = games_folder(games_home()) / f"{batch_id}.series.json"
        if series_file.is_file():
            try:
                payload = json.loads(series_file.read_text(encoding="utf-8"))
            except ValueError:
                raise HTTPException(422, "corrupt series record") from None
            if isinstance(payload, dict):
                return cast(dict[str, object], payload)
        raise HTTPException(404, "unknown batch")

    @app.post("/api/simulations/batch/{batch_id}/resume")
    def resume_simulation_batch(batch_id: str) -> dict[str, object]:
        store = open_store()
        try:
            from .simulations import simulation_manager

            batch = simulation_manager.resume_batch(
                store,
                games_home(),
                batch_id=batch_id,
            )
            return {
                "batch_id": batch.batch_id,
                "status": batch.status,
                "execution": batch.execution(),
            }
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

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

    @app.post("/api/simulations/paired")
    def start_paired_series(body: PairedSeriesBody) -> dict[str, object]:
        """Start a paired overnight A-vs-B comparison series (same seeds, seats, pod)."""
        store = open_store()
        try:
            job = paired_series.paired_series_manager.start_series(
                store,
                games_home(),
                base_revision_id=body.base_revision_id,
                variant_revision_id=body.variant_revision_id,
                pod=body.pod,
                opponent_ids=body.opponent_ids,
                budget_pairs=body.budget_pairs,
                look_every_pairs=body.look_every_pairs,
                base_seed=body.base_seed,
                rotate_seats=body.rotate_seats,
                threshold_pp=body.threshold_pp,
                significance_level=body.significance_level,
                workers=body.workers,
                games_per_jvm=body.games_per_jvm,
            )
            return job.to_dict()
        except KeyError as error:
            raise HTTPException(404, f"unknown deck revision: {error}") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error
        finally:
            store.close()

    @app.get("/api/simulations/paired-plan")
    def paired_series_plan(
        budget_pairs: int = Query(
            ge=paired_comparison.MIN_BUDGET_PAIRS, le=paired_comparison.MAX_BUDGET_PAIRS
        ),
        seats_per_seed: int = Query(default=4, ge=1, le=6),
    ) -> dict[str, object]:
        """Pre-run plan of a paired series: detectable difference and its assumptions."""
        return paired_series.planned_detectable_difference_pp(budget_pairs, seats_per_seed)

    @app.get("/api/simulations/paired")
    def list_paired_series() -> list[dict[str, object]]:
        """List recent paired A-vs-B comparison series."""
        return paired_series.paired_series_manager.list_series(games_home())

    @app.get("/api/simulations/paired/{series_id}")
    def get_paired_series(series_id: str) -> dict[str, object]:
        """Status and sequential statistics of one paired comparison series."""
        try:
            found = paired_series.paired_series_manager.get_series(games_home(), series_id)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        if found is None:
            raise HTTPException(404, "unknown paired series")
        return found

    @app.post("/api/simulations/paired/{series_id}/cancel")
    def cancel_paired_series(series_id: str) -> dict[str, object]:
        """Request cancellation of a running paired comparison series."""
        try:
            cancelled = paired_series.paired_series_manager.cancel_series(series_id)
            if not cancelled:
                raise HTTPException(404, "unknown paired series")
            found = paired_series.paired_series_manager.get_series(games_home(), series_id)
            return found if found is not None else {"cancelled": True}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/simulations/paired/{series_id}/resume")
    def resume_paired_series(series_id: str) -> dict[str, object]:
        """Resume an interrupted, cancelled, or failed paired comparison series."""
        try:
            job = paired_series.paired_series_manager.resume_series(games_home(), series_id)
            return job.to_dict()
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error

    @app.post("/api/simulations/readiness-audit")
    def readiness_audit_route(body: ReadinessAuditBody) -> dict[str, object]:
        """C-3 audit: check XMage card facts and pilot knowledge for deck + free Tier-S/A pool."""
        commanders = (
            [body.commander.strip()]
            if isinstance(body.commander, str)
            else [str(c).strip() for c in body.commander if str(c).strip()]
        )
        commanders = [c for c in commanders if c]
        if not commanders:
            raise HTTPException(422, "commander is required")
        store = open_store()
        try:
            return paired_series.simulator_readiness_audit(
                store,
                commanders,
                cards=_cards(body.cards) if body.cards is not None else None,
                tiers=body.tiers or ["S", "A"],
            )
        except KeyError as error:
            raise HTTPException(404, f"unknown commander or card: {error}") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    def _resolve_base_cards(store: StudioStore, base_revision_id: str) -> list[RevisionCard]:
        if base_revision_id.startswith("repo:"):
            return resolve_repo_baseline_cards(store, base_revision_id)
        base_rows = revision_rows(store, base_revision_id)
        return [
            RevisionCard(str(r["card_id"]), int(r["quantity"]), str(r["zone"])) for r in base_rows
        ]

    @app.get("/api/diff-baselines")
    def diff_baselines(
        commander: list[str] = Query(min_length=1, max_length=2),
    ) -> dict[str, object]:
        """Read-only repo baseline decks available as comparison targets (#1404 / B-4)."""
        return {"baselines": baseline_decks_for_commander(commander)}

    @app.post("/api/diff")
    def diff(body: DiffBody) -> dict[str, object]:
        store = open_store()
        try:
            base_cards = _resolve_base_cards(store, body.base_revision_id)
            return deck_diff.diff_impact(store, base_cards, _cards(body.cards), cohort=body.cohort)
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.post("/api/cut-lab")
    def cut_lab_route(body: CutBody) -> dict[str, object]:
        """Ordered cut suggestions from measured figures only, with the deck figure deltas of
        each cut (#1418). Locked, rejected cards, the commander and basics never appear."""
        store = open_store()
        try:
            return cut_lab.cut_suggestions(
                store,
                _cards(body.cards),
                locked=body.locked,
                rejected=body.rejected,
                deferred=body.deferred,
                role_minimums=body.role_minimums,
                cohort=body.cohort,
            )
        finally:
            store.close()

    @app.post("/api/cut-lab/what-if")
    def cut_lab_what_if_route(body: CutWhatIfBody) -> dict[str, object]:
        """What if card ``add`` went in instead of ``cut``: the counted deltas of that swap
        (``deck_diff.diff_impact``), nothing is changed (#1418)."""
        store = open_store()
        try:
            base = _cards(body.cards)
            commander_rows = [r for r in list_rows(store, base) if r["zone"] == "commander"]
            identity = frozenset().union(*(color_set(r["color_identity"]) for r in commander_rows))
            found = list_rows(store, [RevisionCard(body.add, 1, "main")])
            if not found:
                raise HTTPException(422, "die neue Karte ist unbekannt")
            add_row = found[0]
            if body.add in {card.card_id for card in base}:
                raise HTTPException(422, "die neue Karte steht schon im Deck")
            if (
                not add_row["commander_legal"]
                or not color_set(add_row["color_identity"]) <= identity
            ):
                raise HTTPException(
                    422, "die neue Karte ist nicht legal oder außerhalb der Farbidentität"
                )
            if not add_row["available_lower_bound"]:
                raise HTTPException(422, "von der neuen Karte ist kein Exemplar frei")
            target: list[RevisionCard] = []
            removed = False
            for card in base:
                if not removed and card.card_id == body.cut and card.zone == "main":
                    removed = True
                    if card.quantity > 1:
                        target.append(RevisionCard(card.card_id, card.quantity - 1, card.zone))
                    continue
                target.append(card)
            if not removed:
                raise HTTPException(422, "die zu kürzende Karte steht nicht im Deck")
            target.append(RevisionCard(body.add, 1, "main"))
            return deck_diff.diff_impact(store, base, target, cohort=body.cohort)
        finally:
            store.close()

    @app.post("/api/cut-lab/finish")
    def cut_lab_finish_route(body: CutFinishBody) -> dict[str, object]:
        """The final list and the ADD/CUT patch from the starting list (#1418)."""
        store = open_store()
        try:
            return cut_lab.finish(store, _cards(body.start), _cards(body.cards))
        finally:
            store.close()

    @app.post("/api/prefilter")
    def prefilter(body: PrefilterBody) -> dict[str, object]:
        store = open_store()
        try:
            base_cards = _resolve_base_cards(store, body.base_revision_id)
            return builder.prefilter_lists(
                store, base_cards, _cards(body.cards), trials=body.trials
            )
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.put("/api/cards/{card_id}/favorite")
    def favorite(card_id: str, body: FavoriteBody) -> dict[str, object]:
        """Only the favorite mark; the exclusion and the note of the card stay as stored."""
        store = open_store()
        try:
            return builder.set_favorite(store, card_id, body.favorite)
        except KeyError as error:
            raise HTTPException(404, "unknown card") from error
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

    @app.get("/api/labels")
    def known_labels() -> dict[str, object]:
        store = open_store()
        try:
            return {"known": labels.known_labels(store)}
        finally:
            store.close()

    @app.put("/api/cards/{card_id}/labels")
    def card_labels(card_id: str, body: LabelsBody) -> dict[str, object]:
        """The Owner's archetype labels of a card. Never an input of a tier or the index."""
        store = open_store()
        try:
            return {
                "card_id": card_id,
                "labels": labels.set_card_labels(store, card_id, body.labels),
            }
        except KeyError as error:
            raise HTTPException(404, "unknown card") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.put("/api/decks/{deck_id}/labels")
    def deck_labels(deck_id: str, body: LabelsBody) -> dict[str, object]:
        store = open_store()
        try:
            return {
                "deck_id": deck_id,
                "labels": labels.set_deck_labels(store, deck_id, body.labels),
            }
        except KeyError as error:
            raise HTTPException(404, "unknown deck") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.get("/api/allocation")
    def allocation_route() -> dict[str, object]:
        """Per card: copies bound by saved decks, overbooking and storage locations (#1419).
        Display only; nothing is locked."""
        store = open_store()
        try:
            return allocation.allocation(store)
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

    @app.get("/api/decks/{deck_id}/series")
    def deck_paired_series(deck_id: str) -> dict[str, object]:
        """Stored paired series in which a revision of this deck was base (A) or variant (B).
        Read-only; counts and the stored intervals, no verdict, never part of the tier list."""
        store = open_store()
        try:
            revision_ids = deck_series.deck_revision_ids(store, deck_id)
        finally:
            store.close()
        if revision_ids is None:
            raise HTTPException(404, "unknown deck")
        return deck_series.deck_series(games_home(), revision_ids)

    @app.get("/api/decks/{deck_id}/history")
    def deck_history(deck_id: str) -> list[dict[str, object]]:
        store = open_store()
        try:
            return builder.history(store, deck_id)
        finally:
            store.close()

    @app.post("/api/decks/{deck_id}/branches/{branch:path}/draft/card")
    def change_draft_card(
        deck_id: str,
        body: DraftCardBody,
        branch: str = PathParam(min_length=1, max_length=60),
    ) -> dict[str, object]:
        """One copy of a card into the working list of a variant, or out of it (the tier
        list's "ins Deck"). Writes a draft, never a saved state."""
        store = open_store()
        try:
            return builder.change_draft_card(store, deck_id, branch, body.card_id, body.delta)
        except KeyError as error:
            raise HTTPException(404, "unknown deck, variant or card") from error
        except builder.DraftChangeRefused as error:
            raise HTTPException(409, str(error)) from error
        finally:
            store.close()

    @app.get("/api/decks/{deck_id}/branches/{branch:path}/draft")
    def get_draft(
        deck_id: str, branch: str = PathParam(min_length=1, max_length=60)
    ) -> dict[str, object]:
        store = open_store()
        try:
            return {"draft": builder.read_draft(store, deck_id, branch)}
        finally:
            store.close()

    @app.put("/api/decks/{deck_id}/branches/{branch:path}/draft")
    def put_draft(
        deck_id: str,
        body: DraftBody,
        branch: str = PathParam(min_length=1, max_length=60),
    ) -> dict[str, object]:
        store = open_store()
        try:
            if not store.connection.execute(
                "SELECT 1 FROM deck WHERE deck_id = ?", (deck_id,)
            ).fetchone():
                raise HTTPException(404, "unknown deck")
            updated_at = builder.write_draft(
                store,
                deck_id,
                branch,
                _cards(body.cards),
                body.base_revision_id,
                expected_updated_at=body.expected_updated_at,
                expected_base_revision_id=body.expected_base_revision_id,
                check_conflict=body.check_conflict,
            )
            return {"saved": True, "updated_at": updated_at}
        except builder.DraftConflict as error:
            raise HTTPException(409, str(error)) from error
        finally:
            store.close()

    @app.delete("/api/decks/{deck_id}/branches/{branch:path}/draft")
    def delete_draft(
        deck_id: str, branch: str = PathParam(min_length=1, max_length=60)
    ) -> dict[str, object]:
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

    @app.get("/api/decks/{deck_id}/modules")
    def get_deck_modules(deck_id: str) -> dict[str, object]:
        store = open_store()
        try:
            return {
                "schema": deck_modules.DECK_MODULES_SCHEMA,
                "deck_id": deck_id,
                "modules": deck_modules.list_modules(store, deck_id),
            }
        except KeyError as error:
            raise HTTPException(404, "unknown deck") from error
        finally:
            store.close()

    @app.post("/api/decks/{deck_id}/modules")
    def save_deck_module(deck_id: str, body: ModuleSaveBody) -> dict[str, object]:
        store = open_store()
        try:
            saved = deck_modules.save_module(
                store,
                deck_id=deck_id,
                name=body.name,
                role=body.role,
                cards=_cards(body.cards),
                module_id=body.module_id,
                sort_order=body.sort_order,
            )
            return {"module": saved}
        except KeyError as error:
            raise HTTPException(404, "unknown deck or module") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.delete("/api/decks/{deck_id}/modules/{module_id}")
    def remove_deck_module(deck_id: str, module_id: str) -> dict[str, object]:
        store = open_store()
        try:
            deck_modules.delete_module(store, deck_id, module_id)
            return {"deleted": True, "module_id": module_id}
        except KeyError as error:
            raise HTTPException(404, "unknown deck or module") from error
        finally:
            store.close()

    @app.post("/api/decks/{deck_id}/modules/seed")
    def seed_deck_modules(deck_id: str, body: ModuleSeedBody) -> dict[str, object]:
        store = open_store()
        try:
            created = deck_modules.seed_modules_from_cards(
                store,
                deck_id=deck_id,
                cards=_cards(body.cards),
                core_card_ids=body.core_card_ids,
                core_name=body.core_name,
                package_name=body.package_name,
            )
            return {"modules": created}
        except KeyError as error:
            raise HTTPException(404, "unknown deck") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.post("/api/decks/{deck_id}/modules/compile")
    def compile_deck_modules(deck_id: str, body: ModuleCompileBody) -> dict[str, object]:
        store = open_store()
        try:
            return deck_modules.compile_modules(
                store,
                deck_id,
                body.module_ids,
                owned_only=body.owned_only,
                save=body.save,
                branch=body.branch,
                note=body.note,
            )
        except KeyError as error:
            raise HTTPException(404, "unknown deck or module") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.get("/api/decks/{deck_id}/primer")
    def read_primer(deck_id: str) -> dict[str, object]:
        store = open_store()
        try:
            return get_deck_primer(store, deck_id)
        except KeyError as error:
            raise HTTPException(404, "unknown deck") from error
        finally:
            store.close()

    @app.put("/api/decks/{deck_id}/primer")
    def write_primer(deck_id: str, body: PrimerBody) -> dict[str, object]:
        store = open_store()
        try:
            return set_deck_primer(store, deck_id, body.content)
        except KeyError as error:
            raise HTTPException(404, "unknown deck") from error
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
                "combos": combos.deck_combos(store, rows),
            }
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.get("/api/revisions/{revision_id}/export")
    def export(revision_id: str, format: str = "txt", include_primer: bool = False) -> Response:
        if format not in {"txt", "json", *EXPORT_TEXT_FORMATS}:
            raise HTTPException(422, "unknown export format")
        store = open_store()
        try:
            if format == "json":
                return JSONResponse(lab_snapshot(store, revision_id))
            rows = revision_rows(store, revision_id)
            primer_text = ""
            if include_primer:
                rev_row = store.connection.execute(
                    "SELECT deck_id FROM deck_revision WHERE revision_id = ?",
                    (revision_id,),
                ).fetchone()
                if rev_row is not None:
                    primer_text = str(get_deck_primer(store, str(rev_row["deck_id"]))["content"])
            if format in EXPORT_TEXT_FORMATS:
                return PlainTextResponse(export_text(rows, format, primer=primer_text))
            header = format_primer_comments(primer_text)
            lines = [*header, *(f"{row['quantity']} {row['engine_name']}" for row in rows)]
            return PlainTextResponse("\n".join(lines) + "\n")
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.get("/api/revisions/{revision_id}/dossier")
    def export_dossier(
        revision_id: str,
        base_revision_id: str | None = Query(default=None, max_length=200),
    ) -> Response:
        """Printable Markdown deck dossier with shape, role counts, card list, and revision changelog (#1404)."""
        store = open_store()
        try:
            md = export_deck_dossier(store, revision_id, base_revision_id=base_revision_id)
            return PlainTextResponse(md, media_type="text/markdown;charset=utf-8")
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
                "combos": combos.deck_combos(store, rows),
            }
        finally:
            store.close()

    @app.post("/api/deck-facts")
    def deck_facts_route(body: ListBody) -> dict[str, object]:
        """Bracket check and data gaps of a deck list: counts with names and origin, no
        verdict (#1404 options 1 and 10)."""
        store = open_store()
        try:
            return deck_facts.deck_facts(store, list_rows(store, _cards(body.cards)))
        finally:
            store.close()

    @app.post("/api/tokens")
    def tokens_route(body: ListBody) -> dict[str, object]:
        """Local Scryfall-derived token overview for a deck list (#1450): created tokens with
        creating cards, explicit denominators, and UNKNOWN list for unresolved creators."""
        store = open_store()
        try:
            return tokens.deck_tokens(store, _cards(body.cards))
        finally:
            store.close()

    @app.get("/api/revisions/{revision_id}/tokens")
    def revision_tokens_route(revision_id: str) -> dict[str, object]:
        """Local Scryfall-derived token overview for a stored deck revision (#1450)."""
        store = open_store()
        try:
            return tokens.revision_tokens(store, revision_id)
        except KeyError as error:
            raise HTTPException(404, "unknown revision") from error
        finally:
            store.close()

    @app.post("/api/build-list")
    def build_list_route(body: BuildListBody) -> dict[str, object]:
        """The deck's cards grouped by storage location, with the copies no known location
        covers as "Standort unbekannt" (#1404). Facts only; marks are not read."""
        store = open_store()
        try:
            cards = _cards(body.cards)
            rows = list_rows(store, cards)
            known = {str(row["card_id"]) for row in rows}
            missing = sorted({card.card_id for card in cards} - known)
            if missing:
                raise HTTPException(404, f"unknown card: {missing[0]}")
            return build_list.build_list(
                store,
                rows,
                expected_total=sum(card.quantity for card in cards),
                deck_id=body.deck_id,
            )
        except build_list.BuildListError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.post("/api/deck-evidence")
    def deck_evidence_route(body: DeckEvidenceBody) -> dict[str, object]:
        """Evidence per deck card (#1404): counted values per source with n/N and the group
        named, unknown never 0, no sum, no score. Marks are not read."""
        store = open_store()
        try:
            cards = _cards(body.cards)
            rows = list_rows(store, cards)
            known = {str(row["card_id"]) for row in rows}
            missing = sorted({card.card_id for card in cards} - known)
            if missing:
                raise HTTPException(404, f"unknown card: {missing[0]}")
            return deck_evidence.deck_evidence(store, rows, cohort=body.cohort)
        except deck_evidence.DeckEvidenceError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.post("/api/castability")
    def castability_route(body: ListBody) -> dict[str, object]:
        """Colour castability conditioned on land drops (Karsten) and the opening hand
        figure of a deck list (#1415, #1404 option 2), plus the starting-hand chance per role
        (``hand_roles``). A description, no land count advice."""
        store = open_store()
        try:
            rows = [dict(row) for row in list_rows(store, _cards(body.cards))]
            ids = [str(row["card_id"]) for row in rows]
            role_map: dict[str, list[str]] = {}
            for start in range(0, len(ids), 500):
                chunk = ids[start : start + 500]
                marks = ",".join("?" * len(chunk))
                for found in store.connection.execute(
                    "SELECT c.card_id, r.role FROM card_fact c JOIN card_role r "
                    f"USING (oracle_id) WHERE c.card_id IN ({marks}) ORDER BY r.role",
                    chunk,
                ):
                    role_map.setdefault(str(found["card_id"]), []).append(str(found["role"]))
            return {
                **castability.deck_castability(rows),
                "hand_roles": castability.hand_roles(rows, role_map),
            }
        finally:
            store.close()

    @app.post("/api/sample-hand")
    def sample_hand_route(body: SampleHandBody) -> dict[str, object]:
        """Deterministic seeded 7-card sample opening hand and London Mulligan simulator (#1404)."""
        store = open_store()
        try:
            rows = [dict(row) for row in list_rows(store, _cards(body.cards))]
            return castability.draw_sample_hand(
                rows,
                seed=body.seed,
                mulligans=body.mulligans,
                draw_steps=body.draw_steps,
                bottom_indices=body.bottom_indices,
            )
        finally:
            store.close()

    @app.post("/api/land-advisor")
    def land_advisor_route(body: LandAdvisorBody) -> dict[str, object]:
        """Land count and coloured sources against the coloured symbols, with the figures of
        the commander's source-deck groups and free pool land candidates. An observation, no
        recommendation."""
        store = open_store()
        try:
            cards = _cards(body.cards)
            rows = list_rows(store, cards)
            commanders = [str(row["oracle_name"]) for row in rows if row["zone"] == "commander"]
            return {
                "deck": land_advisor.deck_profile(rows),
                "groups": land_advisor.source_deck_groups(store, commanders),
                "small_group": land_advisor.SMALL_GROUP,
                "land_candidates": land_advisor.land_candidates(
                    store,
                    commanders,
                    cards,
                    cohort=body.cohort,
                    min_share=body.min_share,
                ),
                "land_cycles": land_advisor.land_cycles_summary(store, rows),
            }
        finally:
            store.close()

    @app.post("/api/swap")
    def swap_route(body: SwapBody) -> dict[str, object]:
        """Role-matched swap candidates (`mode="replace"` or `mode="cut"`) in the builder."""
        store = open_store()
        try:
            return swap.swap_candidates(
                store,
                commander=body.commander,
                deck_card_ids=body.deck_card_ids,
                card_id=body.card_id,
                mode=body.mode,
                cohort=body.cohort,
                universe=body.universe,
                exclude_marked=body.exclude_marked,
                sort_by=body.sort_by,
                deck_id=body.deck_id,
                branch=body.branch,
            )
        except KeyError as error:
            raise HTTPException(404, f"unknown card or commander: {error}") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.post("/api/packages")
    def packages_route(body: PlanPackagesBody) -> dict[str, object]:
        """Synergistic corpus lift packages and Spellbook shell packages touched by the deck (#1404 op. 7)."""
        store = open_store()
        try:
            commanders = packages._parse_commander_arg(body.commander)
            return packages.deck_packages(store, commanders, _cards(body.cards), cohort=body.cohort)
        except KeyError as error:
            raise HTTPException(404, f"unknown card or commander: {error}") from error
        finally:
            store.close()

    @app.post("/api/build-plan")
    def build_plan_route(body: PlanPackagesBody) -> dict[str, object]:
        """Guided 6-step deck-building plan against cohort reference spans + role coverage (#1404 op. 5, #1413)."""
        store = open_store()
        try:
            commanders = packages._parse_commander_arg(body.commander)
            return packages.build_plan(store, commanders, _cards(body.cards), cohort=body.cohort)
        except KeyError as error:
            raise HTTPException(404, f"unknown card or commander: {error}") from error
        finally:
            store.close()

    @app.post("/api/upgrade-path")
    def upgrade_path_route(body: PlanPackagesBody) -> dict[str, object]:
        """Descriptive role-matched upgrade path against source-deck inclusion shares (B-2)."""
        store = open_store()
        try:
            commanders = packages._parse_commander_arg(body.commander)
            return packages.upgrade_path(store, commanders, _cards(body.cards), cohort=body.cohort)
        except KeyError as error:
            raise HTTPException(404, f"unknown card or commander: {error}") from error
        finally:
            store.close()

    @app.post("/api/deck-doctor")
    def deck_doctor_route(body: DeckDoctorBody) -> dict[str, object]:
        """Descriptive p25/p75 cohort deviation check with free pool remedies (#1404)."""
        store = open_store()
        try:
            commanders = packages._parse_commander_arg(body.commander)
            return packages.deck_doctor_remedies(
                store,
                commanders,
                _cards(body.cards),
                cohort=body.cohort,
                limit=body.limit,
            )
        except KeyError as error:
            raise HTTPException(404, f"unknown card or commander: {error}") from error
        finally:
            store.close()

    @app.post("/api/card-duel")
    def card_duel_route(body: DuelBody) -> dict[str, object]:
        """Two cards side by side: roles, mana value, frequency n/N and observed fit with the
        rest of the deck against the group's baseline (#1404 option 3). Never "better"."""
        store = open_store()
        try:
            commanders = (
                [body.commander] if isinstance(body.commander, str) else list(body.commander)
            )
            return card_duel.card_duel(
                store,
                commanders,
                deck_card_ids=body.deck_card_ids,
                card_a=body.card_a,
                card_b=body.card_b,
                cohort=body.cohort,
            )
        except KeyError as error:
            raise HTTPException(404, f"unknown card: {error}") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.post("/api/decklist-parse")
    def decklist_parse_route(body: DecklistParseBody) -> dict[str, object]:
        """Parse plain decklist text against the commander's legal collection pool."""
        store = open_store()
        try:
            commanders = (
                [body.commander] if isinstance(body.commander, str) else list(body.commander)
            )
            return parse_decklist_text(store, commanders, body.text)
        except KeyError as error:
            raise HTTPException(404, f"unknown commander: {error}") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.get("/api/similar-decks")
    def similar_decks_get(
        commander: list[str] = Query(min_length=1, max_length=2),
        revision: str | None = Query(default=None, max_length=120),
        deck_id: str | None = Query(default=None, max_length=120),
        branch: str = Query(default="main", min_length=1, max_length=80),
        card_id: list[str] = Query(default=[]),
        cohort: str = Query(default="all", min_length=1, max_length=120),
        n: int = Query(default=20, ge=1, le=100),
        include_unowned: bool = Query(default=False),
    ) -> dict[str, object]:
        """Nearest non-duplicate source decks by Jaccard similarity without basic lands."""
        store = open_store()
        try:
            resolved_ids = similar_decks.resolve_user_deck_cards(
                store,
                revision_id=revision,
                deck_id=deck_id,
                branch=branch,
                card_ids=card_id if card_id else None,
            )
            return similar_decks.find_similar_decks(
                store,
                commander,
                deck_card_ids=resolved_ids,
                cohort=cohort,
                n=n,
                include_unowned=include_unowned,
            )
        except KeyError as error:
            raise HTTPException(404, f"unknown commander: {error}") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.post("/api/similar-decks")
    def similar_decks_post(body: SimilarDecksBody) -> dict[str, object]:
        """Nearest non-duplicate source decks by Jaccard similarity for a live draft list."""
        store = open_store()
        try:
            commanders = (
                [body.commander] if isinstance(body.commander, str) else list(body.commander)
            )
            resolved_ids = similar_decks.resolve_user_deck_cards(
                store,
                revision_id=body.revision,
                deck_id=body.deck_id,
                branch=body.branch,
                card_ids=body.deck_card_ids if body.deck_card_ids else None,
            )
            return similar_decks.find_similar_decks(
                store,
                commanders,
                deck_card_ids=resolved_ids,
                cohort=body.cohort,
                n=body.n,
                include_unowned=body.include_unowned,
            )
        except KeyError as error:
            raise HTTPException(404, f"unknown commander: {error}") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            store.close()

    @app.get("/api/deck-browser")
    def deck_browser_route(
        commander: str = Query(default="", max_length=200),
        q: str = Query(default="", max_length=200),
        origin: str = Query(default="all", max_length=40),
        cohort: str = Query(default="all", max_length=120),
        label: str = Query(default="", max_length=120),
        must_contain: list[str] = Query(default=[]),
        must_not_contain: list[str] = Query(default=[]),
        include_unowned: bool = Query(default=False),
        limit_decks: int = Query(default=100, ge=1, le=500),
        limit_cards: int = Query(default=60, ge=1, le=300),
    ) -> Response:
        """Read-only Deck-Browser (#1323): filter saved and source decks + card co-occurrence.
        Remembered per store state and parameters (#1563)."""
        store = open_store()
        try:
            return answer_cache.json_answer(
                store,
                "deck_browser",
                (
                    commander,
                    q,
                    origin,
                    cohort,
                    label,
                    tuple(must_contain),
                    tuple(must_not_contain),
                    include_unowned,
                    limit_decks,
                    limit_cards,
                ),
                lambda: similar_decks.browse_decks(
                    store,
                    commander=commander,
                    q=q,
                    origin=origin,
                    cohort=cohort,
                    label=label,
                    must_contain=must_contain,
                    must_not_contain=must_not_contain,
                    include_unowned=include_unowned,
                    limit_decks=limit_decks,
                    limit_cards=limit_cards,
                ),
            )
        finally:
            store.close()

    @app.get("/api/deck-browser/{item_id:path}")
    def deck_browser_detail_route(item_id: str) -> dict[str, object]:
        """Read-only card list for a single saved or source deck in the Deck-Browser."""
        store = open_store()
        try:
            return similar_decks.get_browser_deck_detail(store, item_id)
        except KeyError as error:
            raise HTTPException(404, f"unknown deck: {error}") from error
        finally:
            store.close()

    @app.post("/api/engine-check")
    def engine_check_route(body: ListBody) -> dict[str, object]:
        """The runner's deck validation and the engine's card list for a list, no game."""
        store = open_store()
        try:
            rows = list_rows(store, _cards(body.cards))
            return engine_check.check_rows(rows, games_home())
        finally:
            store.close()

    @app.get("/img/by-name")
    @app.get("/img-name")
    def image_by_name(name: str = Query(min_length=1, max_length=200)) -> Response:
        store = open_store()
        try:
            url = web_image_url_by_name(store, name)
        finally:
            store.close()
        if url is None:
            raise HTTPException(404, "no image")
        return RedirectResponse(
            url=url,
            status_code=302,
            headers={"Referrer-Policy": "no-referrer", "Cache-Control": "max-age=604800"},
        )

    @app.get("/img/{card_id}")
    def image(card_id: str, face: str = "front") -> Response:
        if face not in {"front", "back"}:
            raise HTTPException(422, "face is front or back")
        store = open_store()
        try:
            url = web_image_url(store, card_id, face)
        finally:
            store.close()
        if url is None:
            raise HTTPException(404, "no image")
        return RedirectResponse(
            url=url,
            status_code=302,
            headers={"Referrer-Policy": "no-referrer", "Cache-Control": "max-age=604800"},
        )

    def games_home() -> Path:
        return Path(data_folder).resolve() if data_folder is not None else studio_data_dir()

    @app.get("/api/games")
    def game_list() -> list[dict[str, object]]:
        return games.list_games(games_home(), live_game_ids=play_manager.live_ids())

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

    @app.get("/api/outcomes/decks")
    def outcome_decks() -> dict[str, object]:
        """Every deck that sits in the game logs, at any seat, with its game counts.

        The outcomes of a game are data for every deck at the table, not only the
        Owner's: this lists each deck id the logs name — opponents and precons
        included — so ``/api/outcomes`` can be asked for any of them (#1267).
        A deck seated twice in one game counts once for that game.
        """
        report = card_outcomes.load_exposures(games.games_folder(games_home()))
        finished: dict[str, int] = {}
        for game in report["exposures"]:
            for deck_id in {seat["deck_id"] for seat in game["seats"]}:
                finished[deck_id] = finished.get(deck_id, 0) + 1
        return {
            "decks": [
                {
                    "deck_id": deck_id,
                    "games": finished.get(deck_id, 0),
                    "games_skipped": report["skipped_with_deck"].get(deck_id, 0),
                }
                for deck_id in card_outcomes.deck_ids_in(report)
            ]
        }

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
            if body.human_seats:
                total_seats = 1 + len(body.opponent_ids)
                for seat in body.human_seats:
                    if seat < 0 or seat >= total_seats:
                        raise ValueError(f"human seat {seat} out of range 0..{total_seats - 1}")
                game_id, deck_paths = launch.prepare_table_deck_paths(
                    store,
                    games_home(),
                    revision_id=body.revision_id,
                    opponent_ids=body.opponent_ids,
                    seed=body.seed,
                )
                seat_styles_map = (
                    {idx: float(val) for idx, val in enumerate(body.seat_styles, start=1)}
                    if body.seat_styles
                    else None
                )
                return play_manager.start_game(
                    games_home(),
                    deck_paths,
                    seed=body.seed,
                    human_seats=body.human_seats,
                    decision_timeout_seconds=body.decision_timeout_seconds,
                    ai_delay_ms=body.ai_delay_ms,
                    game_id=game_id,
                    style=body.style,
                    seat_styles=seat_styles_map,
                )
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
            return games.read_game(
                games_home(),
                game_id,
                start=start,
                count=count,
                live_game_ids=play_manager.live_ids(),
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(404, "unknown game") from error

    @app.get("/api/play/{game_id}")
    def interactive_game_state(
        game_id: str,
        start: int = Query(default=0, ge=0),
        count: int = Query(default=200, ge=0, le=1000),
    ) -> dict[str, object]:
        try:
            return play_manager.snapshot(games_home(), game_id, start=start, count=count)
        except (KeyError, ValueError) as error:
            raise HTTPException(404, "unknown game") from error

    @app.post("/api/play/{game_id}/decision")
    def submit_interactive_decision(game_id: str, body: PlayDecisionBody) -> dict[str, object]:
        session = play_manager.get(game_id)
        if session is None:
            raise HTTPException(404, "no active interactive game")
        try:
            return session.submit_decision(
                {
                    "decision_id": body.decision_id,
                    "selected_option_ids": body.selected_option_ids,
                    "ordering": body.ordering,
                    "numeric_choice": body.numeric_choice,
                    "numeric_choices": body.numeric_choices,
                }
            )
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except TimeoutError as error:
            raise HTTPException(504, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error

    @app.post("/api/play/{game_id}/concede")
    def concede_interactive_game(
        game_id: str, body: PlayConcedeBody | None = None
    ) -> dict[str, object]:
        session = play_manager.get(game_id)
        if session is None:
            raise HTTPException(404, "no active interactive game")
        try:
            return session.concede(None if body is None else body.seat)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except TimeoutError as error:
            raise HTTPException(504, str(error)) from error
        except RuntimeError as error:
            raise HTTPException(409, str(error)) from error

    @app.post("/api/play/{game_id}/speed")
    def set_interactive_speed(game_id: str, body: PlaySpeedBody) -> dict[str, object]:
        session = play_manager.get(game_id)
        if session is None:
            raise HTTPException(404, "no active interactive game")
        return {"ai_delay_ms": session.set_speed(body.ai_delay_ms)}

    @app.delete("/api/games/{game_id}")
    def delete_game(game_id: str) -> dict[str, object]:
        play_manager.shutdown_game(game_id, discard=True)
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

    @app.get("/favicon.ico")
    def favicon() -> Response:
        return Response(status_code=204)

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
