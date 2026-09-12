#!/bin/bash
# WS77 provider transport-remediation build (WS77-owned, qualification-only).
# Mechanically equivalent to the WS68 build chain (ws68_build.sh) with only
# path/provenance changes for this WS77 worktree and the VERIFIED-ACCEPTED-PIN
# Forge checkout /home/moeen/ws77-forge-src-a9a95db (HEAD/tree/clean verified
# identical to the accepted pin; /tmp/ws65-forge-src-a9a95db lost its ignored
# target/ build output while /tmp stood at 100% and no workstream may delete
# another workstream's /tmp data), PLUS the WS77 transport observation overlay
# (additive milestones on payManaCost/applyManaToCost early-false paths; zero
# semantic change) applied after the WS68 overlay. No other overlay,
# generator, or bootstrap semantic change. Order (binding): generate(ws40) ->
# bootstrap -> successor/state overlays -> WS48 behavior overlay (repaired) ->
# WS53 chained overlay -> WS55 breadth overlay -> WS62 concession-transport +
# stack-SA overlay -> WS64 countertype-singleton transport overlay -> WS68
# transport remediation overlay -> WS77 transport observation overlay -> javac
# against accepted-pin fresh classes (never old-pin prebuilts as evidence).
# Forge checkout consumed READ-ONLY except ignored target/ build output
# from the required fresh mvn compile (no source edits). No WS48/WS53/WS55/
# WS62/WS64/WS68-owned file is modified. CPL audit base files are staged from
# this worktree only.
set -euo pipefail
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
WS=/home/moeen/code/ws77-forge-ghalta-covenant-provider-remediation
FORGE=/home/moeen/ws77-forge-src-a9a95db
EV=/home/moeen/ws77-ev
REF=/home/moeen/.ws48-r1e/ev
FORGE_COMMIT=a9a95db6662c2d28814390a9c0c2f986e39aa8b4
FORGE_TREE=2c18327f79e330f2ed167067166ffd42d61b0849
export FORGE_COMMIT FORGE_TREE
mkdir -p "$EV/runners" "$EV/generated" "$EV/classes" "$EV/contract"
cd "$WS"
# Accepted-pin identity gate on the consumed checkout (read-only check).
test "$(git --git-dir="$FORGE/.git" rev-parse HEAD)" = "$FORGE_COMMIT"
test "$(git --git-dir="$FORGE/.git" rev-parse 'HEAD^{tree}')" = "$FORGE_TREE"
test -z "$(git --git-dir="$FORGE/.git" --work-tree="$FORGE" status --short --untracked-files=no)"
grep -q "tokenReader" qualification/providers/forge/gpl/Ws23ForgeBootstrap.java
cp candidate-qualification/ws45-forge-v1.0.4/run_strict_no_echo_gate.py "$EV/runners/run_strict_no_echo_gate.py"
cp candidate-qualification/ws48-forge-v1.0.5/run_behavior_transcript_probe.py "$EV/runners/run_behavior_transcript_probe.py"
python3 scripts/ws45_patch_noecho_runner_lineage.py --runner "$EV/runners/run_strict_no_echo_gate.py"
python3 scripts/ws45_patch_noecho_runner_forge_lock.py --runner "$EV/runners/run_strict_no_echo_gate.py"
python3 scripts/ws45_patch_noecho_runner_forge_lock.py --runner "$EV/runners/run_behavior_transcript_probe.py"
python3 scripts/ws48_patch_v105_runner_identity.py --noecho-runner "$EV/runners/run_strict_no_echo_gate.py"
out="$EV/generated"
python3 scripts/ws40_generate_forge_provider.py --player-controller "$FORGE/forge-game/src/main/java/forge/game/player/PlayerController.java" --output-dir "$out" --forge-commit "$FORGE_COMMIT" --forge-tree "$FORGE_TREE"
python3 scripts/finalist_generate_forge_bootstrap.py --source qualification/providers/forge/gpl/Ws23ForgeBootstrap.java --output "$out/java/forge/game/player/Ws23ForgeBootstrap.java"
python3 scripts/ws40_apply_successor_state_overlay.py --provider "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java"
cp qualification/providers/forge/gpl/Ws40SuccessorState.java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws40_fix_successor_state_java.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws40_v103_native_stack_history.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws40_v103_native_revealed_state.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws40_v103_fix_combat_target_type.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws40_v103_lineage_target_resolution.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws40_v103_stack_observer_identity_projection.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws45_v104_exact_stack_target_identity.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws40_v103_native_combat_legal_surface.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws45_apply_generated_overlay.py --generated-dir "$out/java/forge/game/player" --strict-source qualification/providers/forge/gpl/Ws45StrictObservation.java
python3 scripts/ws45_patch_generated_gamestate_identity.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 scripts/ws45_extend_natural_observation.py --strict-java "$out/java/forge/game/player/Ws45StrictObservation.java"
python3 scripts/ws45_v104_nullable_knowledge_presence.py --strict-java "$out/java/forge/game/player/Ws45StrictObservation.java"
python3 scripts/ws48_v105_native_stack_modes.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java" --runner "$EV/runners/run_strict_no_echo_gate.py"
python3 scripts/ws45_v104_native_zero_counter_projection.py --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 candidate-qualification/ws48-forge-v1.0.5/ws48_behavior_provider_overlay.py --provider "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java" --state-java "$out/java/forge/game/player/Ws40SuccessorState.java"
python3 candidate-qualification/ws53-forge-convergence-native-progression/ws53_provider_overlay.py --provider "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java"
python3 candidate-qualification/ws55-forge-mandatory-decision-breadth/ws55_provider_overlay.py --provider "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java"
python3 candidate-qualification/ws62-forge-successor-requalification/ws62_provider_overlay.py --provider "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java"
python3 candidate-qualification/ws64-forge-a04-vertical-path-investigation/ws64_provider_overlay.py --provider "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java"
python3 candidate-qualification/ws68-forge-provider-transport-remediation/ws68_provider_overlay.py --provider "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java"
python3 candidate-qualification/ws77-forge-ghalta-covenant-provider-remediation/ws77_provider_overlay.py --provider "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java"
cp candidate-qualification/ws62-forge-successor-requalification/Ws62ConcessionTransport.java "$out/java/forge/game/player/Ws62ConcessionTransport.java"
! grep -REn 'import forge\.(ai|gui)|RemoteClientGuiGame|PlayerControllerAi|ComputerUtilMana|candidates\.get\(0\)|game\.findById\(expectedNativeId\)' "$out/java"
! grep -REn 'Propaganda|getAction\(\)\.concede|player\.concede\(\)|Player\.concede' "$out/java"
! grep -REn 'Ghalta|Covenant|Fireball|Primal Hunger' "$out/java"
! grep -Eq 'forge-(ai|gui)' "$REF/dependency-classpath.txt"
test -d "$FORGE/forge-game/target/classes/forge/game"
test -d "$FORGE/forge-core/target/classes/forge"
cp="$EV/classes:$FORGE/forge-game/target/classes:$FORGE/forge-core/target/classes:$(cat "$REF/dependency-classpath.txt")"
case "$cp" in
  *forge-66caae*|*/.ws48-r1e/forge-66caae*) echo "WS77_OLD_PIN_ON_CLASSPATH_FAIL_CLOSED" >&2; exit 1;;
esac
"$JAVA_HOME/bin/javac" -cp "$FORGE/forge-game/target/classes:$FORGE/forge-core/target/classes:$(cat "$REF/dependency-classpath.txt")" -d "$EV/classes" "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java" "$out/java/forge/game/player/Ws23ForgeBootstrap.java" "$out/java/forge/game/player/Ws40SuccessorState.java" "$out/java/forge/game/player/Ws45StrictObservation.java" "$out/java/forge/game/player/Ws62ConcessionTransport.java"
printf '%s:%s:%s:%s\n' "$EV/classes" "$FORGE/forge-game/target/classes" "$FORGE/forge-core/target/classes" "$(cat "$REF/dependency-classpath.txt")" > "$EV/provider.classpath"
sha256sum "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java" "$out/java/forge/game/player/Ws40SuccessorState.java" "$out/java/forge/game/player/Ws62ConcessionTransport.java" > "$EV/WS77_PROVIDER_DIGESTS.txt"
cat "$EV/WS77_PROVIDER_DIGESTS.txt"
echo WS77-CLEAN-BUILD-OK
