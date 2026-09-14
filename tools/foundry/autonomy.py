"""Canonical Foundry autonomous-workstream runtime contract (WS198).

Pure stdlib logic for machine-checkable autonomy semantics. No I/O, no Git,
no network, no telemetry access: callers (``state.py``, ``context_capsule.py``,
``launcher.py``, tests) supply plain mappings plus optional ancestry/spec
callbacks. Static prose lives in versioned instruction files (``AGENTS.md``,
agent definitions, skills, ``docs/foundry-execution/AUTONOMY.md``); this
module carries only values, vocabularies, and fail-closed checks so dynamic
prompts never duplicate static contract text.

Design (XHIGH-adjudicated, smallest coherent set):

- ``TECHNICAL_DECISION_AUTHORITY = AUTONOMOUS_WITHIN_CONTRACT`` is the
  default; genuine Rules/evidence-policy/architecture/scope/provider/freeze
  questions stay ``AUTHORITY_GATE`` for Sol High.
- Semantic Completion: continue through remediable in-scope failures until
  the authorized scope is COMPLETE or a genuine terminal gate exists.
- Conditional continuation past ``exact_next_action`` is bounded by
  ``continuation_policy`` (default ``EXACT_NEXT_ACTION_ONLY``).
- Early ``COMPLETE`` claims are checked by ``check_completion_readiness``
  (advisory + credit-boundary signal; never retroactive invalidation).
- Successor planning is plan-only: pointer in state + separate validated
  artifact; execution always requires a fresh Coordinator/operator launch.
- Session rotation is advisory and threshold-free (WS78B structural guidance
  only; token/cache figures remain ``UNKNOWN`` without an ``opencode
  export`` aggregate).
"""

from __future__ import annotations

import re
from collections.abc import Callable

# --------------------------------------------------------------------------
# Canonical vocabularies (single source; schema/state/capsule/tests import
# these instead of re-declaring strings).
# --------------------------------------------------------------------------

TECHNICAL_DECISION_AUTHORITY_DEFAULT = "AUTONOMOUS_WITHIN_CONTRACT"

CONTINUATION_POLICIES = ("EXACT_NEXT_ACTION_ONLY", "BOUNDED_IN_SCOPE")
CONTINUATION_POLICY_DEFAULT = "EXACT_NEXT_ACTION_ONLY"

SUCCESSOR_STATUSES = ("NONE", "PROPOSED", "AUTHORIZED")
SUCCESSOR_STATUS_DEFAULT = "NONE"

ROTATION_RECOMMENDATIONS = ("NO_ROTATION", "REVIEW_PROMPT", "ROTATE_TO_FRESH_CONTINUATION")
ROTATION_DEFAULT = "NO_ROTATION"

RECOMMENDED_LANES = ("high", "xhigh")

EXECUTABILITY_CLASSES = ("IMMEDIATE", "DEPENDENCY_BLOCKED", "COORDINATOR_DECISION")

#: Maximum default recommendation count for terminal successor planning.
MAX_SUCCESSOR_RECOMMENDATIONS = 3

#: Compact-capsule text budget (bytes). Values-only additions must fit.
CAPSULE_BUDGET_BYTES = 4096

#: Canonical TUI work directive (mirrors ``.opencode/commands/work.md``).
WORK_DIRECTIVE = (
    "Execute/resume the active workstream through Semantic Completion using this capsule. "
    "Read the full state, contract, and evidence only when the capsule is insufficient "
    "for the next action."
)

#: Canonical headless extras: the same directive, supplied as caller prompt
#: text for ``opencode run --auto`` (documented in AUTONOMY.md; never injected
#: as launcher config, so TUI/headless stay semantically identical without
#: duplicating policy prose into dynamic prompts).
#: Headless prompt syntax is ``opencode run [message..]`` (pinned 1.18.30):
#: a bare message IS the prompt.
HEADLESS_EXTRAS = (
    "Derive the execution capsule via "
    "`python3 tools/foundry/context_capsule.py --state \"$FOUNDRY_STATE_PATH\"` "
    "and " + WORK_DIRECTIVE
)

