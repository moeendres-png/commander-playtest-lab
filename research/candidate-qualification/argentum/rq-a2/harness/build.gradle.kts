import java.nio.file.Paths
import kotlin.io.path.readLines
import java.io.File

// RQ-A2 external qualification harness. CPL-side only: it compiles against
// candidate jars built at the exact lock plus their dumped runtime classpaths.
// It never adds sources to the candidate checkout.
plugins {
    kotlin("jvm") version "2.4.0"
}

repositories {
    mavenCentral()
}

kotlin {
    jvmToolchain(21)
}

// Candidate dependency surface: union of dumped runtime classpaths (game-server
// covers engine/sdk/sets/eras/Spring/kotlinx; gym adds the gym module) plus the
// rules-engine test-fixtures jar (TestCards/GameTestDriver support types).
val argentumSrc = "/tmp/rq-a2-argentum-src"
val cpDumps = listOf(
    "$argentumSrc/game-server/build/rq-a2-classpath.txt",
    "$argentumSrc/gym/build/rq-a2-classpath.txt"
).flatMap { Paths.get(it).readLines() }
    .map { it.trim() }
    .filter { it.isNotEmpty() && File(it).exists() }
    .distinct()

dependencies {
    cpDumps.forEach { implementation(files(it)) }
    implementation(files("$argentumSrc/rules-engine/build/libs/rules-engine-test-fixtures.jar"))
}

tasks.withType<JavaExec>().configureEach {
    // Probes must be hermetic: same-process reruns must not share static state.
    jvmArgs("-Djava.awt.headless=true")
}

// One runnable task per probe main. Each writes machine-readable evidence JSON
// under ../evidence/ (relative to this project dir).
fun probeTask(name: String, main: String, outFile: String) {
    tasks.register<JavaExec>(name) {
        group = "rq-a2"
        mainClass.set(main)
        classpath = sourceSets["main"].runtimeClasspath
        args(outFile)
    }
}

probeTask("rqA2Replay", "rqa2.ReplayProbeKt", "../evidence/ARGENTUM_REPLAY_ROUNDTRIP.json")
probeTask("rqA2Debug", "rqa2.DebugMainKt", "../evidence/ARGENTUM_DEBUG.json")
probeTask("rqA2ReplayNeg", "rqa2.ReplayNegativeControlsKt", "../evidence/ARGENTUM_REPLAY_NEGATIVE_CONTROLS.json")
probeTask("rqA2AbilityId", "rqa2.AbilityIdProbeKt", "../evidence/ARGENTUM_ABILITY_ID_PROBE.json")
probeTask("rqA2HiddenInfo", "rqa2.HiddenInfoProbeKt", "../evidence/ARGENTUM_HIDDEN_INFO_ADVERSARY.json")
probeTask("rqA2FivePlayer", "rqa2.FivePlayerProbeKt", "../evidence/ARGENTUM_FIVE_PLAYER_PROBE.json")
probeTask("rqA2RulesDense", "rqa2.RulesDenseProbeKt", "../evidence/ARGENTUM_RULES_DENSE_PROBES.json")
probeTask("rqA2Freshness", "rqa2.FreshnessProbeKt", "../evidence/ARGENTUM_DECISION_FRESHNESS.json")
