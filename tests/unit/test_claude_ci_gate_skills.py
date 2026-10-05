from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / ".claude" / "skills"

NEW_SKILLS = (
    "post-patch-validation",
    "differential-review",
    "verification-before-completion",
    "agentic-actions-auditor",
    "systematic-debugging",
    "commander-quality-gate",
    "sharp-edges",
    "fp-check",
    "receiving-code-review",
)

# Files intentionally retained byte-for-byte from their pinned upstream blobs.
EXACT_GIT_BLOBS = {
    "post-patch-validation/references/evidence-model.md": "341229a0788b7fad6e93d85303a619af08ece5c7",
    "post-patch-validation/scripts/post_patch_validation.py": "025667053e4860add7f41fe889ffa2b966ffb77e",
    "post-patch-validation/scripts/pyproject.toml": "e38d3aaad7076a70b3866b05b56ed8f5bb5c457f",
    "differential-review/adversarial.md": "0176d374bc2d9d59f114b647cb21f0685bc7e9f3",
    "differential-review/methodology.md": "71d9dc0babf1417ee79ec8d5214ea690d0c2fe6b",
    "differential-review/patterns.md": "71078a725d986c90d014cceff0cc54414ad3b1a1",
    "differential-review/reporting.md": "cb5e37b4eab89c429bf6f968d3e3482adaa39faa",
    "differential-review/agents/adversarial-modeler.md": "b7c1dbace7a07650d504e6d9765b6de193a844f0",
    "agentic-actions-auditor/SKILL.md": "efdeacdf470d5bd1d714ca231d6276f086214971",
    "agentic-actions-auditor/references/action-profiles.md": "8b6afc4920e4a71802764e72f3ec7f83f0e530ce",
    "agentic-actions-auditor/references/cross-file-resolution.md": "1ec95b5505f71def1c5f9895493bf87e719264c5",
    "agentic-actions-auditor/references/foundations.md": "a8a7397da09643dce6211739602549bf247fa414",
    "agentic-actions-auditor/references/vector-a-env-var-intermediary.md": "77388fc7ae219976adc2cb4ca5719f6664db3ef5",
    "agentic-actions-auditor/references/vector-b-direct-expression-injection.md": "75e6a7fd961a74937d6e4bdf3b3a611978a8b5dc",
    "agentic-actions-auditor/references/vector-c-cli-data-fetch.md": "630d9e4f14d22fb7adf810176d8436546333f72b",
    "agentic-actions-auditor/references/vector-d-pr-target-checkout.md": "659d2f60fc9b9b7b2a847e625b5307308e281d86",
    "agentic-actions-auditor/references/vector-e-error-log-injection.md": "681dd7ae2485c031fd5210cacd42e6b5562cb109",
    "agentic-actions-auditor/references/vector-f-subshell-expansion.md": "5ca7365843780b0d50cecd22154efcfa99c4c9d8",
    "agentic-actions-auditor/references/vector-g-eval-of-ai-output.md": "7e2bbfb63819ac5a25a61695fc594493a17207cf",
    "agentic-actions-auditor/references/vector-h-dangerous-sandbox-configs.md": "e28e4ace81fb01346a8984100f53c2dac7d2b9e6",
    "agentic-actions-auditor/references/vector-i-wildcard-allowlists.md": "881ee57e23a8bb6dee9b00b53838d727a8e3abb0",
    "systematic-debugging/condition-based-waiting.md": "70994f777c586f7d4c43033aac34c7cf0da6688b",
    "systematic-debugging/defense-in-depth.md": "e2483354dc2b62478a2624e34ca18bc0efe887b2",
    "systematic-debugging/root-cause-tracing.md": "12ef5222e24e19ab92172b82b69ef1b0c30d9bfa",
    "systematic-debugging/find-polluter.sh": "985f5d08ccf8a3f2d40739cfcaf4413bb24bf1cb",
    "systematic-debugging/condition-based-waiting-example.ts": "703a06b653160d060bbf46ab5c6e0cd7446bd592",
    "commander-quality-gate/references/upstream-gate-SKILL.md": "7a07cb9ea19d94f3db30533243c44b841a519c96",
    "fp-check/SKILL.md": "b7e7278cbae101f948f39890e5dcc088248d789d",
    "fp-check/references/bug-class-verification.md": "3eb666d646b4c6071b82012d4911ba0650665078",
    "fp-check/references/deep-verification.md": "1b2499d03627b0d8a025f115f2137292766abdf7",
    "fp-check/references/evidence-templates.md": "c0227e56238eb856d9d4efc6d2bde6c85ebd3339",
    "fp-check/references/false-positive-patterns.md": "7ad448441b882e1f801f31550f9528f7ff7d9310",
    "fp-check/references/gate-reviews.md": "b9dd2f4eaf118ca5206ef94ecf12c6b826d4fded",
    "fp-check/references/standard-verification.md": "c9e5b901ad4b3008950c31f24806f7bacdbf6cfe",
    "receiving-code-review/SKILL.md": "950da7b74bf6dbed6b8726d12ddadd65a9f5fda7",
    "sharp-edges/SKILL.md": "44ea7876d7e5f3b5599c64684eb1a02c1500cb7a",
    "licenses/trailofbits-skills-CC-BY-SA-4.0.txt": "3b7b82d0da2db857eda1a798dbd908ea136f07b5",
    "licenses/superpowers-MIT.txt": "abf0390320aa14406af7a520b9b0739fdda9bf08",
    "licenses/claude-gate-skill-MIT.txt": "687b32c3e6fc995db0f5929fc1780c0bd5c8c507",
}

