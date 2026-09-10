#!/bin/bash
# WS50 Checkpoint A: reproduce the R1e provider build from THIS worktree's sources.
# Faithful local mirror of .github/workflows/ws48-v105-behavior-transcript-probe.yml
# "Build Forge and WS48 behavior provider" step, plus ci_mirror_build.sh lineage.
# Forge checkout is consumed READ-ONLY (no mvn, no writes; jars prebuilt at R1e).
set -euo pipefail
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
WS=/home/moeen/code/ws50-forge-decision-sequence-slice
FORGE=/home/moeen/.ws48-r1e/forge-66caae16015bd403bc0a52fa6689afb5508f74d0
EV=/home/moeen/code/ws50-forge-decision-sequence-slice/candidate-qualification/ws50-forge-decision-sequence/ev-checkpoint-a
FORGE_COMMIT=66caae16015bd403bc0a52fa6689afb5508f74d0
FORGE_TREE=40fc8f29ce4de31a964972461db2b48b4221e07f
export FORGE_COMMIT FORGE_TREE
mkdir -p "$EV/runners" "$EV/generated" "$EV/classes" "$EV/contract"
cd "$WS"
test "$(git rev-parse HEAD)" = "10a7f8f6ebc5be2b2a89d3d019f0c16659cadc7d"
# Stage immutable WS47 contract from the frozen-contract ref (read-only git show).
git show 192e2b77c0625ad26905bd0ee8dcc3f44a5796c8:qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json > "$EV/contract/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json"
git show 192e2b77c0625ad26905bd0ee8dcc3f44a5796c8:qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json > "$EV/contract/WS47_PROVIDER_DENOMINATOR_107.json"
test "$(sha256sum "$EV/contract/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json" | awk '{print $1}')" = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"
python3 -m py_compile candidate-qualification/ws48-forge-v1.0.5/ws48_behavior_provider_overlay.py
python3 -m py_compile candidate-qualification/ws48-forge-v1.0.5/run_behavior_transcript_probe.py
python3 -m py_compile candidate-qualification/ws48-forge-v1.0.5/build_behavior_coverage.py
cp candidate-qualification/ws45-forge-v1.0.4/run_strict_no_echo_gate.py "$EV/runners/run_strict_no_echo_gate.py"
cp candidate-qualification/ws48-forge-v1.0.5/run_behavior_transcript_probe.py "$EV/runners/run_behavior_transcript_probe.py"
python3 scripts/ws45_patch_noecho_runner_lineage.py --runner "$EV/runners/run_strict_no_echo_gate.py"
python3 scripts/ws45_patch_noecho_runner_forge_lock.py --runner "$EV/runners/run_strict_no_echo_gate.py"
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
! grep -REn 'import forge\.(ai|gui)|RemoteClientGuiGame|PlayerControllerAi|ComputerUtilMana|candidates\.get\(0\)|game\.findById\(expectedNativeId\)' "$out/java"
cp="$FORGE/forge-game/target/classes:$FORGE/forge-core/target/classes:$(cat /home/moeen/.ws48-r1e/ev/dependency-classpath.txt)"
"$JAVA_HOME/bin/javac" -cp "$cp" -d "$EV/classes" "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java" "$out/java/forge/game/player/Ws23ForgeBootstrap.java" "$out/java/forge/game/player/Ws40SuccessorState.java" "$out/java/forge/game/player/Ws45StrictObservation.java"
printf '%s:%s:%s:%s\n' "$EV/classes" "$FORGE/forge-game/target/classes" "$FORGE/forge-core/target/classes" "$(cat /home/moeen/.ws48-r1e/ev/dependency-classpath.txt)" > "$EV/provider.classpath"
sha256sum "$out/java/forge/game/player/Ws23ForgeVerticalProvider.java" "$out/java/forge/game/player/Ws40SuccessorState.java" > "$EV/WS50_PROVIDER_DIGESTS.txt"
cat "$EV/WS50_PROVIDER_DIGESTS.txt"
echo WS50-CHECKPOINT-A-BUILD-OK
