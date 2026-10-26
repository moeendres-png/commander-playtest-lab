"""FastAPI-App der Commander Lab UI (V1: Statistik-Ansicht + Deck-Liste).

Die Simulations-Warteschlange (Treiber-Aufruf, Fortschritt) ist der
naechste Schritt; diese Fassung liefert das lesende Geruest plus
Health-Check und eine schlichte Startseite.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from commander_lab.api.lab_ui import decks as decks_mod
from commander_lab.api.lab_ui import reports as reports_mod
from commander_lab.api.lab_ui import runs as runs_mod


class RunPayload(BaseModel):
    baseline: str = ""
    variant: str | None = None
    swaps: list[str] = []
    opponents: list[str] = []
    seeds: str = "1-25"
    no_rotate: bool = False
    workers: int | None = None
    stop_when_decided: bool = False
    look_every: int | None = None
    comparison_id: str | None = None
    retry_failed: bool = False


def create_app(repo_root: str | Path, results_root: str | Path) -> FastAPI:
    repo = Path(repo_root)
    results = Path(results_root)
    jobs = runs_mod.JobManager(repo, results)
    app = FastAPI(
        title="Commander Lab UI",
        description=(
            "Lokale Oberflaeche fuer das Commander-Playtest-Lab. "
            "Zeigt nur gemessene Reports, rechnet nichts neu."
        ),
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "repo_root": str(repo), "results_root": str(results)}

    @app.get("/api/decks")
    def api_decks() -> dict[str, object]:
        return decks_mod.list_decks(repo)

    @app.get("/api/reports")
    def api_reports() -> dict[str, object]:
        return {"reports": reports_mod.find_reports(results)}

    @app.get("/api/reports/{report_id:path}")
    def api_report(report_id: str) -> dict[str, object]:
        report_path = results / report_id / "COMPARISON_REPORT.json"
        if not report_path.is_file():
            raise HTTPException(status_code=404, detail="Report nicht gefunden")
        return reports_mod.summarize_report(report_path)

    @app.get("/reports/{report_id:path}", response_class=HTMLResponse)
    def html_report(report_id: str) -> str:
        report_path = results / report_id / "COMPARISON_REPORT.json"
        if not report_path.is_file():
            raise HTTPException(status_code=404, detail="Report nicht gefunden")
        return reports_mod.render_report_html(reports_mod.summarize_report(report_path))

    @app.post("/api/runs/plan-only")
    def api_plan_only(payload: RunPayload) -> dict[str, object]:
        try:
            plan = jobs.plan_only(_spec_from(payload))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"plan": plan}

    @app.post("/api/runs", status_code=201)
    def api_submit_run(payload: RunPayload) -> dict[str, object]:
        try:
            job = jobs.submit(_spec_from(payload))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return job.to_dict()

    @app.get("/api/runs")
    def api_list_runs() -> dict[str, object]:
        return {"runs": [job.to_dict() for job in jobs.list_jobs()]}

    @app.get("/api/runs/{job_id}")
    def api_get_run(job_id: str) -> dict[str, object]:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Run nicht gefunden")
        return job.to_dict()

    @app.post("/api/runs/{job_id}/cancel")
    def api_cancel_run(job_id: str) -> dict[str, object]:
        if not jobs.cancel(job_id):
            raise HTTPException(status_code=404, detail="Run nicht gefunden oder nicht laufend")
        return {"id": job_id, "status": "cancelled"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        found = reports_mod.find_reports(results)
        items = "".join(
            f'<li><a href="/api/reports/{r["id"]}">{r["id"]}</a>'
            f" ({r['completed']}/{r['total']} Spiele)</li>"
            for r in found
        )
        return (
            "<html><body><h1>Commander Lab UI (Prototyp)</h1>"
            "<h2>Simulation starten</h2>"
            '<form id="runform">'
            'Baseline: <input name="baseline" size="60" '
            'value="data/decks/rogshai_current.json"><br>'
            'Variante (optional): <input name="variant" size="60"><br>'
            'Swaps (optional, A=&gt;B;C=&gt;D): <input name="swaps" size="60"><br>'
            'Gegner 1: <input name="opp1" size="60" '
            'value="data/opponents/hosts_of_mordor_precon.json"><br>'
            'Gegner 2: <input name="opp2" size="60"><br>'
            'Gegner 3: <input name="opp3" size="60"><br>'
            'Seeds: <input name="seeds" value="1-25"> '
            'Workers: <input name="workers" type="number" value="1"> '
            '<label><input name="no_rotate" type="checkbox"> nur Sitz 1</label>'
            "<br><button>Starten</button></form>"
            '<pre id="out"></pre>'
            "<script>"
            "document.getElementById('runform').addEventListener('submit',"
            "async (e) => { e.preventDefault(); const f = e.target;"
            " const swaps = f.swaps.value ? f.swaps.value.split(';') : [];"
            " const opponents = [f.opp1.value, f.opp2.value, f.opp3.value]"
            "  .filter((v) => v);"
            " const body = { baseline: f.baseline.value,"
            "  variant: f.variant.value || null, swaps, opponents,"
            "  seeds: f.seeds.value, workers: parseInt(f.workers.value) || null,"
            "  no_rotate: f.no_rotate.checked };"
            " const r = await fetch('/api/runs', { method: 'POST',"
            "  headers: { 'Content-Type': 'application/json' },"
            "  body: JSON.stringify(body) });"
            " document.getElementById('out').textContent ="
            "  JSON.stringify(await r.json(), null, 2); });"
            "</script>"
            "<h2>Reports</h2><ul>" + (items or "<li>keine</li>") + "</ul>"
            '<p><a href="/api/decks">Deck-Liste (JSON)</a> | '
            '<a href="/api/runs">Runs (JSON)</a> | '
            '<a href="/docs">API-Doku</a></p></body></html>'
        )

    return app


def _spec_from(payload: RunPayload) -> runs_mod.RunSpec:
    return runs_mod.RunSpec(
        baseline=payload.baseline,
        opponents=payload.opponents,
        variant=payload.variant,
        swaps=payload.swaps,
        seeds=payload.seeds,
        no_rotate=payload.no_rotate,
        workers=payload.workers,
        stop_when_decided=payload.stop_when_decided,
        look_every=payload.look_every,
        comparison_id=payload.comparison_id,
        retry_failed=payload.retry_failed,
    )
