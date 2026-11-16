"""Static guards for the Studio pages: no literal 'null' children, no price wording, labelled inputs."""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"
PRICE_WORDS = re.compile(r"\b(preis\w*|kaufen|zukauf|price\w*|buy)\b|€", re.IGNORECASE)


def _files(pattern: str) -> list[Path]:
    found = sorted(STATIC.glob(pattern))
    assert found, pattern
    return found


def test_replace_children_never_receives_a_bare_null() -> None:
    # replaceChildren turns a null argument into the text "null"; call sites must spread
    # through the kids() filter whenever an argument can be null.
    source = (STATIC / "decks.js").read_text(encoding="utf-8")
    for call in re.finditer(r"replaceChildren\((?!\.\.\.)[^;]*?\bnull\b", source, re.DOTALL):
        raise AssertionError(f"replaceChildren with a null child: {call.group(0)[:80]!r}")


def test_no_price_wording_in_pages_and_scripts() -> None:
    for path in [*_files("*.html"), *_files("*.js")]:
        text = path.read_text(encoding="utf-8")
        hits = PRICE_WORDS.findall(text)
        assert not hits, f"{path.name}: {hits}"


def test_every_text_input_and_select_has_a_name() -> None:
    tag = re.compile(r"<(input|select|textarea)\b([^>]*)>", re.IGNORECASE)
    unlabeled: list[str] = []
    for path in _files("*.html"):
        text = path.read_text(encoding="utf-8")
        for match in tag.finditer(text):
            attrs = match.group(2)
            if re.search(r'type="(checkbox|radio|hidden|button)"', attrs):
                continue
            ident = re.search(r'id="([^"]+)"', attrs)
            labelled = "aria-label" in attrs or "title=" in attrs
            if not labelled:
                before = text[: match.start()]
                labelled = before.rfind("<label") > before.rfind(
                    "</label>"
                )  # wrapped in an open <label>
            if not labelled:
                unlabeled.append(f"{path.name}:{ident.group(1) if ident else match.group(1)}")
    assert unlabeled == []