# Whole directories retained byte-for-byte: sha256 over sorted "name blobsha" lines.
# (A digest per directory avoids path words such as "auth" sitting beside a hash.)
EXACT_DIRECTORY_DIGESTS = {
    "sharp-edges/references": "1ba1df5c747ef33d9a4493c4e15ee4636f8b1995060b000c9fefcc8082824a42",
}

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n")
    _, raw, _ = text.split("---", 2)
    parsed = yaml.safe_load(raw)
    assert isinstance(parsed, dict)
    return parsed


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def test_new_skill_frontmatter_and_names() -> None:
    for skill in NEW_SKILLS:
        path = SKILLS_ROOT / skill / "SKILL.md"
        assert path.is_file(), skill
        meta = _frontmatter(path.read_text(encoding="utf-8"))
        assert meta["name"] == skill
        description = meta.get("description")
        assert isinstance(description, str) and description.strip()
        assert len(description) <= 1024


def test_new_skill_markdown_links_resolve() -> None:
    for skill in NEW_SKILLS:
        skill_dir = SKILLS_ROOT / skill
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        for raw in LINK_RE.findall(text):
            target = raw.split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "#")):
                continue
            if target.startswith("{baseDir}/"):
                resolved = skill_dir / target.removeprefix("{baseDir}/")
            else:
                resolved = skill_dir / target
            assert resolved.exists(), f"{skill}: dead link {raw} -> {resolved}"


def test_exact_upstream_blobs_have_not_drifted() -> None:
    for relative, expected in EXACT_GIT_BLOBS.items():
        path = SKILLS_ROOT / relative
        assert path.is_file(), relative
        assert _git_blob_sha(path.read_bytes()) == expected, relative


def _directory_digest(directory: Path) -> str:
    lines = "".join(
        f"{path.name} {_git_blob_sha(path.read_bytes())}\n"
        for path in sorted(directory.iterdir())
        if path.is_file()
    )
    return hashlib.sha256(lines.encode()).hexdigest()


def test_exact_upstream_directories_have_not_drifted() -> None:
    for relative, expected in EXACT_DIRECTORY_DIGESTS.items():
        directory = SKILLS_ROOT / relative
        assert directory.is_dir(), relative
        assert _directory_digest(directory) == expected, relative


def test_provenance_and_licenses_present() -> None:
    provenance = (SKILLS_ROOT / "CI_GATE_SKILLS_PROVENANCE.md").read_text(encoding="utf-8")
    for pin in (
        "82fe8226252622fa807643bdca1710901198553a",
        "5fd93af4cd0c623e020d0cc7e9ce178b4ac1f70f",
        "6d352f7d06b83e98102847f3ef91da5061c262de",
        "8ca22dba9a94f28898bbce59f2537ff4d87c747d",
    ):
        assert pin in provenance
    assert "AGENTS.md" in provenance
    assert "CC BY-SA 4.0" in provenance
    assert "MIT" in provenance


def test_post_patch_runner_is_valid_python() -> None:
    runner = SKILLS_ROOT / "post-patch-validation" / "scripts" / "post_patch_validation.py"
    compile(runner.read_text(encoding="utf-8"), str(runner), "exec")
