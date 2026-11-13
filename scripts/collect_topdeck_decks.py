"""Collect TopDeck.gg tournament decklists and commander presence (#1205).

Fetches EDH tournament data from TopDeck.gg API v2 for a 90-day window:
- Adheres to TopDeck rate limits (max 5 requests/min, default 13s delay).
- Caches raw tournament slices in .cache/topdeck_tournaments/.
- Counts tournament presence across 107 collection commanders.
- Extracts complete 100-card tournament decklists (1 commander + 99 mainboard).
- Exports presence CSV, per-commander deck CSVs, and documentation.

Attribution:
    Data provided by TopDeck.gg (https://topdeck.gg).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Add src to sys.path if run directly
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

logger = logging.getLogger("collect_topdeck")

TOPDECK_API_URL = "https://topdeck.gg/api/v2/tournaments"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Canonical 107 collection commanders in CPL
DEFAULT_107_COMMANDERS = [
    "Kykar, Wind's Fury",
    "Anowon, the Ruin Sage",
    "Zetalpa, Primal Dawn",
    "Sram, Senior Edificer",
    "Lavinia, Azorius Renegade",
    "Arcanis the Omnipotent",
    "Uurg, Spawn of Turg",
    "Lonis, Cryptozoologist",
    "Alandra, Sky Dreamer",
    "Korvold, Fae-Cursed King",
    "Esix, Fractal Bloom",
    "The Gitrog Monster",
    "Brudiclad, Telchor Engineer",
    "Jeska, Thrice Reborn",
    "Halana and Alena, Partners",
    "Loran of the Third Path",
    "Tor Wauki the Younger",
    "Selvala, Explorer Returned",
    "Adrix and Nev, Twincasters",
    "Rionya, Fire Dancer",
    "Jedit Ojanen of Efrava",
    "Fynn, the Fangbearer",
    "Kaervek the Merciless",
    "Titania, Protector of Argoth",
    "Kamahl, Pit Fighter",
    "Veyran, Voice of Duality",
    "Kediss, Emberclaw Familiar",
    "Linden, the Steadfast Queen",
    "Esior, Wardwing Familiar",
    "Lathliss, Dragon Queen",
    "Mazirek, Kraul Death Priest",
    "Braids, Arisen Nightmare",
    "Ayli, Eternal Pilgrim",
    "Agrus Kos, Wojek Veteran",
    "Chulane, Teller of Tales",
    "Bennie Bracks, Zoologist",
    "Yargle, Glutton of Urborg",
    "Omnath, Locus of Rage",
    "God-Eternal Bontu",
    "Jolrael, Mwonvuli Recluse",
    "Galazeth Prismari",
    "Surrak, the Hunt Caller",
    "Ovika, Enigma Goliath",
    "Plargg and Nassari",
    "Ruby, Daring Tracker",
    "Morska, Undersea Sleuth",
    "Sophia, Dogged Detective",
    "Durnan of the Yawning Portal",
    "Tromell, Seymour's Butler",
    "Szarel, Genesis Shepherd",
    "Doc Ock, Sinister Scientist",
    "Spider-Man Noir",
    "Spider-Man, Web-Slinger",
    "Stegron the Dinosaur Man",
    "Venom, Evil Unleashed",
    "Carnage, Crimson Chaos",
    "Prowler, Clawed Thief",
    "Rhino, Barreling Brute",
    "Vulture, Scheming Scavenger",
    "Lizard, Connors's Curse",
    "Mary Jane Watson",
    "Molten Man, Inferno Incarnate",
    "Sun-Spider, Nimble Webber",
    "Swarm, Being of Bees",
    "Bre of Clan Stoutarm",
    "Brigid, Clachan's Heart // Brigid, Doun's Mind",
    "Doran, Besieged by Time",
    "Kirol, Attentive First-Year",
    "Lluwen, Imperfect Naturalist",
    "Maralen, Fae Ascendant",
    "Rhys, the Evermore",
    "Tam, Mindful First-Year",
    "Rootha, Mastering the Moment",
    "Tam, Observant Sequencer // Deep Sight",
    "Sanar, Unfinished Genius // Wild Idea",
    "Muddle, the Ever-Changing",
    "Mica, Reader of Ruins",
    "Soul of Windgrace",
    "Prime Speaker Zegana",
    "Titanbones, Towering Heart",
    "Tinybones, Pocket Nuisance",
    "Juri, Master of the Revue",
    "Winter, Team Player",
    "Winter, Tormented Loner",
    "Yargle, Goliath of Otaria",
    "Gideon the Oathless",
    "Hapatra, the Desert Fang",
    "Hapatra, the Desert Frost",
    "Teyo, Lightshield Expert",
    "Teyo, Diamondblade Mage",
    "Loot, the Nexus",
    "Tam, the Possibility",
    "Saheeli, Jewel of Avishkar",
    "Saheeli, Consul of Oversight",
    "Rootha, Mercurial Artist",
    "Ramos, Dragon Engine",
    "Garna, Bloodfist of Keld",
    "Tatyova, Benthic Druid",
    "Ishai, Ojutai Dragonspeaker",
    "Multani, Yavimaya's Avatar",
    "Gilanra, Caller of Wirewood",
    "Rograkh, Son of Rohgahh",
    "Lyra Dawnbringer",
    "Myojin of Night's Reach",
    "Syr Alin, the Lion's Claw",
    "Moraug, Fury of Akoum",
    "Koma, Cosmos Serpent",
]


def to_safe_slug(name: str) -> str:
    """Convert commander name to safe file-system slug."""
    s = name.lower()
    # Handle split names
    s = s.replace("//", " ")
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "_", s).strip("_")
    return s


def player_initials(name: str) -> str:
    """Reduce a player name to its initials (Owner decision #1108).

    For each space-separated token, take its first alphabetic character,
    uppercased; tokens without any letter contribute nothing.
    Example: "Void of Emperor [INTIM]" becomes "V O E I".
    """
    initials: list[str] = []
    for token in name.split():
        for char in token:
            if char.isalpha():
                initials.append(char.upper())
                break
    return " ".join(initials)


def anonymize_player_labels(names: Iterable[str]) -> dict[str, str]:
    """Map distinct player names to initials labels in first-appearance order.

    If several distinct names reduce to the same initials, the second one
    (in first-appearance order) gets the suffix " 2", the third " 3", and
    so on, so labels stay unique within one export file and deck grouping
    and counts are preserved exactly.
    """
    labels: dict[str, str] = {}
    counts: dict[str, int] = {}
    for name in names:
        if name in labels:
            continue
        base = player_initials(name)
        counts[base] = counts.get(base, 0) + 1
        labels[name] = base if counts[base] == 1 else f"{base} {counts[base]}"
    return labels


def get_api_key() -> str:
    """Retrieve API key from TOPDECK_API_KEY environment variable."""
    key = os.environ.get("TOPDECK_API_KEY", "").strip()
    if key:
        return key
    raise RuntimeError("TopDeck API key not found. Set TOPDECK_API_KEY environment variable.")


def extract_cards_from_section(section_data: object) -> list[tuple[str, int]]:
    """Extract list of (card_name, quantity) tuples from section object."""
    cards: list[tuple[str, int]] = []
    if isinstance(section_data, dict):
        for card_name, info in section_data.items():
            qty = 1
            if isinstance(info, dict):
                qty = int(info.get("count", 1) or 1)
            elif isinstance(info, (int, float)):
                qty = int(info)
            cards.append((str(card_name).strip(), qty))
    elif isinstance(section_data, list):
        for item in section_data:
            if isinstance(item, dict):
                name = item.get("name") or item.get("card_name")
                qty = int(item.get("count", item.get("quantity", 1)) or 1)
                if name:
                    cards.append((str(name).strip(), qty))
            elif isinstance(item, str):
                cards.append((item.strip(), 1))
    return cards


def parse_decklist_text(text: str) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Parse text decklist fallback with ~~Commanders~~ and ~~Mainboard~~ sections."""
    commanders: list[tuple[str, int]] = []
    mainboard: list[tuple[str, int]] = []
    current_section = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("~~commanders~~") or lower.startswith("// commander"):
            current_section = "commander"
            continue
        if lower.startswith("~~mainboard~~") or lower.startswith("// mainboard"):
            current_section = "mainboard"
            continue
        m = re.match(r"^(\d+)\s+(.+)$", line)
        if m:
            qty = int(m.group(1))
            cname = m.group(2).strip()
            if current_section == "commander":
                commanders.append((cname, qty))
            else:
                mainboard.append((cname, qty))
    return commanders, mainboard


@dataclass
class DecklistRecord:
    tournament_name: str
    date_str: str
    player_name: str
    wins: int
    draws: int
    losses: int
    commander_name: str
    commanders: list[tuple[str, int]]
    mainboard: list[tuple[str, int]]
    is_complete: bool
    top_cut: int = 0
    wins_bracket: int | None = None
    losses_bracket: int | None = None


def fetch_slice(
    start_ts: int,
    end_ts: int,
    *,
    api_key: str,
    user_agent: str,
    cache_path: Path,
    delay: float = 13.0,
    offline_only: bool = False,
    force_refresh: bool = False,
) -> list[dict[str, object]]:
    """Fetch or load cached tournaments for a time slice."""
    if cache_path.is_file() and not force_refresh:
        logger.info("Loading cached slice: %s", cache_path.name)
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning("Corrupted cache file %s: %s", cache_path, e)

    if offline_only:
        logger.warning("Offline mode: cache missing for slice %s", cache_path.name)
        return []

    logger.info(
        "Requesting TopDeck tournaments [%s - %s] (start=%d, end=%d)...",
        datetime.datetime.fromtimestamp(start_ts, tz=datetime.UTC).strftime("%Y-%m-%d"),
        datetime.datetime.fromtimestamp(end_ts, tz=datetime.UTC).strftime("%Y-%m-%d"),
        start_ts,
        end_ts,
    )

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "User-Agent": user_agent,
        "Accept": "application/json",
    }
    payload = {
        "game": "Magic: The Gathering",
        "format": "EDH",
        "start": start_ts,
        "end": end_ts,
        "columns": [
            "name",
            "id",
            "decklist",
            "wins",
            "draws",
            "losses",
            "winsBracket",
            "lossesBracket",
        ],
    }

    for attempt in range(1, 4):
        t0 = time.time()
        req = urllib.request.Request(
            TOPDECK_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode("utf-8"))
                elapsed = time.time() - t0
                logger.info("Received %d tournaments in %.2fs", len(data), elapsed)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(raw_bytes)
                # Sleep to respect rate limits
                logger.info("Sleeping %.1fs for rate limit...", delay)
                time.sleep(delay)
                return data if isinstance(data, list) else []
        except urllib.error.HTTPError as e:
            logger.error("HTTP %d on attempt %d: %s", e.code, attempt, e.reason)
            if e.code in (403, 429):
                raise RuntimeError(f"Rate limited or blocked by TopDeck: HTTP {e.code}") from e
            if attempt == 3:
                raise RuntimeError(f"Failed to fetch slice after 3 attempts: HTTP {e.code}") from e
            time.sleep(delay)
        except Exception as e:
            logger.error("Attempt %d failed to fetch slice: %s", attempt, e)
            if attempt == 3:
                raise RuntimeError(f"Failed to fetch slice after 3 attempts: {e}") from e
            time.sleep(delay)

    return []


