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
// under ../evidence/ (relative to this project dir). Every JavaExec forks a
// fresh JVM, so separate invocations are separate processes (U22 relies on this).
fun probeTask(name: String, main: String, vararg args: String) {
    tasks.register<JavaExec>(name) {
        group = "rq-a2"
        mainClass.set(main)
        classpath = sourceSets["main"].runtimeClasspath
        args(args.toList())
    }
}

val evDir = "/home/moeen/code/rq-a2-argentum-comparable-qualification/research/candidate-qualification/argentum/rq-a2/evidence"

probeTask("rqA2Replay", "rqa2.ReplayProbeKt", "$evDir/ARGENTUM_REPLAY_ROUNDTRIP.json")
probeTask("rqA2ReplayNeg", "rqa2.ReplayNegativeControlsKt", "$evDir/ARGENTUM_REPLAY_NEGATIVE_CONTROLS.json")
probeTask("rqA2AbilityId", "rqa2.AbilityIdProbeKt", "record", "S1-study", "$evDir/u22/S1-A.replay", "$evDir/u22/S1-A.digests.json")
probeTask("rqA2HiddenInfo", "rqa2.HiddenInfoProbeKt", "$evDir/ARGENTUM_HIDDEN_INFO_ADVERSARY.json")
probeTask("rqA2FivePlayer", "rqa2.FivePlayerProbeKt", "$evDir/ARGENTUM_FIVE_PLAYER_PROBE.json")
probeTask("rqA2RulesDense", "rqa2.RulesDenseProbeKt", "$evDir/ARGENTUM_RULES_DENSE_PROBES.json")
probeTask("rqA2Freshness", "rqa2.FreshnessProbeKt", "$evDir/ARGENTUM_DECISION_FRESHNESS.json")

// U22 cross-process matrix: each task execution forks a fresh JVM.
for (spec in listOf("S1-study", "S2-activation", "S3-storm", "S4-ping")) {
    val tag = spec.substringBefore("-")
    for (run in listOf("A", "B")) {
        probeTask("u22rec$tag$run", "rqa2.AbilityIdProbeKt",
            "record", spec, "$evDir/u22/$tag-$run.replay", "$evDir/u22/$tag-$run.digests.json")
    }
    probeTask("u22rep${tag}Apinned", "rqa2.AbilityIdProbeKt",
        "replay", "$evDir/u22/$tag-A.replay", "$evDir/u22/$tag-A.replay.pinned.json")
    probeTask("u22rep${tag}Aunpinned", "rqa2.AbilityIdProbeKt",
        "replayUnpinned", "$evDir/u22/$tag-A.replay", "$evDir/u22/$tag-A.replay.unpinned.json")
}
probeTask("u22diffS3", "rqa2.AbilityIdProbeKt",
    "diffself", "S3-storm", "$evDir/u22/S3-diffself.json")
