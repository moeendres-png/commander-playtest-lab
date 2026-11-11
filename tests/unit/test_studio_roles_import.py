"""Role import: lossless, scoped, one transaction (#1178). All data here is synthetic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, roles
from commander_lab.studio.__main__ import main
from tests.unit.test_studio_builder import _fill

FOREST = "oracle-forest"
RAT = "oracle-swarm-rat"
FILLER = "oracle-filler-01"


@pytest.fixture
def studio(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _file(
    folder: Path,
    name: str,
    role_ids: dict[str, list[str]],
    *,
    origin: str = roles.ORIGIN_TAGGER,
    mode: str = roles.FULL_SNAPSHOT,
    key: str = "WUG",
    completeness: str | None = None,
    **extra: object,
) -> Path:
    payload: dict[str, object] = {
        "schema": roles.ROLES_SCHEMA,
        "role_origin": origin,
        "fetched_at": "2026-11-11T10:00:00Z",
        "scope": {
            "mode": mode,
            "key": key,
            "completeness": completeness
            or ("COMPLETE_FOR_SCOPE" if mode == roles.FULL_SNAPSHOT else "PARTIAL"),
        },
        "roles": role_ids,
    }
    if origin != roles.ORIGIN_ORACLE_TEXT:
        payload["tags"] = {role: roles.ROLES[role] for role in role_ids}
    if origin == roles.ORIGIN_CROSSWALK:
        payload["crosswalk_version"] = "test-1"
    payload.update(extra)
    path = folder / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _dump(store: StudioStore) -> dict[str, list[tuple[object, ...]]]:
    tables = ("source", "card_role", "card_role_claim", "corpus_deck_role")
    return {
        table: sorted(
            (tuple(row) for row in store.connection.execute(f"SELECT * FROM {table}")), key=repr
        )
        for table in tables
    }


def _pairs(store: StudioStore) -> set[tuple[str, str]]:
    rows = store.connection.execute("SELECT oracle_id, role FROM card_role")
    return {(str(r[0]), str(r[1])) for r in rows}


def _deck_roles(store: StudioStore) -> dict[tuple[str, str], int]:
    rows = store.connection.execute("SELECT deck_id, role, cards FROM corpus_deck_role")
    return {(str(r[0]), str(r[1])): int(r[2]) for r in rows}


def test_a_second_identical_import_changes_nothing(studio: StudioStore, tmp_path: Path) -> None:
    path = _file(tmp_path, "wug.json", {"ramp": [FOREST, FILLER], "removal": [RAT]})
    first = roles.import_roles(studio, path)
    assert first["claims_added"] == 3
    assert first["claims_removed"] == 0
    assert _pairs(studio) == {(FOREST, "ramp"), (FILLER, "ramp"), (RAT, "removal")}
    before = _dump(studio)
    again = roles.import_roles(studio, path)
    assert again["claims_added"] == 0
    assert again["claims_removed"] == 0
    assert _dump(studio) == before
    assert before["card_role_claim"]
    assert _deck_roles(studio) == {
        ("d1", "ramp"): 30,
        ("d2", "ramp"): 36,
        ("d1", "removal"): 1,
        ("d3", "removal"): 1,
        ("d4", "removal"): 1,
    }


def test_partial_packages_only_add_and_keep_the_earlier_ones(
    studio: StudioStore, tmp_path: Path
) -> None:
    first = _file(
        tmp_path, "a.json", {"ramp": [FOREST]}, origin=roles.ORIGIN_ORACLE_TEXT,
        mode=roles.PARTIAL_INCREMENTAL, key="REVIEW_A",
    )  # fmt: skip
    second = _file(
        tmp_path, "b.json", {"removal": [RAT]}, origin=roles.ORIGIN_ORACLE_TEXT,
        mode=roles.PARTIAL_INCREMENTAL, key="REVIEW_B",
    )  # fmt: skip
    overlap = _file(
        tmp_path, "c.json", {"ramp": [FOREST, FILLER], "removal": [RAT]},
        origin=roles.ORIGIN_ORACLE_TEXT, mode=roles.PARTIAL_INCREMENTAL, key="REVIEW_A",
    )  # fmt: skip
    roles.import_roles(studio, first)
    assert _pairs(studio) == {(FOREST, "ramp")}
    assert _deck_roles(studio) == {("d1", "ramp"): 30, ("d2", "ramp"): 36}
    roles.import_roles(studio, second)
    assert _pairs(studio) == {(FOREST, "ramp"), (RAT, "removal")}
    report = roles.import_roles(studio, overlap)
    assert report["claims_added"] == 2  # the filler card (ramp), and the rat again for REVIEW_A
    assert report["claims_removed"] == 0
    assert _pairs(studio) == {(FOREST, "ramp"), (FILLER, "ramp"), (RAT, "removal")}
    assert _deck_roles(studio)[("d1", "ramp")] == 30  # unchanged outside what was added
    assert studio.count("source") >= 3


def test_a_full_snapshot_replaces_only_its_own_origin_scope_and_roles(
    studio: StudioStore, tmp_path: Path
) -> None:
    wug = _file(tmp_path, "wug.json", {"ramp": [FOREST, FILLER], "removal": [RAT]}, key="WUG")
    green = _file(tmp_path, "g.json", {"ramp": [FOREST]}, key="G")
    review = _file(
        tmp_path, "review.json", {"ramp": [RAT]}, origin=roles.ORIGIN_ORACLE_TEXT,
        mode=roles.PARTIAL_INCREMENTAL, key="REVIEW",
    )  # fmt: skip
    for path in (wug, green, review):
        roles.import_roles(studio, path)
    newer = _file(tmp_path, "wug2.json", {"ramp": [FOREST]}, key="WUG")  # no filler, no removal
    before = _dump(studio)
    with pytest.raises(ValueError, match="would remove 1 earlier claims"):
        roles.import_roles(studio, newer)
    assert _dump(studio) == before  # refused: nothing changed, not even the source register
    report = roles.import_roles(studio, newer, allow_scope_replace=True)
    assert report["claims_removed"] == 1
    # the filler card lost its claim; the removal claim stays because "removal" is not in the file
    assert _pairs(studio) == {(FOREST, "ramp"), (RAT, "ramp"), (RAT, "removal")}
    by_origin = report["claims_by_origin"]
    assert by_origin == {roles.ORIGIN_ORACLE_TEXT: 1, roles.ORIGIN_TAGGER: 3}
    # scope G was not touched by a snapshot of WUG
    claims = studio.connection.execute(
        "SELECT role_origin, scope_key, oracle_id, role FROM card_role_claim ORDER BY 1, 2, 3, 4"
    ).fetchall()
    assert ("SCRYFALL_TAGGER_ORIGINAL", "G", FOREST, "ramp") in [tuple(c) for c in claims]


def test_an_oracle_text_review_never_overwrites_a_tagger_label(
    studio: StudioStore, tmp_path: Path
) -> None:
    review = _file(
        tmp_path, "review.json", {"ramp": [FOREST]}, origin=roles.ORIGIN_ORACLE_TEXT,
        mode=roles.PARTIAL_INCREMENTAL, key="REVIEW",
    )  # fmt: skip
    tagger = _file(tmp_path, "tagger.json", {"ramp": [FOREST]})
    roles.import_roles(studio, review)
    review_source = studio.connection.execute("SELECT source_id FROM card_role").fetchone()[0]
    roles.import_roles(studio, tagger)
    claims = studio.connection.execute(
        "SELECT role_origin, original_tag FROM card_role_claim ORDER BY 1"
    ).fetchall()
    assert [tuple(c) for c in claims] == [
        ("ORACLE_TEXT_REVIEW", None),
        ("SCRYFALL_TAGGER_ORIGINAL", "ramp"),
    ]
    tagger_source = studio.connection.execute("SELECT source_id FROM card_role").fetchone()[0]
    assert tagger_source != review_source  # the builder row now points at the tagger label
    # three kinds of statement stay apart: tagger label, normalized by a crosswalk, Oracle text
    normalized = _file(
        tmp_path, "crosswalk.json", {"ramp": [FILLER]}, origin=roles.ORIGIN_CROSSWALK,
        mode=roles.PARTIAL_INCREMENTAL, key="CROSSWALK",
    )  # fmt: skip
    roles.import_roles(studio, normalized)
    rule = studio.connection.execute(
        "SELECT mapping_rule FROM card_role_claim WHERE role_origin = 'CROSSWALK_NORMALIZED'"
    ).fetchone()[0]
    assert rule == "crosswalk:test-1"
    classes = {
        row[0]: row[1] for row in studio.connection.execute("SELECT title, data_class FROM source")
    }
    assert classes["tagger.json"] == "ORIGINAL_SOURCE"
    assert classes["crosswalk.json"] == "NORMALIZED_SOURCE"
    assert classes["review.json"] == "DERIVED_DESCRIPTIVE"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"scope": None}, "no scope"),
        (
            {"scope": {"mode": "FULL_SNAPSHOT", "key": "WUG", "completeness": "PARTIAL"}},
            "contradicts",
        ),
        (
            {
                "scope": {
                    "mode": "PARTIAL_INCREMENTAL",
                    "key": "X",
                    "completeness": "COMPLETE_FOR_SCOPE",
                }
            },
            "contradicts",
        ),
        ({"scope": {"mode": "SOMETIMES", "key": "WUG", "completeness": "PARTIAL"}}, "scope.mode"),
        (
            {"scope": {"mode": "FULL_SNAPSHOT", "key": "", "completeness": "COMPLETE_FOR_SCOPE"}},
            "scope.key",
        ),
        ({"role_origin": "GUESS"}, "role_origin"),
        ({"schema": "studio-roles-9"}, "unknown schema"),
        ({"fetched_at": ""}, "fetched_at"),
        ({"roles": {"time_travel": [FOREST]}}, "unknown role"),
        ({"roles": {"ramp": FOREST}}, "not a list"),
        ({"roles": {"ramp": ["card:project:0001"]}}, "not an oracle id"),
        ({"roles": {"ramp": ["Sol Ring"]}}, "not an oracle id"),
        ({"roles": {"ramp": [FOREST, FOREST]}}, "twice"),
        ({"roles": {"ramp": [7]}}, "not an oracle id"),
        ({"tags": {}}, "no original tag"),
        ({"tags": None}, "needs the original tag"),
    ],
)
def test_unclear_files_are_refused_and_nothing_changes(
    studio: StudioStore, tmp_path: Path, change: dict[str, object], message: str
) -> None:
    good = json.loads(_file(tmp_path, "good.json", {"ramp": [FOREST]}).read_text(encoding="utf-8"))
    roles.import_roles(studio, tmp_path / "good.json")
    before = _dump(studio)
    payload = {**good, **change}
    payload = {key: value for key, value in payload.items() if value is not None}
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        roles.import_roles(studio, bad, allow_scope_replace=True)
    assert _dump(studio) == before


def test_other_kinds_of_unclear_files(studio: StudioStore, tmp_path: Path) -> None:
    before = _dump(studio)
    unscoped = tmp_path / "unscoped.json"
    unscoped.write_text(json.dumps({"fetched_at": "x", "roles": {"ramp": [FOREST]}}))
    with pytest.raises(ValueError, match="not read as a full snapshot"):
        roles.import_roles(studio, unscoped)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(ValueError, match="not valid JSON"):
        roles.import_roles(studio, broken)
    review_with_tags = _file(
        tmp_path, "r.json", {"ramp": [FOREST]}, origin=roles.ORIGIN_ORACLE_TEXT,
        mode=roles.PARTIAL_INCREMENTAL, key="R", tags={"ramp": "ramp"},
    )  # fmt: skip
    with pytest.raises(ValueError, match="carries no tagger tags"):
        roles.import_roles(studio, review_with_tags)
    crosswalk = _file(
        tmp_path, "x.json", {"ramp": [FOREST]}, origin=roles.ORIGIN_CROSSWALK,
        mode=roles.PARTIAL_INCREMENTAL, key="X", crosswalk_version="",
    )  # fmt: skip
    with pytest.raises(ValueError, match="crosswalk_version"):
        roles.import_roles(studio, crosswalk)
    assert _dump(studio) == before


def test_an_error_in_the_middle_rolls_everything_back(
    studio: StudioStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roles.import_roles(studio, _file(tmp_path, "one.json", {"ramp": [FOREST]}))
    before = _dump(studio)

    def broken(db: object) -> None:
        raise RuntimeError("the disk went away")

    monkeypatch.setattr(roles, "rebuild_corpus_deck_role", broken)
    with pytest.raises(RuntimeError, match="disk"):
        roles.import_roles(studio, _file(tmp_path, "two.json", {"removal": [RAT]}, key="G"))
    assert _dump(studio) == before
    assert not studio.connection.in_transaction  # no half-open transaction is left behind


def test_rows_from_before_claims_are_kept_and_later_superseded(
    studio: StudioStore, tmp_path: Path
) -> None:
    source = studio.register_source(
        data_class=roles.DataClass.ORIGINAL_SOURCE, title="old.json", sha256="ab" * 32
    )
    studio.connection.executemany(
        "INSERT INTO card_role(oracle_id, role, source_id) VALUES (?, ?, ?)",
        [(FOREST, "ramp", source), (RAT, "removal", source), ("oracle-other", "tutor", source)],
    )
    studio.connection.commit()
    partial = _file(
        tmp_path, "p.json", {"ramp": [FILLER]}, origin=roles.ORIGIN_ORACLE_TEXT,
        mode=roles.PARTIAL_INCREMENTAL, key="R",
    )  # fmt: skip
    report = roles.import_roles(studio, partial)
    assert _pairs(studio) == {
        (FOREST, "ramp"), (RAT, "removal"), ("oracle-other", "tutor"), (FILLER, "ramp"),
    }  # fmt: skip
    assert report["claims_by_origin"] == {roles.LEGACY_ORIGIN: 3, roles.ORIGIN_ORACLE_TEXT: 1}
    full = _file(tmp_path, "full.json", {"ramp": [FOREST], "removal": [], "tutor": []}, key="WUG")
    report = roles.import_roles(studio, full)
    assert report["legacy_claims_superseded"] == 1  # (forest, ramp) now has a tagger claim
    assert report["legacy_claims_left_in_these_roles"] == 2  # cannot be told apart: kept
    assert _pairs(studio) == {
        (FOREST, "ramp"), (RAT, "removal"), ("oracle-other", "tutor"), (FILLER, "ramp"),
    }  # fmt: skip


def test_the_file_of_the_older_fetch_is_read_as_a_full_snapshot_of_its_identity(
    studio: StudioStore, tmp_path: Path
) -> None:
    old = tmp_path / "old_fetch.json"
    old_payload = {
        "source": "Scryfall tagger (otag), public card search",
        "fetched_at": "2026-11-10T00:00:00Z",
        "identity": "GWU",
        "tags": {"ramp": "ramp", "removal": "removal"},
        "roles": {"ramp": [FOREST], "removal": [RAT]},
    }
    old.write_text(json.dumps(old_payload), encoding="utf-8")
    parsed = roles.read_role_file(old)
    assert (parsed.origin, parsed.mode, parsed.scope_key) == (
        roles.ORIGIN_TAGGER, roles.FULL_SNAPSHOT, "WUG",
    )  # fmt: skip
    assert parsed.legacy_format
    assert roles.import_roles(studio, old)["legacy_file_format"] is True
    # a file that names fewer roles than tags is not a complete snapshot
    old_payload["roles"] = {"ramp": [FOREST]}
    old.write_text(json.dumps(old_payload), encoding="utf-8")
    with pytest.raises(ValueError, match="not a complete snapshot"):
        roles.read_role_file(old)


def test_role_counts_per_deck_follow_the_roles_exactly_once(
    studio: StudioStore, tmp_path: Path
) -> None:
    roles.import_roles(studio, _file(tmp_path, "a.json", {"ramp": [FOREST]}))
    assert _deck_roles(studio) == {("d1", "ramp"): 30, ("d2", "ramp"): 36}
    roles.import_roles(
        studio,
        _file(tmp_path, "b.json", {"removal": [RAT]}, mode=roles.PARTIAL_INCREMENTAL, key="B"),
    )
    assert _deck_roles(studio) == {
        ("d1", "ramp"): 30,
        ("d2", "ramp"): 36,
        ("d1", "removal"): 1,
        ("d3", "removal"): 1,
        ("d4", "removal"): 1,
    }
    integrity = studio.connection.execute("PRAGMA integrity_check").fetchall()
    assert [tuple(row) for row in integrity] == [("ok",)]
    assert studio.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_role_labels_are_compared_without_assuming_equality() -> None:
    labels = ["ramp", "mana-rock", "sweeper", "hate-graveyard", "draw"]
    report = roles.check_role_labels(labels)
    assert report["search_alias"] == ["board_wipe", "graveyard_hate"]
    assert report["canonical"] == ["ramp", "mana_rock", "card_draw"]
    assert "tutor" in report["unknown"]
    # without the canonical label there is no alias to point to
    assert "board_wipe" in roles.check_role_labels(["ramp"])["unknown"]


def test_the_fetch_writes_scope_origin_and_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(roles, "_page", lambda address: {"data": [{"oracle_id": "a"}]})
    written = roles.fetch_role_file("gwu", tmp_path / "roles.json", pause=0)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema"] == roles.ROLES_SCHEMA
    assert payload["role_origin"] == roles.ORIGIN_TAGGER
    assert payload["identity"] == "WUG"  # fixed color order
    assert payload["scope"] == {
        "mode": "FULL_SNAPSHOT", "key": "WUG", "completeness": "COMPLETE_FOR_SCOPE",
    }  # fmt: skip
    assert payload["tag_aliases"] == roles.SEARCH_ALIASES
    parsed = roles.read_role_file(written)
    assert parsed.scope_key == "WUG"
    assert not parsed.legacy_format


def test_the_command_line_needs_the_flag_to_remove_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = str(tmp_path / "data")
    first = _file(tmp_path, "one.json", {"ramp": [FOREST, FILLER]})
    second = _file(tmp_path, "two.json", {"ramp": [FOREST]})
    assert main(["--data", data, "import-roles", str(first)]) == 0
    assert json.loads(capsys.readouterr().out)["claims_added"] == 2
    with pytest.raises(ValueError, match="--replace-scope"):
        main(["--data", data, "import-roles", str(second)])
    assert main(["--data", data, "import-roles", str(second), "--replace-scope"]) == 0
    assert json.loads(capsys.readouterr().out)["claims_removed"] == 1
    labels = tmp_path / "labels.txt"
    labels.write_text("ramp\nsweeper\n", encoding="utf-8")
    assert main(["check-role-labels", str(labels)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["search_alias"] == ["board_wipe"]