def process_tournaments(
    tournaments: list[dict[str, object]],
    commander_names: list[str],
) -> tuple[dict[str, object], dict[str, list[DecklistRecord]]]:
    """Process tournaments and aggregate presence and decklists."""
    # Deduplicate tournaments by TID
    unique_tournaments: dict[str, dict[str, object]] = {}
    for t in tournaments:
        tid = str(t.get("TID") or "")
        if tid and tid not in unique_tournaments:
            unique_tournaments[tid] = t
        elif not tid:
            unique_tournaments[f"anon_{len(unique_tournaments)}"] = t

    total_standings = 0
    standings_with_leader = 0

    commander_set = set(commander_names)
    presence_counts: dict[str, int] = {c: 0 for c in commander_names}
    decks_by_commander: dict[str, list[DecklistRecord]] = {c: [] for c in commander_names}

    for t in unique_tournaments.values():
        t_name = str(t.get("tournamentName") or t.get("name") or "Unknown Tournament").strip()
        top_cut = int(t.get("topCut") or 0)
        start_ts = t.get("startDate")
        if isinstance(start_ts, (int, float)):
            date_str = datetime.datetime.fromtimestamp(start_ts, tz=datetime.UTC).strftime(
                "%Y-%m-%d"
            )
        else:
            date_str = ""

        standings = t.get("standings", [])
        if not isinstance(standings, list):
            continue

        for s in standings:
            if not isinstance(s, dict):
                continue
            total_standings += 1

            leader = str(s.get("leader") or "").strip()
            if leader:
                standings_with_leader += 1

            player = str(s.get("name") or "Unknown Player").strip()
            wins = int(s.get("wins", 0) or 0)
            draws = int(s.get("draws", 0) or 0)
            losses = int(s.get("losses", 0) or 0)

            wb_raw = s.get("winsBracket")
            lb_raw = s.get("lossesBracket")
            wins_bracket = int(wb_raw) if wb_raw is not None else None
            losses_bracket = int(lb_raw) if lb_raw is not None else None

            # Extract deck
            deck_obj = s.get("deckObj")
            decklist_str = str(s.get("decklist") or "").strip()

            cmd_cards: list[tuple[str, int]] = []
            mb_cards: list[tuple[str, int]] = []

            if isinstance(deck_obj, dict) and ("Commanders" in deck_obj or "Mainboard" in deck_obj):
                cmd_cards = extract_cards_from_section(deck_obj.get("Commanders"))
                mb_cards = extract_cards_from_section(deck_obj.get("Mainboard"))
            elif decklist_str:
                cmd_cards, mb_cards = parse_decklist_text(decklist_str)

            # Determine commander identity
            matched_commander: str | None = None
            if leader in commander_set:
                matched_commander = leader

            if matched_commander:
                presence_counts[matched_commander] += 1

                has_deck = bool(cmd_cards or mb_cards)
                if has_deck:
                    tot_cmd_qty = sum(q for _, q in cmd_cards)
                    tot_mb_qty = sum(q for _, q in mb_cards)
                    is_complete = (tot_cmd_qty == 1) and (tot_mb_qty == 99)

                    record = DecklistRecord(
                        tournament_name=t_name,
                        date_str=date_str,
                        player_name=player,
                        wins=wins,
                        draws=draws,
                        losses=losses,
                        commander_name=matched_commander,
                        commanders=cmd_cards,
                        mainboard=mb_cards,
                        is_complete=is_complete,
                        top_cut=top_cut,
                        wins_bracket=wins_bracket,
                        losses_bracket=losses_bracket,
                    )
                    decks_by_commander[matched_commander].append(record)

    stats = {
        "unique_tournaments": len(unique_tournaments),
        "standings_total_90d": total_standings,
        "standings_with_leader_90d": standings_with_leader,
        "presence_counts": presence_counts,
    }
    return stats, decks_by_commander


