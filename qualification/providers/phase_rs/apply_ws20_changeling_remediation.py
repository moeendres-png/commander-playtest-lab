#!/usr/bin/env python3
"""Deterministic WS-20 v2 local remediation for the exact fresh phase.rs source.

The script modifies the candidate Rules Core, never the Commander Lab adapter.
`--repro-only` installs only the minimized regression and must fail upstream.
Default mode replaces the known lossy commander creature-type helper and installs
positive, negative, generalized, registration, and zone regressions.

The caller must verify the exact source commit/tree before invoking this script.
The script additionally guards the unchanged upstream TODO/function anchors so a
future source change fails closed instead of accepting a stale patch.
"""
from __future__ import annotations

import argparse
from pathlib import Path

PINNED_COMMIT = "5c87559082f4703c10c3f70692a02bb675c5e576"
REL = Path("crates/engine/src/game/commander.rs")

FUNCTION_START = "/// CR 205.3m + CR 903.3: The set of creature subtypes (\"creature types\") across\n"
FUNCTION_END = "fn push_creature_type(types: &mut Vec<String>, subtype: &str) {\n"
TEST_ANCHOR = "    // --- Deck Validation Tests ---\n"
TODO_SENTINEL = "// TODO(strict): CR 702.73a — a Changeling commander is every creature type and\n"

REPRO_TEST = r'''
    /// WS-20 minimized reproduction of the WS-15 blocker.
    /// CR 702.73a: Changeling means this object is every creature type in every zone.
    #[test]
    fn ws20_repro_changeling_commander_is_every_creature_type() {
        let mut state = setup_commander_game();
        state.all_creature_types = vec![
            "Elf".to_string(),
            "Goblin".to_string(),
            "Doctor".to_string(),
        ];
        let cmd_id = create_commander_in_command_zone(
            &mut state,
            PlayerId(0),
            "Generic Changeling Commander",
            vec![],
        );
        let obj = state.objects.get_mut(&cmd_id).unwrap();
        obj.keywords.push(crate::types::keywords::Keyword::Changeling);
        obj.base_keywords.push(crate::types::keywords::Keyword::Changeling);

        let types = commander_creature_types(&state, PlayerId(0));
        for expected in ["Elf", "Goblin", "Doctor"] {
            assert!(
                types.iter().any(|actual| actual.eq_ignore_ascii_case(expected)),
                "CR 702.73a: a Changeling commander must be every creature type; missing {expected}"
            );
        }
    }

'''

