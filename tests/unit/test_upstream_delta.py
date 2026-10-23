"""Upstream delta check: classification, card-name mapping, deck cross-reference and the merge
dry-run, on a small synthetic repository with a fork branch and an upstream branch."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "upstream_delta", ROOT / "scripts/upstream_delta.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


delta = _module()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write(repo: Path, path: str, text: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _registration(*cards: tuple[str, str, str]) -> str:
    rows = "".join(
        f'        cards.add(new SetCardInfo("{name}", 1, Rarity.RARE, mage.cards.{letter}.{cls}.class));\n'
        for name, letter, cls in cards
    )
    return f"class SomeSet {{\n    SomeSet() {{\n{rows}    }}\n}}\n"


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "fork"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _write(
        root, "Mage.Sets/src/mage/sets/SomeSet.java", _registration(("Old Card", "o", "OldCard"))
    )
    _write(root, "Mage.Sets/src/mage/cards/o/OldCard.java", "class OldCard { int v = 1; }\n")
    _write(root, "Mage/src/main/java/mage/Engine.java", "class Engine { int v = 1; }\n")
    base = _commit(root, "base")

    # upstream: a card changed, a card added (with its registration), an engine fix, a test
    _git(root, "checkout", "-q", "-b", "upstream", base)
    _write(root, "Mage.Sets/src/mage/cards/o/OldCard.java", "class OldCard { int v = 2; }\n")
    _write(root, "Mage.Sets/src/mage/cards/n/NewCard.java", "class NewCard {}\n")
    _write(
        root,
        "Mage.Sets/src/mage/sets/SomeSet.java",
        _registration(("Old Card", "o", "OldCard"), ("New Card", "n", "NewCard")),
    )
    _commit(root, "[SET] Implement New Card")
    _write(root, "Mage/src/main/java/mage/Engine.java", "class Engine { int v = 2; }\n")
    _write(root, "Mage.Tests/src/test/java/EngineTest.java", "class EngineTest {}\n")
    _commit(root, "Fix the engine")
    _write(root, "Utils/mtg-cards-data.txt", "data\n")
    _commit(root, "Update data")
    upstream = _git(root, "rev-parse", "HEAD")

    # fork pin: its own change to the same engine line, so a merge conflicts
    _git(root, "checkout", "-q", "-b", "pin", base)
    _write(root, "Mage/src/main/java/mage/Engine.java", "class Engine { int v = 3; }\n")
    pin = _commit(root, "fork change")
    return {"root": root, "base": base, "upstream": upstream, "pin": pin}


def _decks(tmp_path: Path) -> Path:
    decks = tmp_path / "decks"
    decks.mkdir()
    deck = {
        "commander": {"commanders": ["Old Card"]},
        "cards": [{"oracle_name": "New Card // Back Side", "quantity": 1}],
    }
    (decks / "demo.json").write_text(json.dumps(deck), encoding="utf-8")
    return decks


def test_classify_path_covers_every_kind() -> None:
    cases = {
        "Mage.Sets/src/mage/cards/a/Foo.java": "card",
        "Mage.Sets/src/mage/sets/Bar.java": "set",
        "Mage.Tests/src/test/java/X.java": "test",
        "Mage.Verify/src/test/java/X.java": "verify",
        "Utils/mtg-cards-data.txt": "data",
        ".github/workflows/maven.yml": "ci",
        "Mage/src/main/java/mage/Y.java": "engine",
        "Mage.Server/src/main/java/Z.java": "engine",
        "README.md": "other",
    }
    assert {path: delta.classify_path(path) for path in cases} == cases


def test_commit_kinds_come_back_in_a_fixed_order() -> None:
    files = ["Utils/a.txt", "Mage/src/main/java/A.java", "Mage.Tests/T.java"]
    assert delta.commit_kinds(files) == ["engine", "test", "data"]


def test_parse_log_splits_records_and_files() -> None:
    sep, fld = delta._RECORD, delta._FIELD
    text = (
        f"{sep}aaa{fld}2026-10-22{fld}A. Author{fld}Fix: a | b\nMage/src/main/java/X.java\n\n"
        f"{sep}bbb{fld}2026-10-21{fld}B{fld}[SET] Implement C\n"
        "Mage.Sets/src/mage/cards/c/C.java\nMage.Sets/src/mage/sets/S.java\n"
    )
    first, second = delta.parse_log(text)
    assert (first["sha"], first["subject"], first["kinds"]) == ("aaa", "Fix: a | b", ["engine"])
    assert second["files"] == [
        "Mage.Sets/src/mage/cards/c/C.java",
        "Mage.Sets/src/mage/sets/S.java",
    ]
    assert second["kinds"] == ["card", "set"]


def test_front_face_strips_the_back() -> None:
    assert delta.front_face("Delver of Secrets // Insectile Aberration") == "Delver of Secrets"
    assert delta.front_face("Sol Ring") == "Sol Ring"


def test_card_classes_are_added_or_modified_and_named(repo: dict[str, Any]) -> None:
    changes = delta.card_class_changes(repo["root"], repo["base"], repo["upstream"])
    assert changes == {"OldCard": "modified", "NewCard": "added"}
    names = delta.card_names_for_classes(repo["root"], repo["upstream"], list(changes))
    assert names == {"OldCard": "Old Card", "NewCard": "New Card"}


def test_a_class_without_a_registration_has_no_name(repo: dict[str, Any]) -> None:
    assert delta.card_names_for_classes(repo["root"], repo["upstream"], ["GhostCard"]) == {}


def test_registered_names_tell_which_cards_a_ref_has(repo: dict[str, Any]) -> None:
    cards = ["Old Card", "New Card", "Nobody"]
    assert delta.registered_names(repo["root"], repo["pin"], cards) == {"Old Card"}
    assert delta.registered_names(repo["root"], repo["upstream"], cards) == {"Old Card", "New Card"}


def test_merge_dry_run_names_the_conflicting_file(repo: dict[str, Any]) -> None:
    result = delta.merge_conflicts(repo["root"], repo["pin"], repo["upstream"])
    assert result == {
        "status": "CONFLICTS",
        "conflicted_files": ["Mage/src/main/java/mage/Engine.java"],
    }


def test_merge_dry_run_is_clean_without_a_competing_change(repo: dict[str, Any]) -> None:
    clean = delta.merge_conflicts(repo["root"], repo["base"], repo["upstream"])
    assert clean == {"status": "CLEAN", "conflicted_files": []}


def test_the_report_counts_decks_and_the_collection(repo: dict[str, Any], tmp_path: Path) -> None:
    collection = tmp_path / "collection.txt"
    collection.write_text("New Card\nSomething Else\n", encoding="utf-8")
    report = delta.build_report(
        repo["root"],
        repo["pin"],
        repo["upstream"],
        precon_dir=_decks(tmp_path),
        collection_file=collection,
    )
    assert report["commits_total"] == 3
    assert report["commits_by_kind"] == {"engine": 1, "card": 1, "set": 1, "test": 1, "data": 1}
    assert report["card_classes"] == {"added": 1, "modified": 1, "deleted": 0, "name_unresolved": 0}
    assert [c["name"] for c in report["changed_cards_in_precons"]] == ["New Card", "Old Card"]
    assert report["changed_cards_in_collection"] == 1
    assert [c["subject"] for c in report["engine_commits"]] == ["Fix the engine"]
    assert report["merge"]["status"] == "CONFLICTS"
    # No importer report: the pin's registry decides. New Card is unregistered there and
    # registered upstream; Old Card is registered at the pin already.
    assert report["missing_precon_cards_source"] == "registry at the pin"
    assert report["missing_precon_cards_total"] == 1
    assert report["missing_precon_cards_now_implemented"] == [
        {"name": "New Card", "decks": ["demo"]}
    ]


def test_a_missing_precon_card_counts_only_when_upstream_gained_it(
    repo: dict[str, Any], tmp_path: Path
) -> None:
    import_report = {
        "results": [
            {"deck": "demo", "missing_cards": [{"card": "New Card"}, {"card": "Old Card"}]},
            {"deck": "other", "missing_cards": [{"card": "Nobody"}]},
            {"deck": "fine"},
        ]
    }
    report = delta.build_report(
        repo["root"],
        repo["pin"],
        repo["upstream"],
        precon_dir=_decks(tmp_path),
        collection_file=tmp_path / "absent.txt",
        import_report=import_report,
    )
    # Old Card is registered at the pin already, Nobody nowhere: only New Card is a gain.
    assert report["missing_precon_cards_now_implemented"] == [
        {"name": "New Card", "decks": ["demo"]}
    ]


def test_markdown_names_the_merge_state_and_the_gains(repo: dict[str, Any], tmp_path: Path) -> None:
    report = delta.build_report(
        repo["root"],
        repo["pin"],
        repo["upstream"],
        precon_dir=_decks(tmp_path),
        collection_file=tmp_path / "absent.txt",
        import_report={"results": [{"deck": "demo", "missing_cards": [{"card": "New Card"}]}]},
    )
    text = delta.render_markdown(report)
    assert "3 commits the pin lacks" in text
    assert "Merge into the pin: **CONFLICTS** (1 files)" in text
    assert "- New Card (demo)" in text
    assert "Fix the engine" in text


def test_an_unknown_pin_is_a_git_error_not_an_empty_report(repo: dict[str, Any]) -> None:
    with pytest.raises(subprocess.CalledProcessError):
        delta.build_report(repo["root"], "0" * 40, repo["upstream"])


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("    public void restore(GameState state) {", ("restore", "GameState")),
        ("    public Api(int x, Map<A, B> m) {", ("Api", "int,Map<A,B>")),
        ("    Foo bar(final Game g, @Nullable UUID id);", ("bar", "Game,UUID")),
        (
            "    public int[] values(Map<String, List<Integer>> m, String... rest) {",
            ("values", "Map<String,List<Integer>>,String..."),
        ),
        (
            "    @Override public boolean apply(Game game, Ability source) {",
            ("apply", "Game,Ability"),
        ),
        ("        return foo(x);", None),
        ("        foo(x);", None),
        ("    FOO(1);", None),
        ("        final Foo x = bar(y);", None),
        ("        else if (x) {", None),
        ("        Foo bar(Game g);", None),
    ],
)
def test_parse_declaration_reads_member_declarations_only(
    line: str, expected: tuple[str, str] | None
) -> None:
    assert delta.parse_declaration(line) == expected


@pytest.fixture()
def signature_repo(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "sig"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    api = (
        "class Api {\n"
        "    public Api(int x) {\n    }\n"
        "    public void restore(GameState state) {\n    }\n"
        "    private void gone(String s) {\n    }\n"
        "    public int helper(int a) {\n        return a;\n    }\n"
        "}\n"
    )
    _write(root, "Mage/src/main/java/mage/Api.java", api)
    _write(root, "Mage/src/main/java/mage/Foo.java", "interface Foo {\n    Foo bar(Game g);\n}\n")
    _write(
        root, "Mage.Sets/src/mage/sets/SomeSet.java", _registration(("Odd Card", "o", "OddCard"))
    )
    _write(root, "Mage.Sets/src/mage/cards/o/OddCard.java", "class OddCard {}\n")
    base = _commit(root, "base")

    _git(root, "checkout", "-q", "-b", "upstream", base)
    changed = (
        api.replace("Api(int x)", "Api(int x, int y)")
        .replace("restore(GameState state)", "restore(GameState state, boolean full)")
        .replace("    private void gone(String s) {\n    }\n", "")
        .replace("int a) {\n        return a;", "int renamed) {\n        return renamed;")
    )
    _write(root, "Mage/src/main/java/mage/Api.java", changed)
    _write(
        root,
        "Mage/src/main/java/mage/Foo.java",
        "interface Foo {\n    Foo bar(Game g, int n);\n}\n",
    )
    _write(
        root,
        "Mage.Sets/src/mage/cards/o/OddCard.java",
        "class OddCard {\n    Map<UUID, Set<UUID>> m = new HashMap<>();\n"
        "    int roll = RandomUtil.nextInt(6);\n}\n",
    )
    upstream = _commit(root, "upstream changes the API")

    _git(root, "checkout", "-q", "-b", "pin", base)
    _write(
        root,
        "Mage.Tests/src/test/java/StateTest.java",
        "class StateTest {\n    void t() {\n        api.restore(state);\n    }\n}\n",
    )
    _write(
        root,
        "Mage/src/main/java/mage/Other.java",
        'class Other {\n    void t() { gone("x"); }\n}\n',
    )
    pin = _commit(root, "fork test and caller")

    lab = tmp_path / "lab-bridge" / "src"
    _write(
        lab.parent, "src/main/Bridge.java", 'class Bridge {\n    void t() { api.gone("s"); }\n}\n'
    )
    return {"root": root, "base": base, "upstream": upstream, "pin": pin, "lab": lab}


def test_scan_finds_changed_and_removed_signatures_but_not_renamed_parameters(
    signature_repo: dict[str, Any],
) -> None:
    scan = delta.scan_diff(
        signature_repo["root"], signature_repo["base"], signature_repo["upstream"]
    )
    found = {
        (s["name"], s["kind"], s["old_parameters"], tuple(s["new_parameters"]))
        for s in scan["signature_changes"]
    }
    assert found == {
        ("Api", "changed", "int", ("int,int",)),
        ("restore", "changed", "GameState", ("GameState,boolean",)),
        ("gone", "removed", "String", ()),
        ("bar", "changed", "Game", ("Game,int",)),
    }


def test_scan_reports_added_rng_and_unordered_lines_with_their_file(
    signature_repo: dict[str, Any],
) -> None:
    hazards = delta.scan_diff(
        signature_repo["root"], signature_repo["base"], signature_repo["upstream"]
    )["hazards"]
    assert [(h["category"], h["file"].rsplit("/", 1)[-1]) for h in hazards] == [
        ("unordered", "OddCard.java"),
        ("rng", "OddCard.java"),
    ]


def test_callers_are_the_files_the_fork_changed_and_the_lab_bridge(
    signature_repo: dict[str, Any],
) -> None:
    root, base, pin = signature_repo["root"], signature_repo["base"], signature_repo["pin"]
    signatures = delta.scan_diff(root, base, signature_repo["upstream"])["signature_changes"]
    delta.fork_callers(
        root, pin, delta.changed_files(root, base, pin), signatures, signature_repo["lab"]
    )
    callers = {s["name"]: s["fork_callers"] for s in signatures}
    assert callers["restore"] == ["Mage.Tests/src/test/java/StateTest.java"]
    # Api.java declares gone() and is excluded; Other.java is a fork file, Bridge.java the lab.
    assert callers["gone"] == [
        "Mage/src/main/java/mage/Other.java",
        "lab-bridge/src/main/Bridge.java",
    ]
    assert callers["bar"] == []


def test_the_report_ties_hazards_to_precon_decks_and_signatures_to_callers(
    signature_repo: dict[str, Any], tmp_path: Path
) -> None:
    decks = tmp_path / "decks"
    decks.mkdir()
    (decks / "odd.json").write_text(
        json.dumps({"commander": {"commanders": ["Odd Card"]}, "cards": []}), encoding="utf-8"
    )
    report = delta.build_report(
        signature_repo["root"],
        signature_repo["pin"],
        signature_repo["upstream"],
        precon_dir=decks,
        collection_file=tmp_path / "absent.txt",
        lab_sources=signature_repo["lab"],
    )
    assert [h["card"] for h in report["hazards_in_precons"]] == ["Odd Card", "Odd Card"]
    assert {s["name"] for s in report["signature_changes_with_fork_callers"]} == {"restore", "gone"}
    text = delta.render_markdown(report)
    assert "Determinism hazards in new upstream lines: 1 RNG, 1 unordered collection" in text
    assert "changed `restore(GameState)` to `(GameState,boolean)` in `Api.java`" in text
    assert "name also used in StateTest.java" in text
    assert "removed `gone(String)` in `Api.java`" in text


def test_pull_request_status_attaches_to_missing_cards_only(
    repo: dict[str, Any], tmp_path: Path
) -> None:
    report = delta.build_report(
        repo["root"],
        repo["pin"],
        repo["upstream"],
        precon_dir=_decks(tmp_path),
        collection_file=tmp_path / "absent.txt",
        import_report={
            "results": [{"deck": "demo", "missing_cards": [{"card": "Nobody"}, {"card": "Other"}]}]
        },
        pull_requests={"Nobody": {"number": 7, "state": "open"}, "Unrelated": {"number": 8}},
    )
    assert report["missing_precon_cards_total"] == 2
    assert report["missing_precon_cards_with_pull_request"] == [
        {"name": "Nobody", "decks": ["demo"], "pull_request": {"number": 7, "state": "open"}}
    ]


def test_registry_matching_ignores_accents_and_matches_split_faces(tmp_path: Path) -> None:
    root = tmp_path / "reg"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _write(
        root,
        "Mage.Sets/src/mage/sets/SomeSet.java",
        _registration(
            ("Lothlorien Blade", "l", "LothlorienBlade"), ("Fire // Ice", "f", "FireIce")
        ),
    )
    ref = _commit(root, "registry")
    cards = ["Lothlórien Blade", "Fire", "Fire // Ice", "Ice", "Nobody"]
    # A bare back face ("Ice") is not a name a deck lists, so it does not match.
    assert delta.registered_names(root, ref, cards) == {"Lothlórien Blade", "Fire", "Fire // Ice"}


def test_triggers_are_measured_where_a_script_can_and_flagged_where_it_cannot(
    repo: dict[str, Any], tmp_path: Path
) -> None:
    report = delta.build_report(
        repo["root"],
        repo["pin"],
        repo["upstream"],
        precon_dir=_decks(tmp_path),
        collection_file=tmp_path / "absent.txt",
        today=date.today() + timedelta(weeks=7),
    )
    rows = {name.split()[0]: row for name, row in report["triggers"].items()}
    assert rows["T1"]["status"] == "REVIEW"
    assert rows["T2"] == {"status": "NOT_MET", "detail": "upstream POM unreadable"}
    # demo needs New Card, which upstream registers: one deck, below the threshold of two.
    assert rows["T3"]["status"] == "NOT_MET"
    assert "1 would be complete" in rows["T3"]["detail"]
    assert rows["T4"]["status"] == "OWNER"
    assert rows["T5"]["status"] == "MET"  # Engine.java conflicts
    assert rows["T6"]["status"] == "MET"
    assert "Repin trigger" in delta.render_markdown(report)


def test_the_pom_version_decides_trigger_t2(tmp_path: Path) -> None:
    root = tmp_path / "pom"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    _write(root, "pom.xml", "<project><version>1.4.62</version></project>\n")
    old = _commit(root, "old")
    _write(root, "pom.xml", "<project><version>1.4.63-dev</version></project>\n")
    new = _commit(root, "new")
    assert delta.pom_version(root, old) == (1, 4, 62)
    assert delta.pom_version(root, new) > delta.RELEASE_VERSION_FLOOR


def test_the_report_never_names_which_cards_the_owner_holds(
    repo: dict[str, Any], tmp_path: Path
) -> None:
    collection = tmp_path / "collection.txt"
    collection.write_text("New Card\n", encoding="utf-8")
    report = delta.build_report(
        repo["root"],
        repo["pin"],
        repo["upstream"],
        precon_dir=_decks(tmp_path),
        collection_file=collection,
    )
    assert report["changed_cards_in_collection"] == 1
    assert all("in_collection" not in card for card in report["changed_cards"])


def test_a_commented_out_registration_is_not_a_registration(tmp_path: Path) -> None:
    root = tmp_path / "commented"
    root.mkdir()
    _git(root, "init", "-q", "-b", "master")
    live = '        cards.add(new SetCardInfo("Live Card", 1, Rarity.RARE, mage.cards.l.LiveCard.class));\n'
    dead = '        //cards.add(new SetCardInfo("Dead Card", 2, Rarity.RARE, mage.cards.d.DeadCard.class));\n'
    _write(root, "Mage.Sets/src/mage/sets/SomeSet.java", f"class SomeSet {{\n{live}{dead}}}\n")
    ref = _commit(root, "registry")
    assert delta.registered_names(root, ref, ["Live Card", "Dead Card"]) == {"Live Card"}
    assert delta.card_names_for_classes(root, ref, ["LiveCard", "DeadCard"]) == {
        "LiveCard": "Live Card"
    }


def test_t3_counts_only_cards_upstream_gained_not_ones_the_pin_already_registers(
    repo: dict[str, Any], tmp_path: Path
) -> None:
    # The importer lists Old Card as missing although the pin registers it (some other cause),
    # so upstream's registration is no gain and the deck is not unblocked by a merge.
    decks = tmp_path / "decks"
    decks.mkdir()
    deck = {"commander": {"commanders": ["Old Card"]}, "cards": [{"name": "New Card"}]}
    (decks / "demo.json").write_text(json.dumps(deck), encoding="utf-8")
    import_report = {
        "results": [{"deck": "demo", "missing_cards": [{"card": "New Card"}, {"card": "Old Card"}]}]
    }
    report = delta.build_report(
        repo["root"],
        repo["pin"],
        repo["upstream"],
        precon_dir=decks,
        collection_file=tmp_path / "absent.txt",
        import_report=import_report,
    )
    t3 = next(row for name, row in report["triggers"].items() if name.startswith("T3"))
    assert "0 would be complete" in t3["detail"]
    assert [c["name"] for c in report["missing_precon_cards_now_implemented"]] == ["New Card"]