def export_results(
    stats: dict[str, object],
    decks_by_commander: dict[str, list[DecklistRecord]],
    output_dir: Path,
    commander_names: list[str],
    chulane_out_path: Path | None = None,
) -> dict[str, object]:
    """Export presence CSV and per-commander deck CSVs.

    Player names are anonymized to initials in every exported deck CSV
    (Owner decision #1108, 2026-11-13); see anonymize_player_labels.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    presence_counts = stats["presence_counts"]  # type: ignore
    total_standings = int(stats["standings_total_90d"])  # type: ignore
    leader_standings = int(stats["standings_with_leader_90d"])  # type: ignore

    # 1. Export topdeck_commander_presence.csv
    presence_csv_path = output_dir / "topdeck_commander_presence.csv"
    with presence_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "commander_name",
                "topdeck_entries_90d",
                "standings_total_90d",
                "standings_with_leader_90d",
            ]
        )
        for cname in commander_names:
            writer.writerow(
                [cname, presence_counts.get(cname, 0), total_standings, leader_standings]
            )

    logger.info("Wrote %s", presence_csv_path)

    # 2. Export per-commander deck CSVs
    exported_commanders_count = 0
    total_exported_decks = 0
    total_incomplete_decks = 0
    exported_files: list[str] = [presence_csv_path.name]

    per_commander_summary: dict[str, dict[str, int]] = {}

    for cname in commander_names:
        deck_records = decks_by_commander.get(cname, [])
        entries_with_list = len(deck_records)
        complete_decks = [d for d in deck_records if d.is_complete]
        incomplete_decks = [d for d in deck_records if not d.is_complete]

        total_incomplete_decks += len(incomplete_decks)

        per_commander_summary[cname] = {
            "entries_total": presence_counts.get(cname, 0),
            "entries_with_list": entries_with_list,
            "complete_exported": len(complete_decks),
            "incomplete_excluded": len(incomplete_decks),
        }

        is_chulane = cname == "Chulane, Teller of Tales"
        if is_chulane and not chulane_out_path:
            continue

        if complete_decks:
            if is_chulane:
                assert chulane_out_path is not None
                deck_csv_path = chulane_out_path
                deck_csv_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                slug = to_safe_slug(cname)
                deck_csv_path = output_dir / f"topdeck_{slug}_decks.csv"

            labels = anonymize_player_labels(d.player_name for d in complete_decks)

            with deck_csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "tournament",
                        "date",
                        "player",
                        "wins",
                        "draws",
                        "losses",
                        "card_name",
                        "quantity",
                        "section",
                        "top_cut",
                        "wins_bracket",
                        "losses_bracket",
                    ]
                )
                for d in complete_decks:
                    player_label = labels[d.player_name]
                    wb_str = str(d.wins_bracket) if d.wins_bracket is not None else ""
                    lb_str = str(d.losses_bracket) if d.losses_bracket is not None else ""
                    for card_name, qty in d.commanders:
                        writer.writerow(
                            [
                                d.tournament_name,
                                d.date_str,
                                player_label,
                                d.wins,
                                d.draws,
                                d.losses,
                                card_name,
                                qty,
                                "commander",
                                d.top_cut,
                                wb_str,
                                lb_str,
                            ]
                        )
                    # Sort mainboard cards alphabetically
                    sorted_mb = sorted(d.mainboard, key=lambda x: x[0].lower())
                    for card_name, qty in sorted_mb:
                        writer.writerow(
                            [
                                d.tournament_name,
                                d.date_str,
                                player_label,
                                d.wins,
                                d.draws,
                                d.losses,
                                card_name,
                                qty,
                                "main",
                                d.top_cut,
                                wb_str,
                                lb_str,
                            ]
                        )

            exported_commanders_count += 1
            total_exported_decks += len(complete_decks)
            exported_files.append(deck_csv_path.name)
            logger.info(
                "Exported %d complete deck(s) for %s to %s",
                len(complete_decks),
                cname,
                deck_csv_path.name,
            )

    # 3. Export README.md
    readme_path = output_dir / "README.md"
    readme_content = f"""# TopDeck.gg Turnier-Decklisten & Präsenz (90 Tage)

