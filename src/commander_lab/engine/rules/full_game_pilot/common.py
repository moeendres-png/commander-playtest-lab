"""Protocol constants, mana-text helpers, errors and pilot bindings of the full-game lane."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import wraps
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commander_lab.agents import BasePilot
from commander_lab.agents.card_knowledge import card_facts
from commander_lab.engine.rules.failure_privacy import (
    PUBLIC_FAILURE_CODES,
    public_full_game_exception_message,
    public_full_game_message,
    redacted_exception,
    redacted_exception_message,
)
from commander_lab.models import (
    PilotConfig,
)

FULL_GAME_DECISION_PROTOCOL_VERSION = "xmage-external-decision-protocol-1.0.0"
FULL_GAME_LANE = "xmage_full_game_external_pilots"
FULL_GAME_EVIDENCE_CLASS: Literal["technical_conformance_only"] = "technical_conformance_only"
XMAGE_FULL_GAME_COMMAND_ENV = "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"
# Optional extra JVM flags spliced right after the java launcher of the bridge
# command (diagnostics only, e.g. -XX:+HeapDumpOnOutOfMemoryError
# -XX:HeapDumpPath=... for #816). Ignored for non-java launchers.
XMAGE_JVM_FLAGS_ENV = "COMMANDER_LAB_XMAGE_JVM_FLAGS"

# Bridge-process shutdown dispositions observed by close(). Only
# graceful_shutdown may back a clean-shutdown evidence claim; every other
# outcome must fail closed where such a claim matters.
FULL_GAME_SHUTDOWN_GRACEFUL: Literal["graceful_shutdown"] = "graceful_shutdown"
FULL_GAME_SHUTDOWN_UNACKED_EXIT = "unacked_exit"
FULL_GAME_SHUTDOWN_FORCED_KILL = "forced_kill"
FULL_GAME_SHUTDOWN_ALREADY_EXITED = "already_exited"

# WS229 forced-move audit channel. Forced moves (no pilot discretion) are
# auto-submitted only with a structured log record; discretionary actions
# are never hidden from the pilot.
_LOG = logging.getLogger("commander_lab.engine.rules.full_game")

# Boolean outcomes whose "No" answer the pilot treats as aligned. The engine's
# Outcome on a may-prompt is a polarity hint about the choice itself:
# DETRIMENT means accepting hurts the controller. AIDontUseIt is deliberately
# NOT one of them. In XMage that outcome is a label for the engine's own AI
# declining a prompt whose acceptance cannot be judged safely (the repeatable
# multikicker offer, whose affordability check covers one payment only); it is
# not a statement about a player's preference. Reading it as "decline" made
# this Lab refuse every single kicker, buyback, dredge, replicate and squad
# prompt, which is an engine-AI label deciding for a player (F-RULES-03). Its
# loop is bounded instead by the multikicker-chain guard in _decide_boolean.
DECLINE_ALIGNED_BOOLEAN_OUTCOMES = frozenset({"detriment", "detriment_to_controller"})

# Liveness bound for the one may-offer the engine actually repeats.
# ``KickerAbility.addOptionalAdditionalCosts`` phrases it as
# ``"Pay " + (activatedCount + 1) + (" time "|" times ") + cost + " ?"``, so
# "Pay N times" names the ORDINAL of the offer being made -- not a declared
# total -- and N grows by exactly one each time the engine re-offers inside a
# single cast. That ordinal is the only thing that distinguishes the repeating
# offer from an ordinary "Pay {1}?" may-trigger (Mentor of the Meek asks that
# once per creature entering), so the guard in _decide_boolean counts only
# while one ability re-offers with N = previous N + 1, and never caps a prompt
# it cannot parse.
_BOOLEAN_MULTIKICKER_RE = re.compile(r"\bpay\s+(\d+)\s+times?\b", re.IGNORECASE)

# Bridge cost-fact keys (enrichAbilityCostFacts) rendered back into the mana
# symbol text mana_payment_fit already parses. This translates the engine's own
# numbers; it never invents a cost, and an absent fact renders as nothing.
_MANA_COST_COLORS: tuple[tuple[str, str], ...] = (
    ("mana_cost_white", "W"),
    ("mana_cost_blue", "U"),
    ("mana_cost_black", "B"),
    ("mana_cost_red", "R"),
    ("mana_cost_green", "G"),
    ("mana_cost_colorless", "C"),
)


def _cost_amount(metadata: dict[str, Any], key: str) -> float | None:
    """One engine cost fact, or None when the bridge did not report it."""
    value = metadata.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _mana_cost_text(metadata: dict[str, Any]) -> str:
    """Render the bridge's mana-cost facts as the symbols the engine printed.

    Used only to order the pilot's mana sources against an action's cost
    (``mana_payment_fit``); the engine remains the authority on what a payment
    actually costs and on whether it can be made at all.
    """
    parts: list[str] = []
    for key, letter in _MANA_COST_COLORS:
        amount = _cost_amount(metadata, key)
        if amount is not None and amount > 0:
            parts.extend([f"{{{letter}}}"] * int(amount))
    generic = _cost_amount(metadata, "mana_cost_generic")
    if generic is not None and generic > 0:
        parts.append(f"{{{int(generic)}}}")
    return "".join(parts)


_MANA_SYMBOL = re.compile(r"\{([^}]*)\}")
_COLOR_LETTERS = frozenset("wubrgc")

# The bridge's ``enrichAbilityCostFacts`` mana breakdown, as the engine
# publishes it on every ability option. Summing them is the cost's non-X mana
# value: XMage builds an ``X`` symbol as a ``VariableManaCost`` whose own
# ``cost`` Mana is empty, so the announced value never appears in any of
# these numbers. The bridge publishes no X count on any frame, so the count
# is read from the engine's own prompt instead (#700).
_PRIORITY_MANACOST_KEYS: tuple[str, ...] = (
    "mana_cost_white",
    "mana_cost_blue",
    "mana_cost_black",
    "mana_cost_red",
    "mana_cost_green",
    "mana_cost_generic",
    "mana_cost_colorless",
)

# ``Player.announceX`` serves two engine call sites, and only one of them is a
# mana cost. ``AbilityImpl.handleManaXCosts`` prompts "Announce the value for "
# + ``VariableManaCost.getText()``, which prints every X symbol of the cost as
# its own mana symbol and nothing else: "{X}", or "{X}{X}" for ``{X}{X}`` (it
# never folds two symbols into "2{X}"). ``VariableCostImpl.announce`` with
# ``isManaPay == false`` prompts "Announce the value for {X} (" + actionText
# + ")" for a non-mana X, so its prompt carries a "{X}" as well but keeps
# going afterwards. A mana budget is only a statement about a mana X, so the
# engine's own printed prompt is the discriminator, and it is matched WHOLE:
# only a prompt that is exactly the prefix followed by one or more "{X}" and
# nothing else is a mana X. Matching it whole is also what makes the same
# prompt the X count. Engine text, never a Lab-invented one.
_MANA_X_PROMPT = re.compile(r"\AAnnounce the value for (?P<symbols>(?:\{X\})+)\Z", re.IGNORECASE)
# One engine call site announces a mana X through the non-mana wording: Numa, Joraga Chieftain
# asks "Pay {X}{X}?", then ``announceX(0, Integer.MAX_VALUE, "Announce the value for {X} (pay to
# distribute counters)")`` and pays ``{X}{X}`` as ``GenericManaCost(2 * X)``. Announcing the
# ceiling overflows that product, the payment costs nothing and the engine distributes two
# billion counters (precon pod, plan seed 11: no decision for 75 s, BRIDGE_ERROR). The prompt
# is matched whole, and it stands for the two X symbols of the cost it pays.
_PAID_X_PROMPT = re.compile(
    r"\AAnnounce the value for \{X\} \(pay to distribute counters\)\Z", re.IGNORECASE
)
_PAID_X_SYMBOLS = 2
_X_SYMBOL_TOKEN = re.compile(r"\{X\}", re.IGNORECASE)

# XMage's per-game object short id, in the form the pinned engine emits.
#
# Provenance (the canonical XMage pin in config/rules_engines.json):
#   Mage/src/main/java/mage/MageObjectImpl.java:108-110  getIdName()
#       return getName() + " [" + getId().toString().substring(0, 3) + ']';
#   Mage/src/main/java/mage/util/GameLog.java:70-78  getColoredObjectIdName()
#       passes String.format("[%s]", mageObject.getId().toString().substring(0, 3))
#   and GameLog.java:103-116 appends that tag AFTER the closing "</font>", so the
#   engine prints "...<font ...>Name</font> [3a4]" (worked examples in the
#   injectPopupSupport javadoc, GameLog.java:125-132). getLogName() delegates
#   there (MageObjectImpl.java:112-115, CardImpl.java:888-895), so EVERY prompt
#   that names an object carries the tag wherever the engine printed it: at the
#   end of the text, before </div>, or before the message's own punctuation,
#   e.g. "Change this 1 of 1 target: Siege-Gang Commander [3a4]?".
#
# The tag is a prefix of a per-process object UUID, so it carries no Rules
# content and must never enter a twin semantic digest. The 3-8 hex width is the
# width this file's existing tag stripping and the `redact_text` lineage
# already accept (UUID prefix plus the wider face-down/toString forms), not a
# new guess at the shape.
#
# Only an APPENDED tag is removed. It must sit where the engine puts one:
# directly after a closing HTML tag it wrote next to the name, or after the
# whitespace that follows an object name, and it must be followed by a message
# boundary (end of text, a closing tag, punctuation or whitespace). Genuine
# bracketed Rules text does not have that shape, so it survives.
_XMAGE_SHORT_ID_TAG = r"\[[0-9a-fA-F]{3,8}\]"
# Written by the engine right after the name it just closed: "</font> [3a4]".
# Keep the closing tag so the prompt's HTML shape is preserved.
_XMAGE_SHORT_ID_AFTER_CLOSE_RE = re.compile(rf"(</[a-zA-Z][^>]*>)\s*{_XMAGE_SHORT_ID_TAG}")
# Appended after the object name and followed by the rest of the message.
_XMAGE_SHORT_ID_APPENDED_RE = re.compile(rf"\s+{_XMAGE_SHORT_ID_TAG}(?=[^\w]|\Z)")


def mana_x_prompt_symbols(prompt: str) -> int | None:
    """How many X symbols the engine's own mana-X prompt prints, else None.

    None means the prompt is not that exact mana shape: a non-mana X, which the
    engine words further after its "{X}", or anything else the engine says.
    Only the whole-prompt match counts, so the returned number is the X count
    of the announced cost (CR 601.2b, 107.3a) and never a guess about a prompt
    that merely mentions the symbol.
    """
    text = (prompt or "").strip()
    if _PAID_X_PROMPT.match(text) is not None:
        return _PAID_X_SYMBOLS
    match = _MANA_X_PROMPT.match(text)
    if match is None:
        return None
    return len(_X_SYMBOL_TOKEN.findall(match.group("symbols")))


def mana_payment_fit(label: str, unpaid_mana: str) -> int:
    """Order mana abilities inside a payment by what their mana can pay.

    2: the ability makes mana of a color the unpaid cost names, or any color;
    1: it can only pay a generic part; 0: the unpaid cost has no generic part
    and none of its colors. This reads the engine's own ability text
    ("{T}: Add {U}.") and the unpaid cost the engine reports. It only orders
    the pilot's options and never removes one: an unreadable label ranks 1,
    and the engine still applies (or refuses) whatever mana is produced.
    Without it the pilot broke the tie by label order, tapping a Plains-side
    {W} for a {U/R} cost and stranding the payment.
    """
    text = label.casefold()
    produced_text = text.partition(": add ")[2]
    if not produced_text:
        return 1
    if "any color" in produced_text or "any type" in produced_text:
        return 2
    produced = {
        letter
        for symbol in _MANA_SYMBOL.findall(produced_text)
        for letter in symbol
        if letter in _COLOR_LETTERS
    }
    if not produced:
        return 1
    needed: set[str] = set()
    generic = False
    for symbol in _MANA_SYMBOL.findall(unpaid_mana.casefold()):
        letters = {part for part in symbol.split("/") if part in _COLOR_LETTERS}
        needed |= letters
        if not letters or any(part.isdigit() or part == "x" for part in symbol.split("/")):
            generic = True
    if produced & needed:
        return 2
    return 1 if generic else 0


def mana_produced_letters(label: str) -> frozenset[str] | None:
    """Mana letters an engine mana-ability label says it adds, or None if unreadable.

    "Any color"/"any type" reads as all five colors. Same text source as
    ``mana_payment_fit``: the engine's own ability text.
    """
    produced_text = label.casefold().partition(": add ")[2]
    if not produced_text:
        return None
    if "any color" in produced_text or "any type" in produced_text:
        return frozenset("wubrg")
    produced = frozenset(
        letter
        for symbol in _MANA_SYMBOL.findall(produced_text)
        for letter in symbol
        if letter in _COLOR_LETTERS
    )
    return produced or None


def mana_needed_letters(unpaid_mana: str) -> frozenset[str]:
    """Colored mana letters an unpaid cost still names (hybrid halves included)."""
    return frozenset(
        part
        for symbol in _MANA_SYMBOL.findall(unpaid_mana.casefold())
        for part in symbol.split("/")
        if part in _COLOR_LETTERS
    )


class _MultikickerOffer(NamedTuple):
    """One "Pay N times" offer, as the pinned engine phrased it.

    ``ordinal`` is ``activatedCount + 1`` in
    ``KickerAbility.addOptionalAdditionalCosts``: the number of the offer
    being made, which advances by one per payment. ``per_payment`` is the
    mana value of the cost the prompt prints ("{2}"), or None when the prompt
    prints no mana symbol the pilot could divide by.
    """

    ordinal: int
    per_payment: int | None


def _prompt_mana_value(prompt: str) -> int | None:
    """Mana value of the symbols a prompt prints, or None if it prints none.

    "{2}" is two and a colored symbol is one (CR 106.4c). A prompt that
    prints no symbol states no per-payment cost, so it returns None rather
    than inventing one.
    """
    total = 0
    for symbol in _MANA_SYMBOL.findall(prompt or ""):
        text = symbol.strip()
        if not text:
            continue
        try:
            total += max(1, int(text))
        except ValueError:
            total += 1
    return total or None


def _multikicker_offer(prompt: str) -> _MultikickerOffer | None:
    """The engine's repeatable multikicker offer, or None for any other prompt.

    Anything the engine phrases without a "Pay N times" ordinal -- a plain
    kicker, buyback, dredge, replicate, squad or "Pay {1}?" may-trigger -- is
    a single discretionary question and returns None, so no liveness guard can
    ever cap it.
    """
    match = _BOOLEAN_MULTIKICKER_RE.search(prompt or "")
    if match is None:
        return None
    try:
        ordinal = int(match.group(1))
    except ValueError:  # pragma: no cover - the regex admits only digits
        return None
    if ordinal < 1:
        return None
    return _MultikickerOffer(ordinal=ordinal, per_payment=_prompt_mana_value(prompt))


class FullGameProtocolError(RuntimeError):
    """Fail-closed full-game bridge or external-pilot protocol error.

    ``str(exc)`` is the public message and is safe to persist: Lab-authored
    text plus, for transport failures, a stable ``code``. Raw bridge output
    (protocol lines, engine error text, stderr) lives only in
    ``diagnostics`` in memory and never reaches the message (C4).
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        diagnostics: tuple[str, ...] = (),
    ) -> None:
        public = public_full_game_message(message, code=code)
        super().__init__(public)
        self.__suppress_context__ = True
        self.public_message = public
        self.code = (
            code
            if code is None or (type(code) is str and code in PUBLIC_FAILURE_CODES)
            else "ENGINE_FAILURE"
        )
        self.diagnostics = diagnostics