FULL_TESTS = REPRO_TEST + r'''
    /// Generalized regression: no named-card exception; any Changeling commander
    /// expands through the runtime creature-type authority and preserves explicit types.
    #[test]
    fn ws20_changeling_commander_generalized_and_deduplicated() {
        let mut state = setup_commander_game();
        state.all_creature_types = vec![
            "Elf".to_string(),
            "Goblin".to_string(),
            "Doctor".to_string(),
        ];
        let cmd_id = create_commander_in_command_zone(
            &mut state,
            PlayerId(0),
            "Unspecified Shapeshifter",
            vec![],
        );
        let obj = state.objects.get_mut(&cmd_id).unwrap();
        obj.card_types.subtypes = vec!["Shapeshifter".to_string(), "Elf".to_string()];
        obj.keywords.push(crate::types::keywords::Keyword::Changeling);
        obj.base_keywords.push(crate::types::keywords::Keyword::Changeling);

        let types = commander_creature_types(&state, PlayerId(0));
        assert!(types.iter().any(|t| t.eq_ignore_ascii_case("Shapeshifter")));
        assert!(types.iter().any(|t| t.eq_ignore_ascii_case("Doctor")));
        assert_eq!(
            types.iter().filter(|t| t.eq_ignore_ascii_case("Elf")).count(),
            1,
            "explicit and CDA-derived creature types must be case-insensitively deduplicated"
        );
    }

    /// CR 604.3 + CR 702.73a: the CDA functions in every zone. Commander
    /// designation is zone-independent, so this helper must not be battlefield-only.
    #[test]
    fn ws20_changeling_commander_zone_variants() {
        let mut state = setup_commander_game();
        state.all_creature_types = vec!["Elf".to_string(), "Doctor".to_string()];
        let cmd_id = create_commander_in_command_zone(
            &mut state,
            PlayerId(0),
            "Zone-Agnostic Changeling",
            vec![],
        );
        {
            let obj = state.objects.get_mut(&cmd_id).unwrap();
            obj.keywords.push(crate::types::keywords::Keyword::Changeling);
            obj.base_keywords.push(crate::types::keywords::Keyword::Changeling);
        }

        for zone in [Zone::Command, Zone::Graveyard, Zone::Exile, Zone::Hand, Zone::Library] {
            state.objects.get_mut(&cmd_id).unwrap().zone = zone;
            let types = commander_creature_types(&state, PlayerId(0));
            assert!(types.iter().any(|t| t.eq_ignore_ascii_case("Doctor")), "missing Changeling CDA in {zone:?}");
        }
    }

    /// Negative control: ordinary commanders do not gain unrelated creature types.
    #[test]
    fn ws20_nonchangeling_commander_does_not_gain_global_creature_types() {
        let mut state = setup_commander_game();
        state.all_creature_types = vec!["Elf".to_string(), "Doctor".to_string()];
        let cmd_id = create_commander_in_command_zone(
            &mut state,
            PlayerId(0),
            "Ordinary Commander",
            vec![],
        );
        state.objects.get_mut(&cmd_id).unwrap().card_types.subtypes = vec!["Elf".to_string()];

        let types = commander_creature_types(&state, PlayerId(0));
        assert_eq!(types, vec!["Elf".to_string()]);
        assert!(!types.iter().any(|t| t.eq_ignore_ascii_case("Doctor")));
    }

    /// Partner control: a Changeling partner contributes every creature type while
    /// an ordinary partner contributes its explicit type; the union stays deduplicated.
    #[test]
    fn ws20_changeling_partner_unions_with_other_commander() {
        let mut state = setup_commander_game();
        state.all_creature_types = vec!["Elf".to_string(), "Doctor".to_string()];
        let changeling = create_commander_in_command_zone(&mut state, PlayerId(0), "Partner A", vec![]);
        {
            let obj = state.objects.get_mut(&changeling).unwrap();
            obj.keywords.push(crate::types::keywords::Keyword::Changeling);
            obj.base_keywords.push(crate::types::keywords::Keyword::Changeling);
        }
        let ordinary = create_commander_in_command_zone(&mut state, PlayerId(0), "Partner B", vec![]);
        state.objects.get_mut(&ordinary).unwrap().card_types.subtypes = vec!["Elf".to_string()];

        let types = commander_creature_types(&state, PlayerId(0));
        assert!(types.iter().any(|t| t.eq_ignore_ascii_case("Doctor")));
        assert_eq!(types.iter().filter(|t| t.eq_ignore_ascii_case("Elf")).count(), 1);
    }

    /// Registered pre-game commander data is authoritative before object materialization;
    /// Changeling must expand from CardFace keywords as well as live objects.
    #[test]
    fn ws20_registered_changeling_commander_expands_before_materialization() {
        let mut state = setup_commander_game();
        state.all_creature_types = vec!["Elf".to_string(), "Doctor".to_string()];
        state.deck_pools.push(PlayerDeckPool {
            player: PlayerId(0),
            current_commander: std::sync::Arc::new(vec![DeckEntry {
                card: CardFace {
                    card_type: crate::types::card_type::CardType {
                        core_types: vec![CoreType::Creature],
                        subtypes: vec!["Shapeshifter".to_string()],
                        ..Default::default()
                    },
                    keywords: vec![crate::types::keywords::Keyword::Changeling],
                    ..CardFace::default()
                },
                count: 1,
            }]),
            ..PlayerDeckPool::default()
        });

        let types = commander_creature_types(&state, PlayerId(0));
        assert!(types.iter().any(|t| t.eq_ignore_ascii_case("Shapeshifter")));
        assert!(types.iter().any(|t| t.eq_ignore_ascii_case("Doctor")));
    }

'''