Erstellt durch Gemini Flash (Paket C, Refs #1205, #1208).
Abrufdatum: {datetime.date.today().isoformat()}.

> **Hinweis zur Datenquelle:**
> Data provided by TopDeck.gg (https://topdeck.gg).

## 1. Zählprotokoll
- **Untersuchungsfenster:** 90 Tage ({datetime.date.today() - datetime.timedelta(days=90)} bis {datetime.date.today()})
- **Erfasste Turniere (distinkt):** {stats["unique_tournaments"]}
- **Standings gesamt:** {total_standings}
- **Standings mit Leader:** {leader_standings}
- **Untersuchte Commander:** {len(commander_names)}
- **Commander mit Turnier-Präsenz (>0 Einträge):** {sum(1 for c in commander_names if presence_counts.get(c, 0) > 0)}
- **Exportierte Commander (außer Chulane, mit vollständigen Listen):** {exported_commanders_count}
- **Vollständige exportierte Decklisten (1 Commander + 99 Mainboard):** {total_exported_decks}
- **Unvollständige Decklisten (gezählt, aber nicht exportiert):** {total_incomplete_decks}

## 2. Dateien
- `topdeck_commander_presence.csv`: Aktualisierte Präsenz-Zählung aller {len(commander_names)} Commander.
- `topdeck_<commander_slug>_decks.csv`: Vollständige Decklisten je Commander mit mindestens 1 vollständiger Liste.

## 3. Übersicht je Commander mit Präsenz
| Commander | Einträge 90d | Einträge mit Liste | Vollständig exportiert | Unvollständig |
|---|---|---|---|---|
"""
    for cname in commander_names:
        cnt = presence_counts.get(cname, 0)
        if cnt > 0:
            s = per_commander_summary[cname]
            readme_content += (
                f"| {cname} | {cnt} | {s['entries_with_list']} | "
                f"{s['complete_exported']} | {s['incomplete_excluded']} |\n"
            )

    readme_path.write_text(readme_content, encoding="utf-8")
    logger.info("Wrote %s", readme_path)

    return {
        "presence_csv": str(presence_csv_path),
        "readme": str(readme_path),
        "exported_commanders_count": exported_commanders_count,
        "total_exported_decks": total_exported_decks,
        "total_incomplete_decks": total_incomplete_decks,
        "per_commander_summary": per_commander_summary,
        "exported_files": exported_files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect TopDeck.gg tournament decks.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/research/topdeck_20261112"),
        help="Directory to output exported CSVs and README",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache/topdeck_tournaments"),
        help="Cache directory for raw tournament responses",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Days window to fetch (default: 90)",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=10,
        help="Chunk size in days per API request (default: 10)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=13.0,
        help="Delay in seconds between live requests (default: 13.0)",
    )
    parser.add_argument(
        "--start-ts",
        type=int,
        default=None,
        help="Explicit start timestamp for harvest window",
    )
    parser.add_argument(
        "--end-ts",
        type=int,
        default=None,
        help="Explicit end timestamp for harvest window",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force re-fetching slices from API even if cached",
    )
    parser.add_argument(
        "--chulane-out",
        type=Path,
        default=Path("data/research/deckbuilder_1655/topdeck_chulane_decks.csv"),
        help="Output CSV path for Chulane decks",
    )
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="Do not make network requests; use existing cached slices",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    api_key = ""
    if not args.offline_only:
        try:
            api_key = get_api_key()
        except Exception as e:
            logger.error("%s", e)
            sys.exit(1)

    now = int(time.time())
    start_total = args.start_ts if args.start_ts is not None else (now - (args.days * 86400))
    end_total = args.end_ts if args.end_ts is not None else now
    chunk_sec = args.chunk_days * 86400

    all_tournaments: list[dict[str, object]] = []

    if args.offline_only:
        cached_files = sorted(args.cache_dir.glob("topdeck_slice_*.json"))
        if cached_files:
            logger.info("Offline mode: loading %d cached slice files", len(cached_files))
            for cf in cached_files:
                try:
                    with cf.open("r", encoding="utf-8") as f:
                        sdata = json.load(f)
                        if isinstance(sdata, list):
                            all_tournaments.extend(sdata)
                except Exception as e:
                    logger.warning("Failed to load %s: %s", cf, e)
        else:
            logger.warning("Offline mode: no cached slices found in %s", args.cache_dir)
    else:
        current_start = start_total
        slice_idx = 0

        while current_start < end_total:
            current_end = min(current_start + chunk_sec, end_total)
            cache_file = (
                args.cache_dir / f"topdeck_slice_{slice_idx}_{current_start}_{current_end}.json"
            )

            slice_data = fetch_slice(
                current_start,
                current_end,
                api_key=api_key,
                user_agent=DEFAULT_USER_AGENT,
                cache_path=cache_file,
                delay=args.delay,
                offline_only=args.offline_only,
                force_refresh=args.force_refresh,
            )
            all_tournaments.extend(slice_data)

            current_start = current_end
            slice_idx += 1

    logger.info("Total raw tournaments collected: %d", len(all_tournaments))

    stats, decks = process_tournaments(all_tournaments, DEFAULT_107_COMMANDERS)
    summary = export_results(
        stats,
        decks,
        args.output_dir,
        DEFAULT_107_COMMANDERS,
        chulane_out_path=args.chulane_out,
    )

    logger.info("Collection and export complete: %s", summary)


if __name__ == "__main__":
    main()
