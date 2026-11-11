"""Playgroup.gg Card Atlas parser and structured metric extractor (#1192).

Extracts all publicly available structured card telemetry from Playgroup.gg card pages:
- Identity and metadata (slug, title, type line, set name, JSON-LD dataset)
- Prevalence (Live Inclusion %, Times Brought, Decks Running, Unique Players)
- First-cast tempo (n, 7 turn buckets T1-T10+, median, quartiles, max, on-curve, cast-same-turn)
- Funnel (Brought, Ever drawn, Reached battlefield, Still on board, Drawn->Played %, Survival %)
- Outcome observations (Winrate when cast/library/hand with exact n, observed gap, 95% CI)
- Final zone distribution (instances_n, library, battlefield, graveyard, exile)
- Top commanders (rank, name, slug, color identity, deck count)
- Quality warnings for known source discrepancies (e.g. Koma World-Eater brought mismatch & on-curve math)

Governing constraints:
- Pure standard library (re, json, unicodedata).
- No new Any usages (object instead of Any).
- No silent data correction: preserve exact source numbers and flag discrepancies in quality_warnings.
- Mandatory disclosure: 'Live-Korrelation (Playgroup.gg), keine kausale Kartenstärke.'
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Final

PLAYGROUP_DISCLOSURE: Final[str] = "Live-Korrelation (Playgroup.gg), keine kausale Kartenstärke."
PLAYGROUP_LICENSE: Final[str] = "CC BY 4.0"
PLAYGROUP_ATTRIBUTION: Final[str] = "Playgroup.gg"


def to_playgroup_slug(name: str) -> str:
    """Normalize a Magic card name to a Playgroup.gg card URL slug.

    Rules verified against live playgroup.gg endpoints:
    - Normalizes unicode accents (Séance -> seance, Lim-Dûl -> lim-dul)
    - Replaces ' // ' with '-' (split/adventure/modal double-faced cards)
    - Replaces non-alphanumeric characters with '-' (e.g. Drach'Nyen -> drach-nyen)
    - Collapses consecutive hyphens and strips ends.
    """
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = normalized.lower()
    s = s.replace(" // ", "-")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


@dataclass(frozen=True, slots=True)
class PlaygroupTopCommander:
    rank: int
    commander_name: str
    commander_slug: str
    color_identity: str
    decks_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PlaygroupFinalZone:
    zone_name: str
    pct: float
    instances_n: int | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PlaygroupCardRecord:
    card_name: str
    slug: str
    card_id: str | None = None
    oracle_id: str | None = None
    card_type: str | None = None
    set_name: str | None = None
    format_mode: str = "multiplayer"
    retrieved_at_utc: str | None = None
    dataset_identifier: str | None = None
    date_modified: str | None = None
    temporal_coverage: str | None = None
    license: str = PLAYGROUP_LICENSE
    live_inclusion_pct: float | None = None
    deck_inclusion_pct: float | None = None
    times_brought: int | None = None
    decks_running: int | None = None
    median_cast_turn: float | None = None
    drawn_to_played_pct: float | None = None
    first_cast_n: int | None = None
    turn_1_pct: float | None = None
    turn_2_pct: float | None = None
    turn_3_pct: float | None = None
    turn_4_pct: float | None = None
    turn_5_pct: float | None = None
    turn_6_to_9_pct: float | None = None
    turn_10_plus_pct: float | None = None
    p25_cast_turn: float | None = None
    p75_cast_turn: float | None = None
    max_cast_turn: float | None = None
    on_curve_pct: float | None = None
    on_curve_count: int | None = None
    on_curve_denominator: int | None = None
    on_curve_turn: str | None = None
    cast_same_turn_as_drawn_pct: float | None = None
    turns_in_hand: float | None = None
    funnel_brought_n: int | None = None
    funnel_players_n: int | None = None
    ever_drawn_n: int | None = None
    reached_battlefield_n: int | None = None
    still_on_board_at_end_n: int | None = None
    battlefield_survival_pct: float | None = None
    winrate_when_cast_pct: float | None = None
    winrate_when_cast_n: int | None = None
    winrate_when_in_library_pct: float | None = None
    winrate_when_in_library_n: int | None = None
    winrate_when_in_hand_pct: float | None = None
    winrate_when_in_hand_n: int | None = None
    observed_winrate_gap_pp: float | None = None
    ci_95_lower_pp: float | None = None
    ci_95_upper_pp: float | None = None
    conservative_ranking_indicator: str | None = None
    final_zones_instances_n: int | None = None
    final_zones: tuple[PlaygroupFinalZone, ...] = ()
    top_commanders: tuple[PlaygroupTopCommander, ...] = ()
    fetch_status: str = "OK"
    quality_warnings: tuple[str, ...] = ()
    insufficient_sample: bool = False
    disclosure: str = PLAYGROUP_DISCLOSURE

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["final_zones"] = [z.to_dict() for z in self.final_zones]
        d["top_commanders"] = [c.to_dict() for c in self.top_commanders]
        d["quality_warnings"] = list(self.quality_warnings)
        return d


def parse_playgroup_card_html(
    html: str,
    *,
    slug: str = "",
    card_id: str | None = None,
    oracle_id: str | None = None,
    format_mode: str = "multiplayer",
    retrieved_at_utc: str | None = None,
) -> PlaygroupCardRecord:
    """Parse raw HTML of a Playgroup.gg card page into a structured PlaygroupCardRecord."""
    warnings: list[str] = []

    # 1. JSON-LD Dataset
    dataset_identifier: str | None = None
    date_modified: str | None = None
    temporal_coverage: str | None = None
    license_url: str = PLAYGROUP_LICENSE

    for j in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        try:
            raw_json = json.loads(j)
            if isinstance(raw_json, dict) and raw_json.get("@type") == "Dataset":
                dataset_identifier = (
                    str(raw_json["identifier"]) if raw_json.get("identifier") else None
                )
                date_modified = (
                    str(raw_json["dateModified"]) if raw_json.get("dateModified") else None
                )
                temporal_coverage = (
                    str(raw_json["temporalCoverage"]) if raw_json.get("temporalCoverage") else None
                )
                if raw_json.get("license"):
                    license_url = str(raw_json["license"])
        except Exception:
            pass

    # 2. Card name and type
    card_name = ""
    title_m = re.search(r"<h1[^>]*>\s*([^\n<]+)\s*</h1>", html)
    if title_m:
        card_name = title_m.group(1).strip()
    elif slug:
        card_name = slug.replace("-", " ").title()

    card_type: str | None = None
    set_name: str | None = None
    type_m = re.search(
        r"<span>([^<]+)</span>\s*<span[^>]*>·</span>\s*<span>([^<]+)</span>\s*</div>\s*</div>\s*<div class=['\"]text-right",
        html,
    )
    if type_m:
        card_type = type_m.group(1).strip()
        set_name = type_m.group(2).strip()
    else:
        # Fallback card type search
        fallback_type = re.search(
            r"<div class=['\"][^'\"]*text-\[11px\][^'\"]*'>([^<]+)</div>", html
        )
        if fallback_type:
            card_type = fallback_type.group(1).strip()

    # 3. Live Inclusion
    live_inclusion_pct: float | None = None
    incl_m = re.search(
        r"<div class=['\"]font-oswald text-primary leading-none tabular-nums[^\"]*['\"][^>]*>\s*(\d+)%\s*</div>\s*<div[^>]*>Live Inclusion</div>",
        html,
    )
    if incl_m:
        live_inclusion_pct = float(incl_m.group(1))

    # 4. Top Summary Metrics
    times_brought: int | None = None
    tb_m = re.search(r"Times Brought</div>\s*<div[^>]*>(\d+)</div>", html)
    if tb_m:
        times_brought = int(tb_m.group(1))

    decks_running: int | None = None
    dr_m = re.search(r"Decks Running</div>\s*<div[^>]*>(\d+)</div>", html)
    if dr_m:
        decks_running = int(dr_m.group(1))

    median_cast_turn: float | None = None
    mct_m = re.search(r"Median Cast Turn</div>\s*<div[^>]*>\s*([\d\.]+)\s*</div>", html)
    if mct_m:
        median_cast_turn = float(mct_m.group(1))

    drawn_to_played_pct: float | None = None
    dp_m = re.search(r"Drawn → Played</div>\s*<div[^>]*>\s*(\d+)%\s*</div>", html)
    if dp_m:
        drawn_to_played_pct = float(dp_m.group(1))

    # 5. First-cast turn section
    first_cast_n: int | None = None
    turn_1_pct: float | None = None
    turn_2_pct: float | None = None
    turn_3_pct: float | None = None
    turn_4_pct: float | None = None
    turn_5_pct: float | None = None
    turn_6_to_9_pct: float | None = None
    turn_10_plus_pct: float | None = None
    p25_cast_turn: float | None = None
    p75_cast_turn: float | None = None
    max_cast_turn: float | None = None
    on_curve_pct: float | None = None
    on_curve_count: int | None = None
    on_curve_denominator: int | None = None
    on_curve_turn: str | None = None
    cast_same_turn_as_drawn_pct: float | None = None

    fc_m = re.search(r"First-cast turn</h2>\s*<span[^>]*>\s*n=(\d+)\s*</span>", html)
    if fc_m:
        first_cast_n = int(fc_m.group(1))

        # Buckets: T1, T2, T3, T4, T5, T6-9, T10+
        bucket_defs = [
            ("T1", "turn_1_pct"),
            ("T2", "turn_2_pct"),
            ("T3", "turn_3_pct"),
            ("T4", "turn_4_pct"),
            ("T5", "turn_5_pct"),
            ("T6-9", "turn_6_to_9_pct"),
            ("T10+", "turn_10_plus_pct"),
        ]
        bucket_vals: dict[str, float] = {}
        for b_label, var_name in bucket_defs:
            b_esc = re.escape(b_label)
            bm = re.search(
                r"<div class=['\"]font-oswald tabular-nums text-xs[^\"]*['\"][^>]*>\s*(\d+)%\s*</div>\s*<div[^>]*>\s*<div[^>]*></div>\s*</div>\s*<div[^>]*>"
                + b_esc
                + r"</div>",
                html,
            )
            if bm:
                bucket_vals[var_name] = float(bm.group(1))
        turn_1_pct = bucket_vals.get("turn_1_pct")
        turn_2_pct = bucket_vals.get("turn_2_pct")
        turn_3_pct = bucket_vals.get("turn_3_pct")
        turn_4_pct = bucket_vals.get("turn_4_pct")
        turn_5_pct = bucket_vals.get("turn_5_pct")
        turn_6_to_9_pct = bucket_vals.get("turn_6_to_9_pct")
        turn_10_plus_pct = bucket_vals.get("turn_10_plus_pct")

        # Quantiles: Median, P25, P75, max
        quant_m = re.search(
            r"Median\s*<strong[^>]*>([\d\.]+)</strong>\s*</span>\s*<span>\s*P25\s*<strong[^>]*>([\d\.]+)</strong>\s*·\s*P75\s*<strong[^>]*>([\d\.]+)</strong>\s*·\s*max\s*<strong[^>]*>([\d\.]+)</strong>",
            html,
        )
        if quant_m:
            p25_cast_turn = float(quant_m.group(2))
            p75_cast_turn = float(quant_m.group(3))
            max_cast_turn = float(quant_m.group(4))

        # On curve
        oc_m = re.search(
            r"On curve\s*<strong[^>]*>\s*(\d+)%\s*</strong>\s*<span[^>]*>\s*\(\s*(\d+)\s*/\s*(\d+)\s*cast on\s*([A-Za-z0-9\+]+)\s*\)",
            html,
        )
        if oc_m:
            on_curve_pct = float(oc_m.group(1))
            on_curve_count = int(oc_m.group(2))
            on_curve_denominator = int(oc_m.group(3))
            on_curve_turn = oc_m.group(4)
            # Check on-curve calculation discrepancy
            if on_curve_denominator > 0:
                calc_pct = round(100.0 * on_curve_count / on_curve_denominator, 1)
                if abs(calc_pct - on_curve_pct) > 2.0:
                    warnings.append(
                        f"On-curve calculation discrepancy: reported {on_curve_pct}% but "
                        f"{on_curve_count}/{on_curve_denominator} = {calc_pct}%"
                    )

        # Cast same turn as drawn
        std_m = re.search(r"Cast same turn as drawn\s*<strong[^>]*>\s*(\d+)%\s*</strong>", html)
        if std_m:
            cast_same_turn_as_drawn_pct = float(std_m.group(1))

    # 6. Funnel ("good card" funnel)
    funnel_brought_n: int | None = None
    funnel_players_n: int | None = None
    ever_drawn_n: int | None = None
    reached_battlefield_n: int | None = None
    still_on_board_at_end_n: int | None = None
    battlefield_survival_pct: float | None = None

    fn_head = re.search(
        r"The \"good card\" funnel</h2>\s*<span[^>]*>\s*(\d+)\s*brought\s*·\s*(\d+)\s*players\s*</span>",
        html,
    )
    if fn_head:
        funnel_brought_n = int(fn_head.group(1))
        funnel_players_n = int(fn_head.group(2))
        if times_brought is not None and times_brought != funnel_brought_n:
            warnings.append(
                f"Brought count discrepancy: Times Brought = {times_brought} vs Funnel Brought = {funnel_brought_n}"
            )

    for item, attr in [
        ("Ever drawn", "ever_drawn_n"),
        ("Reached battlefield", "reached_battlefield_n"),
        ("Still on board at game end", "still_on_board_at_end_n"),
    ]:
        im = re.search(
            r"<div class=['\"]text-on-surface['\"]>"
            + item
            + r"</div>.*?<div class=['\"]font-oswald tabular-nums text-on-surface text-right['\"]>(\d+)</div>",
            html,
            re.DOTALL,
        )
        if im:
            val = int(im.group(1))
            if attr == "ever_drawn_n":
                ever_drawn_n = val
            elif attr == "reached_battlefield_n":
                reached_battlefield_n = val
            elif attr == "still_on_board_at_end_n":
                still_on_board_at_end_n = val

    surv_m = re.search(
        r"Once cast,\s*(\d+)%\s*of this card is still on the battlefield at game end", html
    )
    if surv_m:
        battlefield_survival_pct = float(surv_m.group(1))

    # 7. Winrate observations and 95% Confidence Interval
    winrate_when_cast_pct: float | None = None
    winrate_when_cast_n: int | None = None
    winrate_when_in_library_pct: float | None = None
    winrate_when_in_library_n: int | None = None
    winrate_when_in_hand_pct: float | None = None
    winrate_when_in_hand_n: int | None = None
    observed_winrate_gap_pp: float | None = None
    ci_95_lower_pp: float | None = None
    ci_95_upper_pp: float | None = None
    conservative_ranking_indicator: str | None = None

    cons_m = re.search(
        r"<span class=['\"]font-oswald tabular-nums text-lg text-primary['\"]>\s*([^<]+)\s*</span>",
        html,
    )
    if cons_m:
        conservative_ranking_indicator = cons_m.group(1).strip()

    wr_cast_m = re.search(
        r"Players who cast this card win\s*<strong[^>]*>(\d+)%</strong>\s*of the time\s*<span[^>]*>\(n=(\d+)\)</span>\s*,\s*vs\s*<strong[^>]*>(\d+)%</strong>\s*when it never left the library\s*<span[^>]*>\(n=(\d+)\)\.?</span>",
        html,
    )
    if wr_cast_m:
        winrate_when_cast_pct = float(wr_cast_m.group(1))
        winrate_when_cast_n = int(wr_cast_m.group(2))
        winrate_when_in_library_pct = float(wr_cast_m.group(3))
        winrate_when_in_library_n = int(wr_cast_m.group(4))

    wr_hand_m = re.search(
        r"When players drew this card but left it in hand, they won\s*<strong[^>]*>(\d+)%</strong>\s*<span[^>]*>\(n=(\d+)\)\.?</span>",
        html,
    )
    if wr_hand_m:
        winrate_when_in_hand_pct = float(wr_hand_m.group(1))
        winrate_when_in_hand_n = int(wr_hand_m.group(2))

    gap_m = re.search(
        r"Observed gap\s*([+\-]?[\d\.]+)pp;\s*95% confidence interval\s*([+\-]?[\d\.]+)pp\s*to\s*([+\-]?[\d\.]+)pp",
        html,
    )
    if gap_m:
        observed_winrate_gap_pp = float(gap_m.group(1))
        ci_95_lower_pp = float(gap_m.group(2))
        ci_95_upper_pp = float(gap_m.group(3))

    # 8. Final zone distribution
    final_zones_instances_n: int | None = None
    fz_head = re.search(r"Final zone distribution</h2>\s*<span[^>]*>(\d+)\s*instances</span>", html)
    if fz_head:
        final_zones_instances_n = int(fz_head.group(1))

    final_zones_list: list[PlaygroupFinalZone] = []
    zone_blocks = re.findall(
        r"<div class=['\"]font-oswald tabular-nums text-2xl[^'\"]*['\"][^>]*>\s*([\d\.]+)%\s*</div>\s*<div class=['\"]uppercase mt-1 text-on-surface_variant[^'\"]*['\"][^>]*>\s*([^<]+)\s*</div>",
        html,
    )
    for pct_s, zname in zone_blocks:
        final_zones_list.append(
            PlaygroupFinalZone(
                zone_name=zname.strip(),
                pct=float(pct_s),
                instances_n=final_zones_instances_n,
            )
        )

    # 9. Top Commanders
    top_commanders_list: list[PlaygroupTopCommander] = []
    cmdr_blocks = re.findall(
        r"<li class=['\"]grid items-center gap-4 py-3 grid-cols-\[28px_1fr_auto\] text-sm['\"]>\s*<span[^>]*>(\d+)</span>\s*<span[^>]*>\s*<a class=\"[^\"]*\" href=\"/commanders/([^\"]+)\">([^<]+)</a>\s*<span[^>]*>(.*?)</span>\s*</span>\s*<span[^>]*>\s*<span class=['\"]font-oswald tabular-nums text-on-surface['\"]>(\d+)\s*decks</span>",
        html,
        re.DOTALL,
    )
    for rank_s, cslug, cname, col_html, decks_s in cmdr_blocks:
        colors = "".join(re.findall(r'alt="\{([WUBRG])\}"', col_html))
        top_commanders_list.append(
            PlaygroupTopCommander(
                rank=int(rank_s),
                commander_slug=cslug.strip(),
                commander_name=cname.strip(),
                color_identity=colors,
                decks_count=int(decks_s),
            )
        )

    # 10. Status classification
    insufficient_sample = False
    effective_n = first_cast_n or 0
    if effective_n >= 30:
        fetch_status = "OK"
    elif effective_n > 0 or (times_brought is not None and times_brought > 0):
        fetch_status = "PARTIAL"
        insufficient_sample = True
        warnings.append(f"Sample size n={effective_n} < 30: marked PARTIAL / insufficient evidence")
    else:
        fetch_status = "NO_DATA"

    return PlaygroupCardRecord(
        card_name=card_name,
        slug=slug,
        card_id=card_id,
        oracle_id=oracle_id,
        card_type=card_type,
        set_name=set_name,
        format_mode=format_mode,
        retrieved_at_utc=retrieved_at_utc,
        dataset_identifier=dataset_identifier,
        date_modified=date_modified,
        temporal_coverage=temporal_coverage,
        license=license_url,
        live_inclusion_pct=live_inclusion_pct,
        times_brought=times_brought,
        decks_running=decks_running,
        median_cast_turn=median_cast_turn,
        drawn_to_played_pct=drawn_to_played_pct,
        first_cast_n=first_cast_n,
        turn_1_pct=turn_1_pct,
        turn_2_pct=turn_2_pct,
        turn_3_pct=turn_3_pct,
        turn_4_pct=turn_4_pct,
        turn_5_pct=turn_5_pct,
        turn_6_to_9_pct=turn_6_to_9_pct,
        turn_10_plus_pct=turn_10_plus_pct,
        p25_cast_turn=p25_cast_turn,
        p75_cast_turn=p75_cast_turn,
        max_cast_turn=max_cast_turn,
        on_curve_pct=on_curve_pct,
        on_curve_count=on_curve_count,
        on_curve_denominator=on_curve_denominator,
        on_curve_turn=on_curve_turn,
        cast_same_turn_as_drawn_pct=cast_same_turn_as_drawn_pct,
        funnel_brought_n=funnel_brought_n,
        funnel_players_n=funnel_players_n,
        ever_drawn_n=ever_drawn_n,
        reached_battlefield_n=reached_battlefield_n,
        still_on_board_at_end_n=still_on_board_at_end_n,
        battlefield_survival_pct=battlefield_survival_pct,
        winrate_when_cast_pct=winrate_when_cast_pct,
        winrate_when_cast_n=winrate_when_cast_n,
        winrate_when_in_library_pct=winrate_when_in_library_pct,
        winrate_when_in_library_n=winrate_when_in_library_n,
        winrate_when_in_hand_pct=winrate_when_in_hand_pct,
        winrate_when_in_hand_n=winrate_when_in_hand_n,
        observed_winrate_gap_pp=observed_winrate_gap_pp,
        ci_95_lower_pp=ci_95_lower_pp,
        ci_95_upper_pp=ci_95_upper_pp,
        conservative_ranking_indicator=conservative_ranking_indicator,
        final_zones_instances_n=final_zones_instances_n,
        final_zones=tuple(final_zones_list),
        top_commanders=tuple(top_commanders_list),
        fetch_status=fetch_status,
        quality_warnings=tuple(warnings),
        insufficient_sample=insufficient_sample,
        disclosure=PLAYGROUP_DISCLOSURE,
    )