NEW_FUNCTION = r'''/// CR 205.3m + CR 903.3: The set of creature subtypes ("creature types") across
/// `player`'s commander(s).
///
/// CR 702.73a + CR 604.3: Changeling is a characteristic-defining ability that
/// means the object is every creature type and functions in every zone. phase.rs
/// already maintains `GameState::all_creature_types` as the runtime creature-type
/// authority used by type-changing effects and filters; expanding through that
/// authority avoids a named-card special case and avoids a second hard-coded catalog.
///
/// Reads `deck_pools.current_commander` first for pre-game registration, falling
/// back to live `is_commander && owner == player` objects. Partner commanders merge
/// their type sets. Subtypes are deduplicated case-insensitively.
pub fn commander_creature_types(state: &GameState, player: PlayerId) -> Vec<String> {
    let mut types: Vec<String> = Vec::new();

    if let Some(pool) = state.deck_pools.iter().find(|pool| pool.player == player) {
        for entry in pool.current_commander.iter() {
            if entry
                .card
                .card_type
                .core_types
                .contains(&crate::types::card_type::CoreType::Creature)
            {
                let has_changeling = entry
                    .card
                    .keywords
                    .iter()
                    .any(|keyword| matches!(keyword, crate::types::keywords::Keyword::Changeling));
                if has_changeling {
                    for subtype in &state.all_creature_types {
                        push_creature_type(&mut types, subtype);
                    }
                }
                for subtype in &entry.card.card_type.subtypes {
                    push_creature_type(&mut types, subtype);
                }
            }
        }
        if !types.is_empty() {
            return types;
        }
    }

    for obj in state
        .objects
        .values()
        .filter(|obj| obj.is_commander && obj.owner == player)
    {
        if obj
            .card_types
            .core_types
            .contains(&crate::types::card_type::CoreType::Creature)
        {
            // The printed/copiable CDA is retained in `base_keywords`; the current
            // set is also consulted for a materialized copied face. This helper is
            // specifically the Commander type-reference authority and does not add
            // legality or type semantics to the Foundry adapter.
            let has_changeling = obj
                .base_keywords
                .iter()
                .chain(obj.keywords.iter())
                .any(|keyword| matches!(keyword, crate::types::keywords::Keyword::Changeling));
            if has_changeling {
                for subtype in &state.all_creature_types {
                    push_creature_type(&mut types, subtype);
                }
            }
            for subtype in &obj.card_types.subtypes {
                push_creature_type(&mut types, subtype);
            }
        }
    }
    types
}

'''


def insert_tests(text: str, tests: str) -> str:
    if "ws20_repro_changeling_commander_is_every_creature_type" in text:
        raise SystemExit("WS-20 tests already present; refusing double application")
    if TEST_ANCHOR not in text:
        raise SystemExit("test insertion anchor missing; upstream changed")
    return text.replace(TEST_ANCHOR, tests + TEST_ANCHOR, 1)


def remediate(text: str) -> str:
    if TODO_SENTINEL not in text:
        raise SystemExit("WS-15 Changeling TODO sentinel missing; upstream implementation changed")
    start = text.find(FUNCTION_START)
    if start < 0:
        raise SystemExit("commander_creature_types start anchor missing")
    end = text.find(FUNCTION_END, start)
    if end < 0:
        raise SystemExit("commander_creature_types end anchor missing")
    return text[:start] + NEW_FUNCTION + text[end:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase_root", type=Path)
    ap.add_argument("--repro-only", action="store_true")
    args = ap.parse_args()

    path = args.phase_root / REL
    text = path.read_text(encoding="utf-8")
    if args.repro_only:
        text = insert_tests(text, REPRO_TEST)
    else:
        text = remediate(text)
        text = insert_tests(text, FULL_TESTS)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