#: Canonical TUI prompt injection (pinned 1.18.30: TUI syntax is
#: ``opencode [project]`` with ``--prompt`` carrying the initial message).
#: Child form (what the launcher execs): ``opencode --auto --prompt "<task>"``.
#: Launcher spelling (argparse passthrough): ``-- --prompt "<task>"``.
#: Bare positional text is NEVER prompt input for TUI: the CLI binds it to
#: the project path, fails instantly with ``Failed to change directory`` on
#: stderr, and STILL returns child exit 0 — an exit-0 false success in which
#: no agent task executed (WS92/WS93 shape, reproduced DIRECTLY_VERIFIED).
#: Post-hoc detection without heuristic stderr parsing is not reliable
#: (exit 0 is the CLI contract), so the launcher refuses the shape at
#: construction (``canonicalize_tui_extras``) and records ``ui_mode`` in
#: run telemetry for future audit joins.
TUI_PROMPT_CHILD_FORM = '--prompt "<task>"'
TUI_PROMPT_LAUNCHER_FORM = '-- --prompt "<task>"'

#: Stop conditions that must NOT voluntarily end a workstream (Semantic
#: Completion non-stop enumeration; normative prose lives in AUTONOMY.md).
SEMANTIC_COMPLETION_NONSTOP = (
    "first test failed",
    "one scenario passed",
    "first blocker found while independent in-scope work remains",
    "compilation succeeded",
    "initial requested artifact written",
    "obvious repair succeeded",
    "primary subgoal completed but required evidence/hardening remains",
)

#: Ordered in-scope capacity use after early primary success (AUTONOMY.md).
EARLY_COMPLETION_HARDENING_ORDER = (
    "impacted validation",
    "evidence completeness",
    "provenance and hash binding",
    "adversarial/negative controls required by contract",
    "final-diff semantic audit",
    "replay/resumability checks where relevant",
    "dependency/unblocking analysis",
    "successor planning",
)

#: Execution-ready successor specification: required machine-checkable fields.
SUCCESSOR_SPEC_REQUIRED_FIELDS = (
    "objective",
    "repository",
    "proposed_branch",
    "proposed_worktree",
    "source_lock_basis",
    "inputs",
    "ownership_surface",
    "dependencies",
    "in_scope",
    "out_of_scope",
    "hard_gates",
    "forbidden_shortcuts",
    "evidence_requirements",
    "recommended_lane",
    "stop_conditions",
    "rationale",
    "initial_prompt",
    "executability",
)

_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")

# Forbidden plan shapes: branch/worktree creation, remote mutation, provider
# switching. Matched case-insensitively against continuation/successor text.
_FORBIDDEN_PLAN_PATTERNS = (
    ("BRANCH_WORKTREE_CREATION_REFUSED", re.compile(r"worktree\s+add|checkout\s+-b|switch\s+-c", re.I)),
    ("REMOTE_MUTATION_REFUSED", re.compile(r"\bgit\s+push\b|\bgh\s+pr\s+create\b|\bgit\s+merge\b|\bgit\s+rebase\b", re.I)),
    ("PROVIDER_SWITCH_REFUSED", re.compile(r"--execution-provider|--model[ =]|-m\s+\S|--variant[ =]", re.I)),
)

# Telemetry-fabrication probe: numeric token/cache/cost claims. A match is a
# refusal unless the text carries export provenance (session_stats aggregate).
_TELEMETRY_PATTERN = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*(?:tokens?|cache[_ -]?(?:read|write|hit)?s?|turns?|USD|\$)\b"
    r"|\b(?:tokens?|cache[_ -]?(?:read|write|hit|savings?)|cost_usd)\b[^\n]*\d",
    re.I,
)
_EXPORT_PROVENANCE_PATTERN = re.compile(r"session_stats\.py|opencode\s+export|AUTOCAPTURED|NOT_RUN|UNKNOWN", re.I)


# --------------------------------------------------------------------------
# Defaults resolution (absent autonomy fields resolve conservatively).
# --------------------------------------------------------------------------

