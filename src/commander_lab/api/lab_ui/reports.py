"""Report-Ansicht fuer die Lab UI: liest COMPARISON_REPORT.json, rechnet
nichts neu. Die UI zeigt nur, was der Treiber gemessen hat.
"""

from __future__ import annotations

import json
from pathlib import Path


def find_reports(results_root: str | Path) -> list[dict[str, object]]:
    """Alle Vergleichs-Reports unter results_root (rekursiv)."""
    root = Path(results_root)
    found: list[dict[str, object]] = []
    if not root.exists():
        return found
    for report_path in sorted(root.rglob("COMPARISON_REPORT.json")):
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        batch = data.get("batch", {})
        found.append(
            {
                "id": str(report_path.parent.relative_to(root)),
                "comparison_id": data.get("comparison_id"),
                "contenders": len(data.get("contenders", [])),
                "completed": batch.get("completed_cases"),
                "failed": batch.get("failed_cases"),
                "total": batch.get("total_cases"),
                "evidence_class": data.get("evidence_class"),
            }
        )
    return found


def summarize_report(report_path: str | Path) -> dict[str, object]:
    """Kernaussagen eines Reports fuer die Ansicht (keine Neuberechnung)."""
    data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    contenders = [
        {
            "deck_id": c.get("deck_id"),
            "wins": c.get("wins"),
            "games_completed": c.get("games_completed"),
            "games_failed": c.get("games_failed"),
            "win_share": c.get("win_share"),
            "win_share_interval_95": c.get("win_share_interval_95"),
            "mean_turns": c.get("mean_turns"),
        }
        for c in data.get("contenders", [])
    ]
    paired = [
        {
            "baseline_deck_id": p.get("baseline_deck_id"),
            "variant_deck_id": p.get("variant_deck_id"),
            "verdict": p.get("verdict"),
            "win_share_difference": p.get("win_share_difference"),
            "win_share_difference_interval_95": p.get("win_share_difference_interval_95"),
            "sign_test_p_value": p.get("sign_test_p_value"),
            "pairs_completed": p.get("pairs_completed"),
            "pairs_censored": p.get("pairs_censored"),
        }
        for p in data.get("paired", [])
    ]
    return {
        "comparison_id": data.get("comparison_id"),
        "batch": data.get("batch"),
        "sequential": data.get("sequential"),
        "seeds": data.get("seeds"),
        "tested_seats": data.get("tested_seats"),
        "evidence_class": data.get("evidence_class"),
        "contenders": contenders,
        "paired": paired,
    }


def render_report_html(summary: dict[str, object]) -> str:
    """Schlichte HTML-Ansicht eines Report-Summary (kein JS, kein CSS)."""
    contenders = summary.get("contenders", [])
    paired = summary.get("paired", [])
    batch = summary.get("batch", {})
    rows = "".join(
        f"<tr><td>{c.get('deck_id')}</td><td>{c.get('wins')}</td>"
        f"<td>{c.get('games_completed')}</td>"
        f"<td>{c.get('win_share')}</td>"
        f"<td>{c.get('win_share_interval_95')}</td>"
        f"<td>{c.get('mean_turns')}</td></tr>"
        for c in contenders
    )
    pair_rows = "".join(
        f"<tr><td>{p.get('baseline_deck_id')}</td>"
        f"<td>{p.get('variant_deck_id')}</td><td>{p.get('verdict')}</td>"
        f"<td>{p.get('win_share_difference')}</td>"
        f"<td>{p.get('win_share_difference_interval_95')}</td>"
        f"<td>{p.get('sign_test_p_value')}</td>"
        f"<td>{p.get('pairs_completed')}</td>"
        f"<td>{p.get('pairs_censored')}</td></tr>"
        for p in paired
    )
    return (
        "<html><body>"
        f"<h1>Vergleich {summary.get('comparison_id')}</h1>"
        f"<p>Batch: {batch.get('completed_cases')}/{batch.get('total_cases')} "
        f"Spiele, {batch.get('failed_cases')} fehlgeschlagen. "
        f"Seeds: {summary.get('seeds')}. Sitze: {summary.get('tested_seats')}. "
        f"Evidenz: {summary.get('evidence_class')}.</p>"
        "<h2>Contender</h2><table border='1'>"
        "<tr><th>Deck</th><th>Siege</th><th>Spiele</th><th>Win-Anteil</th>"
        "<th>95%-Intervall</th><th>Ø Züge</th></tr>"
        + rows
        + "</table><h2>Gepaarter Vergleich</h2><table border='1'>"
        "<tr><th>Baseline</th><th>Variante</th><th>Urteil</th><th>Differenz</th>"
        "<th>95%-Intervall</th><th>p-Wert</th><th>Paare</th>"
        "<th>Zensiert</th></tr>" + pair_rows + "</table></body></html>"
    )
