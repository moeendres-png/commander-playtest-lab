"""Static guards for the one-click starter: the thin wrappers and the module's own text.

The Windows wrappers cannot run here; these checks bind what they may do. A PowerShell parse
check runs only where ``pwsh`` is installed and is otherwise skipped (NOT_RUN, never PASS).
"""

from __future__ import annotations

import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from commander_lab.studio import oneclick

ROOT = Path(__file__).resolve().parents[2]
CMD = ROOT / "Studio starten.cmd"
PS1 = ROOT / "scripts" / "studio_oneclick.ps1"
SH = ROOT / "scripts" / "studio_oneclick.sh"
MODULE = ROOT / "src" / "commander_lab" / "studio" / "oneclick.py"
DOC = ROOT / "docs" / "STUDIO_START_EINFACH.md"
WRAPPERS = (CMD, PS1, SH)

# Destructive, network or secret operations no wrapper may contain.
FORBIDDEN_IN_WRAPPERS = re.compile(
    r"reset\s+--hard|clean\s+-[a-z]*[fdx]|\bstash\b|Remove-Item|\brm\s+-|\brmdir\b|\bdel\s+/|"
    r"Invoke-Expression|\biex\b|Invoke-WebRequest|Invoke-RestMethod|DownloadString|DownloadFile|"
    r"\bcurl\b|\bwget\b|Start-BitsTransfer|auth\s+token|GH_TOKEN|GITHUB_TOKEN|cardmarket|"
    r"preis|price|\bgh\b|git\s+pull|0\.0\.0\.0",
    re.IGNORECASE,
)
# The module may run git pull and gh, but never these.
FORBIDDEN_IN_MODULE = re.compile(
    r"reset\s*\"?,?\s*\"?--hard|\"reset\"|\"stash\"|\"clean\"|\"auth\",\s*\"token\"|"
    r"GH_TOKEN|GITHUB_TOKEN|cardmarket|preisf|price|0\.0\.0\.0|rmtree|shell=True|"
    r"\"--force\"|\(\s*\"push\"",
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", WRAPPERS, ids=lambda p: p.name)
def test_wrappers_are_ascii_and_thin(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.isascii(), f"{path.name}: Windows PowerShell 5.1 and cmd need ASCII"
    assert len(text.splitlines()) <= 70, f"{path.name} must stay a thin wrapper"
    hits = FORBIDDEN_IN_WRAPPERS.findall(text)
    assert hits == [], f"{path.name}: {hits}"


def test_wrappers_call_the_tested_python_module() -> None:
    assert "scripts\\studio_oneclick.ps1" in CMD.read_text(encoding="utf-8")
    for path in (PS1, SH):
        assert "-m commander_lab.studio.oneclick" in path.read_text(encoding="utf-8")


def test_the_cmd_file_pauses_on_error_and_has_crlf_on_checkout() -> None:
    text = CMD.read_text(encoding="utf-8")
    assert "pause" in text and "ExecutionPolicy Bypass" in text and "-File" in text
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert re.search(r"^\*\.cmd\s+text\s+eol=crlf\s*$", attributes, re.MULTILINE)


def test_the_python_install_offer_in_the_wrapper_waits_for_a_yes() -> None:
    text = PS1.read_text(encoding="utf-8")
    before_install = text[: text.index("& winget install")]
    assert "Read-Host" in before_install
    assert "-match '^(j|ja|y|yes)$'" in before_install


def test_the_shell_wrapper_parses() -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("NOT_RUN: bash is not installed")
    done = subprocess.run([bash, "-n", str(SH)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr


def test_the_powershell_wrapper_parses() -> None:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh is None:
        pytest.skip("NOT_RUN: no PowerShell here; the Owner-PC run is the first real check")
    script = (
        "$e = $null; [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{PS1}', [ref]$null, [ref]$e) | Out-Null; if ($e.Count) {{ exit 1 }}"
    )
    done = subprocess.run([pwsh, "-NoProfile", "-Command", script], check=False)
    assert done.returncode == 0


def test_the_module_text_has_no_destructive_secret_or_price_operation() -> None:
    hits = FORBIDDEN_IN_MODULE.findall(MODULE.read_text(encoding="utf-8"))
    assert hits == [], hits


def test_the_only_http_target_of_the_module_is_localhost() -> None:
    text = MODULE.read_text(encoding="utf-8")
    urls = set(re.findall(r"https?://[^\s\"'{}/]+", text))
    assert urls == {"http://127.0.0.1:"}, urls


def test_the_module_loads_only_the_standard_library_at_import() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    top = [
        node
        for node in tree.body
        if isinstance(node, ast.Import | ast.ImportFrom)
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]
    names = {
        (alias.name if isinstance(node, ast.Import) else str(node.module)).split(".")[0]
        for node in top
        for alias in node.names
    }
    assert names, "the module imports something"
    assert names <= set(sys.stdlib_module_names), names - set(sys.stdlib_module_names)
    every = [n for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom)]
    assert not any(
        "commander_lab" in (getattr(n, "module", None) or "")
        or any("commander_lab" in a.name for a in n.names)
        for n in every
    )


def test_the_module_imports_without_site_packages() -> None:
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    done = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import commander_lab.studio.oneclick as m; print(m.SCHRITTE)",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "8"


def _doc_commands() -> list[list[str]]:
    text = DOC.read_text(encoding="utf-8")
    found: list[list[str]] = []
    for line in re.findall(
        r"(?:studio_oneclick\.(?:ps1|sh)|Studio starten\.cmd\")((?: --?[\w-]+(?: [^\s`-][^\s`]*)?)*)",
        text,
    ):
        found.append(shlex.split(line))
    for flag in re.findall(r"`(--[\w-]+(?: [^`<]+| <[^>]+>)?)`", text):
        found.append([t if not t.startswith("<") else "X" for t in shlex.split(flag)])
    return found


def test_every_switch_in_the_owner_page_exists() -> None:
    commands = _doc_commands()
    assert any("--nur-pruefen" in tokens for tokens in commands)
    for tokens in commands:
        oneclick.parser().parse_args(tokens)
