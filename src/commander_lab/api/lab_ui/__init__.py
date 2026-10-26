"""Commander Lab UI: lokale Weboberflaeche fuer das Playtest-Lab.

V1-Umfang (Hans, 2026-10-25): Simulationen einrichten/laufen lassen und
Statistiken aus COMPARISON_REPORT.json einsehen. Spielen (HumanPilot)
kommt danach und ist hier bewusst nicht enthalten.

Kein neues Framework, kein JS-Build: FastAPI wie der bestehende
Tool-Server, serverseitig gerendertes HTML, Ergebnisse als Dateien.
Sammlungsdaten werden nicht eingelesen (stehende Regel): Die
Deck-Liste nennt nur Pfade aus data/decks und data/opponents, nie
Karteninhalte aus Sammlungen.
"""

from commander_lab.api.lab_ui.app import create_app

__all__ = ["create_app"]