class FullGameConformanceError(RuntimeError):
    """A run violated a full-game conformance invariant.

    Every message is Lab-authored; engine-supplied text is reduced with
    ``redacted_summary`` before it is interpolated (C4).
    """

    def __init__(self, message: str) -> None:
        super().__init__(public_full_game_message(message))
        self.__suppress_context__ = True

    @property
    def public_message(self) -> str:
        return str(self)


def _option_non_x_mana_value(metadata: dict[str, Any]) -> int | None:
    """A priority option's engine-reported cost as a non-X mana value.

    ``non_x`` is the sum of the bridge's ``mana_cost_*`` breakdown. XMage holds
    an ``{X}`` symbol as a ``VariableManaCost`` whose own ``cost`` Mana is
    empty and whose value is only fixed once the player announces it, so the
    announced X is absent from every one of those numbers and the sum is the
    rest of the cost alone (CR 601.2b, 107.3a). ``mana_cost_generic`` counts
    generic symbols only, never the colored ones alongside them.

    No X count comes with it: the bridge publishes none on any frame, and the
    cost's own count is in the engine's prompt, so the caller reads it there.

    ``None`` means the bridge reported no breakdown, or one the Lab cannot
    read as a non-negative integer: an unknown cost is never turned into a
    number.
    """
    non_x = 0
    for key in _PRIORITY_MANACOST_KEYS:
        raw = metadata.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            return None
        non_x += raw
    return non_x


