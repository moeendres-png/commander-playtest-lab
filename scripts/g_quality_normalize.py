from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

FILES = [
    "src/commander_lab/agents/pilots.py",
    "src/commander_lab/engine/structural/fixtures.py",
    "src/commander_lab/engine/structural/profiles.py",
    "src/commander_lab/engine/structural/simulator.py",
    "src/commander_lab/evals/golden.py",
    "src/commander_lab/evals/models.py",
    "src/commander_lab/models/meta.py",
    "src/commander_lab/models/pilots.py",
    "src/commander_lab/models/roles.py",
    "src/commander_lab/models/structural.py",
    "tests/golden/test_g_decision_quality.py",
    "tests/unit/test_g_modeling_quality.py",
]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, check=check)


def direct_mechanic_imports() -> None:
    for filename in [
        "src/commander_lab/agents/pilots.py",
        "src/commander_lab/engine/structural/fixtures.py",
        "src/commander_lab/engine/structural/profiles.py",
    ]:
        path = Path(filename)
        text = path.read_text()
        text = text.replace("    StructuralMechanic,\n", "")
        start = text.index("from commander_lab.models import (")
        end = text.index(")\n", start) + 2
        direct = "from commander_lab.models.roles import StructuralMechanic\n"
        if direct not in text:
            text = text[:end] + direct + text[end:]
        path.write_text(text)

    path = Path("tests/unit/test_g_modeling_quality.py")
    text = path.read_text().replace(
        "from commander_lab.models import CardRole, FormatBand, MetaCategory, StructuralMechanic\n",
        "from commander_lab.models import CardRole, FormatBand, MetaCategory\n"
        "from commander_lab.models.roles import StructuralMechanic\n",
    )
    path.write_text(text)


def manual_non_autofixes() -> None:
    path = Path("src/commander_lab/agents/pilots.py")
    text = path.read_text().replace(
        "        if CardRole.COMBAT_PAYOFF in action.roles or action.base_power >= 5:\n"
        "            if korvold_online:\n"
        "                bonus += 0.4\n",
        "        if (CardRole.COMBAT_PAYOFF in action.roles or action.base_power >= 5) and korvold_online:\n"
        "            bonus += 0.4\n",
    )
    path.write_text(text)

    path = Path("src/commander_lab/engine/structural/fixtures.py")
    text = path.read_text()
    replacements = {
        '                            notes=f"Exact verified opponent snapshot card for {deck_id}; source_status={source_status}.",\n': (
            '                            notes=(\n'
            '                                f"Exact verified opponent snapshot card for {deck_id}; "\n'
            '                                f"source_status={source_status}."\n'
            '                            ),\n'
        ),
        '                    f"verified opponent snapshot {deck_id} contains {len(exact_cards)} cards, expected 100"\n': (
            '                    f"verified opponent snapshot {deck_id} contains {len(exact_cards)} cards, "\n'
            '                    "expected 100"\n'
        ),
        '                notes=f"Current opponent commander role profile; source_status={source_status}; evidence_status={spec.get(\'evidence_status\', \'unknown\')}.",\n': (
            '                notes=(\n'
            '                    "Current opponent commander role profile; "\n'
            '                    f"source_status={source_status}; "\n'
            '                    f"evidence_status={spec.get(\'evidence_status\', \'unknown\')}."\n'
            '                ),\n'
        ),
        '                    notes=f"Decision-relevant named opponent profile; source_status={source_status}; evidence_status={spec.get(\'evidence_status\', \'unknown\')}.",\n': (
            '                    notes=(\n'
            '                        "Decision-relevant named opponent profile; "\n'
            '                        f"source_status={source_status}; "\n'
            '                        f"evidence_status={spec.get(\'evidence_status\', \'unknown\')}."\n'
            '                    ),\n'
        ),
        '                    notes=f"Structural role-density card for {deck_id}; source_status={source_status}.",\n': (
            '                    notes=(\n'
            '                        f"Structural role-density card for {deck_id}; "\n'
            '                        f"source_status={source_status}."\n'
            '                    ),\n'
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text)

    path = Path("src/commander_lab/engine/structural/simulator.py")
    text = path.read_text()
    text = text.replace(
        "return int(math.ceil(base_cost + 2 * prior_casts))",
        "return math.ceil(base_cost + 2 * prior_casts)",
    )
    text = text.replace(
        "amount = max(1, int(math.ceil(card.strength(CardRole.DRAW))))",
        "amount = max(1, math.ceil(card.strength(CardRole.DRAW)))",
    )
    path.write_text(text)

    path = Path("tests/unit/test_g_modeling_quality.py")
    text = path.read_text().replace(
        "    # The model stays a 100-card structural completion; only the four hard-known Cosmic names are represented natively.\n",
        "    # The model stays a 100-card structural completion; only the four hard-known Cosmic names\n"
        "    # are represented natively.\n",
    )
    path.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    args = parser.parse_args()

    direct_mechanic_imports()
    run("git", "checkout", args.base_sha, "--", "src/commander_lab/models/__init__.py")
    run("ruff", "check", "--fix", "--", *FILES, check=False)
    run("ruff", "format", "--", *FILES)
    manual_non_autofixes()
    run("ruff", "format", "--", *FILES)
    run("ruff", "check", "--", *FILES)
    run("ruff", "format", "--check", "--", *FILES)
    run("git", "diff", "--check")
    run("python", "-m", "compileall", "-q", "src", "tests")
    run(
        "pytest",
        "-q",
        "tests/golden/test_g_decision_quality.py",
        "tests/unit/test_g_modeling_quality.py",
    )


if __name__ == "__main__":
    main()