def autonomy_defaults(data: dict) -> dict:
    """Resolved autonomy values; absent fields yield conservative defaults."""
    successor = data.get("successor_plan") or {}
    rotation = data.get("rotation_guidance") or {}
    return {
        "technical_decision_authority": data.get("technical_decision_authority")
        or TECHNICAL_DECISION_AUTHORITY_DEFAULT,
        "continuation_policy": data.get("continuation_policy") or CONTINUATION_POLICY_DEFAULT,
        "successor_status": successor.get("status", SUCCESSOR_STATUS_DEFAULT)
        if isinstance(successor, dict)
        else SUCCESSOR_STATUS_DEFAULT,
        "rotation_recommendation": rotation.get("recommendation", ROTATION_DEFAULT)
        if isinstance(rotation, dict)
        else ROTATION_DEFAULT,
    }


def validate_autonomy(data: dict) -> list[str]:
    """Fail-closed validation for present autonomy fields.

    Absent fields are valid (conservative defaults apply at read). Malformed
    present values are refused, never coerced.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["state file must be a mapping"]
    policy = data.get("continuation_policy")
    if policy is not None and policy not in CONTINUATION_POLICIES:
        errors.append(
            f"bad continuation_policy: {policy!r} (want one of {list(CONTINUATION_POLICIES)})"
        )
    successor = data.get("successor_plan")
    if successor is not None:
        if not isinstance(successor, dict):
            errors.append("successor_plan must be an object")
        else:
            status = successor.get("status", SUCCESSOR_STATUS_DEFAULT)
            if status not in SUCCESSOR_STATUSES:
                errors.append(
                    f"bad successor_plan.status: {status!r} "
                    f"(want one of {list(SUCCESSOR_STATUSES)})"
                )
            preauthorized = successor.get("preauthorized", False)
            if "preauthorized" in successor and not isinstance(preauthorized, bool):
                errors.append("successor_plan.preauthorized must be a boolean")
            if status == "AUTHORIZED":
                if not successor.get("spec_path"):
                    errors.append("successor_plan AUTHORIZED requires spec_path")
                if not successor.get("spec_sha256"):
                    errors.append("successor_plan AUTHORIZED requires spec_sha256")
                if preauthorized is not True:
                    errors.append(
                        "successor_plan AUTHORIZED requires preauthorized: true "
                        "(SUCCESSOR_NOT_AUTHORIZED otherwise)"
                    )
    rotation = data.get("rotation_guidance")
    if rotation is not None:
        if not isinstance(rotation, dict):
            errors.append("rotation_guidance must be an object")
        else:
            rec = rotation.get("recommendation", ROTATION_DEFAULT)
            if rec not in ROTATION_RECOMMENDATIONS:
                errors.append(
                    f"bad rotation_guidance.recommendation: {rec!r} "
                    f"(want one of {list(ROTATION_RECOMMENDATIONS)})"
                )
            if "export_verified" in rotation and not isinstance(
                rotation["export_verified"], bool
            ):
                errors.append("rotation_guidance.export_verified must be a boolean")
    return errors


# --------------------------------------------------------------------------
# Completion readiness (advisory + credit-boundary signal).
# --------------------------------------------------------------------------

def check_completion_readiness(
    data: dict,
    live_head: str | None = None,
    is_ancestor: Callable[[str, str], bool] | None = None,
) -> tuple[bool, list[str]]:
    """Advisory readiness for a ``COMPLETE`` claim.

    Never invalidates legacy states: non-COMPLETE statuses are trivially
    ready (no claim made). Ancestry is checked only when both ``live_head``
    and ``is_ancestor`` are supplied; otherwise ancestry stays unchecked and
    is reported as such (never assumed).
    """
    if data.get("status") != "COMPLETE":
        return True, [f"no COMPLETE claim (status={data.get('status')})"]
    reasons: list[str] = []
    validated = data.get("validated_head")
    if validated is None:
        reasons.append("COMPLETION_NOT_READY: validated_head is null (no validation credit)")
    remaining = data.get("remaining_scope") or []
    if remaining:
        reasons.append(
            f"COMPLETION_NOT_READY: remaining_scope has {len(remaining)} open item(s)"
        )
    failed = data.get("failed_gates") or []
    if failed:
        reasons.append(f"COMPLETION_NOT_READY: failed_gates has {len(failed)} open gate(s)")
    if validated is not None and live_head and is_ancestor is not None:
        base = str(data.get("audit_base_sha", ""))
        if base and not is_ancestor(base, str(validated)):
            reasons.append("COMPLETION_NOT_READY: VALIDATED_OUTSIDE_LOCK")
        if not is_ancestor(str(validated), live_head):
            reasons.append("COMPLETION_NOT_READY: VALIDATED_REWRITTEN")
    elif validated is not None:
        reasons.append("ancestry unchecked here (verify via state.py --workdir)")
    if reasons and all(r.startswith("COMPLETION_NOT_READY") for r in reasons):
        return False, reasons
    if any(r.startswith("COMPLETION_NOT_READY") for r in reasons):
        return False, reasons
    return True, reasons or ["COMPLETE claim is backed by validation credit"]


# --------------------------------------------------------------------------
# Bounded conditional continuation.
# --------------------------------------------------------------------------

def scan_forbidden_plan_shapes(text: str) -> list[str]:
    """Refusal codes for plan text that would escape the workstream surface."""
    hits: list[str] = []
    for code, pattern in _FORBIDDEN_PLAN_PATTERNS:
        if pattern.search(text or ""):
            hits.append(code)
    return hits


def continuation_decision(data: dict, item: str) -> tuple[str, str]:
    """Verdict for advancing to ``item`` beyond ``exact_next_action``.

    - The binding ``exact_next_action`` itself always PROCEEDs.
    - Under ``EXACT_NEXT_ACTION_ONLY`` (default) anything else stops.
    - Under ``BOUNDED_IN_SCOPE`` each item must be a declared remainder,
      inside ``in_scope``/outside ``out_of_scope``, and free of forbidden
      plan shapes. Authority-gated lines stop that line only
      (``AUTHORITY_GATE_STOP`` is returned when the item matches a recorded
      authority gate verbatim; otherwise the caller must still honor gates).
    """
    item = item or ""
    if item == (data.get("exact_next_action") or ""):
        return "PROCEED", "item is the binding exact_next_action"
    forbidden = scan_forbidden_plan_shapes(item)
    if forbidden:
        return "SCOPE_REFUSED", f"forbidden plan shape: {forbidden[0]}"
    policy = data.get("continuation_policy") or CONTINUATION_POLICY_DEFAULT
    if policy != "BOUNDED_IN_SCOPE":
        return "EXACT_ACTION_ONLY", (
            f"continuation_policy={policy}: advance only via the binding "
            "exact_next_action (checkpoint, then stop)"
        )
    remaining = data.get("remaining_scope") or []
    if item not in remaining:
        return "SCOPE_REFUSED", "item is not a declared remaining_scope entry"
    if item in (data.get("out_of_scope") or []):
        return "SCOPE_REFUSED", "item is explicitly out_of_scope"
    for gate in data.get("authority_gates") or []:
        if isinstance(gate, str) and gate and gate == item:
            return "AUTHORITY_GATE_STOP", "item is a recorded authority gate question"
    return "PROCEED", "BOUNDED_IN_SCOPE: declared remainder inside scope bounds"


# --------------------------------------------------------------------------
# Successor planning (plan-only; execution always needs a fresh launch).
# --------------------------------------------------------------------------

def validate_successor_spec(spec: dict) -> list[str]:
    """Structural check for one execution-ready successor specification."""
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["successor spec must be a mapping"]
    for field in SUCCESSOR_SPEC_REQUIRED_FIELDS:
        value = spec.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"successor spec missing required field: {field}")
    lane = spec.get("recommended_lane")
    if lane is not None and lane not in RECOMMENDED_LANES:
        errors.append(f"bad recommended_lane: {lane!r} (want high|xhigh)")
    executability = spec.get("executability")
    if executability is not None and executability not in EXECUTABILITY_CLASSES:
        errors.append(
            f"bad executability: {executability!r} (want one of {list(EXECUTABILITY_CLASSES)})"
        )
    # No fabricated future SHAs: a 40-hex SHA is accepted only with provenance
    # naming the existing commit it was read from.
    sha_provenance = str(spec.get("sha_provenance") or "")
    for field in ("source_lock_basis", "rationale", "initial_prompt"):
        value = spec.get(field)
        if isinstance(value, str) and _SHA_RE.search(value) and not sha_provenance.strip():
            errors.append(
                f"successor spec field {field!r} cites a 40-hex SHA without "
                "sha_provenance (future SHAs must not be fabricated)"
            )
    return errors


def validate_successor_set(specs: list) -> list[str]:
    """At most MAX_SUCCESSOR_RECOMMENDATIONS execution-ready proposals."""
    errors: list[str] = []
    if not isinstance(specs, list):
        return ["successor set must be a list"]
    if len(specs) > MAX_SUCCESSOR_RECOMMENDATIONS:
        errors.append(
            f"successor set has {len(specs)} proposals "
            f"(maximum default: {MAX_SUCCESSOR_RECOMMENDATIONS})"
        )
    for index, spec in enumerate(specs):
        for error in validate_successor_spec(spec if isinstance(spec, dict) else {}):
            errors.append(f"successor[{index}]: {error}")
    return errors


def check_successor(data: dict, spec: dict | None = None) -> tuple[str, list[str]]:
    """Successor-plan pointer check.

    Returns ``(status, errors)``. ``PROPOSED`` requires the spec artifact;
    ``AUTHORIZED`` additionally requires ``preauthorized: true`` plus an
    authorization record naming the Coordinator/operator instruction (never
    inferred from ``AUTONOMOUS_WITHIN_CONTRACT``). Execution itself is never
    performed here: even ``AUTHORIZED`` only permits a fresh explicit launch.
    """
    pointer = data.get("successor_plan")
    if pointer is None:
        return SUCCESSOR_STATUS_DEFAULT, []
    if not isinstance(pointer, dict):
        return SUCCESSOR_STATUS_DEFAULT, ["successor_plan must be an object"]
    status = pointer.get("status", SUCCESSOR_STATUS_DEFAULT)
    if status == "NONE":
        return status, []
    errors: list[str] = []
    if spec is None:
        errors.append(f"successor_plan {status} without a spec artifact")
        return status, errors
    errors.extend(validate_successor_spec(spec))
    if status == "AUTHORIZED":
        if pointer.get("preauthorized") is not True:
            errors.append("SUCCESSOR_NOT_AUTHORIZED: AUTHORIZED requires preauthorized: true")
        authorization = spec.get("authorization") or pointer.get("authorization")
        if not (isinstance(authorization, str) and authorization.strip()):
            errors.append(
                "SUCCESSOR_NOT_AUTHORIZED: AUTHORIZED requires an authorization "
                "record naming the Coordinator/operator instruction"
            )
    if status not in SUCCESSOR_STATUSES:
        errors.append(f"bad successor_plan.status: {status!r}")
    return status, errors


# --------------------------------------------------------------------------
# Session rotation (advisory, threshold-free, evidence-honest).
# --------------------------------------------------------------------------

def rotation_render(data: dict) -> str:
    """Human-readable rotation advisory; never a gate, never telemetry."""
    guidance = data.get("rotation_guidance") or {}
    rec = guidance.get("recommendation", ROTATION_DEFAULT) if isinstance(guidance, dict) else ROTATION_DEFAULT
    export_verified = bool(guidance.get("export_verified", False)) if isinstance(guidance, dict) else False
    reason = (guidance.get("reason") or "").strip() if isinstance(guidance, dict) else ""
    if rec == "NO_ROTATION":
        return "rotation: NO_ROTATION"
    text = f"rotation: {rec}"
    if reason:
        text += f" ({reason})"
    if not export_verified:
        text += (
            " [export-missing: hygiene reminder, not telemetry; "
            "no token/cache figures exist without an `opencode export` aggregate]"
        )
    else:
        text += " [export-verified aggregate on record]"
    return text


def scan_telemetry_fabrication(text: str) -> list[str]:
    """Flag numeric token/cache/cost claims lacking export provenance."""
    if not text or not _TELEMETRY_PATTERN.search(text):
        return []
    if _EXPORT_PROVENANCE_PATTERN.search(text):
        return []
    return ["TELEMETRY_FABRICATION_RISK: numeric token/cache/cost claim without export provenance"]