# The cost the engine prints for an X paid by removing counters from the
# ability's own source: "Remove X +1/+1 counters from {this}" (a card that
# names itself prints a short name instead, "... from Marath"). Only this exact
# phrase is read; any other X cost keeps the engine's own bounds.
_REMOVE_X_COUNTERS = re.compile(
    r"\bRemove X (?P<kind>\S+) counters? from (?P<source>\{this\}|[^:,<]+?)\s*(?::|,|$)",
    re.IGNORECASE,
)


def option_x_counter_cap(
    label: str,
    metadata: Mapping[str, object],
    battlefield: object,
) -> int | None:
    """How many counters an "X" paid by removing counters from its source can use.

    #920: some cards pay an announced X by removing X counters from themselves
    through a cost the engine does not bound (Marath, Will of the Wild: ``{X},
    Remove X +1/+1 counters from Marath``). The engine then lets X exceed the
    counters, pays the mana, and cannot remove the counters, so the activation
    is reversed and the game stops. The pilot can see the counters, which are
    board-public, and read the cost off the option's own printed text, so it
    keeps its announced X within what is there.

    ``None`` means the option has no such cost, the printed source is not this
    ability's own permanent, or the permanent is not on the battlefield view;
    an unreadable cost is never turned into a number.
    """
    match = _REMOVE_X_COUNTERS.search(label or "")
    if match is None:
        return None
    source_id = str(metadata.get("source_object_id") or "")
    source_name = str(metadata.get("source_name") or "").casefold()
    printed = match.group("source").strip().casefold()
    # The printed name is this ability's own permanent: "{this}", the full
    # name, or the short name a legendary card uses for itself.
    if not source_id or (
        printed != "{this}" and not (source_name and source_name.startswith(printed))
    ):
        return None
    if not isinstance(battlefield, list):
        return None
    kind = match.group("kind").casefold()
    for item in battlefield:
        if not isinstance(item, dict) or str(item.get("object_id") or "") != source_id:
            continue
        counters = item.get("counters")
        if not isinstance(counters, list):
            return None
        total = 0
        for entry in counters:
            if not isinstance(entry, dict) or str(entry.get("type") or "").casefold() != kind:
                continue
            count = entry.get("count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                return None
            total += count
        return total
    return None


# The cost the engine prints for an X paid by tapping permanents: "Tap X untapped artifacts
# you control" (Necron Overlord). The kind is the plural noun before "you control".
_TAP_X_UNTAPPED = re.compile(
    r"\bTap X untapped (?P<kind>[a-z]+?)s? you control\b",
    re.IGNORECASE,
)


def option_x_tap_cap(
    label: str,
    metadata: Mapping[str, object],
    battlefield: object,
) -> int | None:
    """How many permanents an "X" paid by tapping X untapped permanents can use.

    Sibling of ``option_x_counter_cap`` (#920, plan seed 1, game seed 101, pod 024): Necron
    Overlord's ``{X}, {T}, Tap X untapped artifacts you control`` leaves X unbounded in the
    engine, the benefit-biased pilot announced the 14 mana its Swamps could pay, the mana was
    paid, and the tap cost found five artifacts, so the activation was reversed and the game
    stopped. The untapped permanents are board-public, and the cost is printed on the option the
    pilot chose, so the pilot keeps its announced X within what is there.

    The source is not counted when the same cost taps it (``{T}``): it is tapped first. A
    permanent counts when the printed card catalog gives it the printed type; a token or an
    unknown card does not, which only ever lowers the cap. Mana paid out of the same artifacts
    is not subtracted (a residual, like the mana budget's one-permanent-one-mana reading).

    ``None`` means the option has no such cost or there is no battlefield view; an unreadable
    cost is never turned into a number.
    """
    match = _TAP_X_UNTAPPED.search(label or "")
    if match is None or not isinstance(battlefield, list):
        return None
    kind = match.group("kind").casefold()
    source_id = str(metadata.get("source_object_id") or "")
    taps_source = "{t}" in (label or "").casefold()
    count = 0
    for item in battlefield:
        if not isinstance(item, dict) or item.get("tapped") is not False:
            continue
        if item.get("face_down") is True:
            continue
        if taps_source and source_id and str(item.get("object_id") or "") == source_id:
            continue
        facts = card_facts(str(item.get("name") or ""))
        if facts is not None and kind in facts.types:
            count += 1
    return count


def offers_mana_ability(rule_text: str) -> bool:
    """Whether a public permanent's own ability text reads as a mana ability.

    Same public text convention ``mana_payment_fit`` already orders by: the
    engine prints a mana ability as "``{T}: Add {W}.``", so the produced part
    after ": add " names what it adds. This is a pilot-side affordability
    reading over the actor's own board, never a legality verdict: the Rules
    Core still decides whether any payment succeeds.

    It is deliberately conservative. Text that does not literally read "add"
    followed by a color/type letter in braces ("Add {W}", "Add {C}{C}",
    "Add {G/W}") is not recognised, so an unrecognised mana source lowers the
    pilot's own budget estimate and it announces a smaller value rather than
    one it may not be able to pay.
    """
    produced = str(rule_text).casefold().partition(": add ")[2]
    if not produced:
        return False
    if "any color" in produced or "any type" in produced:
        return True
    return any(
        part in _COLOR_LETTERS
        for symbol in _MANA_SYMBOL.findall(produced)
        for part in symbol.split("/")
    )


def public_full_game_errors[**P, T](operation: Callable[P, T]) -> Callable[P, T]:
    """Keep engine parsing and pilot errors behind the shared public boundary."""

    @wraps(operation)
    def guarded(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            if type(exc) is FullGameProtocolError:
                # Even an exact public exception can carry a dict subclass or
                # hostile keys. Never invoke its lookup/iteration/equality hooks.
                metadata = {
                    key: value for key, value in dict.items(exc.__dict__) if type(key) is str
                }
                raw_code = metadata.get("code")
                code = raw_code if type(raw_code) is str or raw_code is None else "ENGINE_FAILURE"
                # A pilot can attach private notes even to the exact public class.
                # Rebuild the exception; never copy notes or traceback metadata.
                raise FullGameProtocolError(
                    public_full_game_exception_message(exc, code=code),
                    code=code,
                    diagnostics=metadata.get("diagnostics", ()),
                ) from None
            if issubclass(type(exc), FullGameConformanceError):
                raise FullGameConformanceError(public_full_game_exception_message(exc)) from None
            if issubclass(type(exc), FullGameProtocolError):
                raise FullGameProtocolError(redacted_exception_message(exc)) from None
            raise redacted_exception(exc) from None

    return guarded


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FullGamePilotBinding(_StrictModel):
    seat: int = Field(ge=1, le=6)
    deck_id: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    commander_names: tuple[str, ...]
    config: PilotConfig
    pilot_identity: str = Field(min_length=1)
    pilot_version: str = Field(min_length=1)
    decision_policy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def identity_matches_config(self) -> FullGamePilotBinding:
        requested = self.config.pilot_name.casefold().strip()
        if requested != "auto" and requested != self.pilot_identity.casefold().strip():
            raise ValueError("pilot_identity must match explicit PilotConfig.pilot_name")
        if not self.commander_names:
            raise ValueError("commander_names must not be empty")
        return self


@dataclass(frozen=True, slots=True)
class _RuntimePilot:
    binding: FullGamePilotBinding
    pilot: BasePilot
