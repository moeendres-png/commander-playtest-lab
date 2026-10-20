package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.jar.JarEntry;
import java.util.jar.JarFile;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import org.junit.jupiter.api.Test;

/**
 * K1 (XMage architecture transfer): D17 — pilots run out of process; no foreign
 * decision-making code may run inside the engine JVM.
 *
 * <p>XMage upstream ships AI players ({@code mage-player-ai},
 * {@code mage-player-ai-mad}, {@code mage-player-ai-mcts}) as part of its
 * distribution. If any of those artifacts ever lands on the bridge classpath,
 * an engine-internal AI could silently substitute for external decision
 * control. This ratchet fails the build the moment an AI player class or a
 * player-ai dependency appears on the bridge classpath.
 *
 * <p>Test-only addition: no main-source change, the packaged bridge JAR is
 * unaffected.
 */
class BridgeClasspathTest {

    /**
     * Classpath entry name patterns that must never resolve inside the bridge
     * JVM. Kept deliberately narrow: {@code mage/players} (the engine's own
     * player API, including our {@code XmageBridgePlayer}) is fine; the
     * upstream AI packages live under {@code mage/player/ai}.
     */
    private static final List<Pattern> FORBIDDEN_CLASS_PATTERNS = List.of(
            Pattern.compile("^mage/player/ai/.*\\.class$"),
            Pattern.compile("^mage/player/[^/]*ComputerPlayer[^/]*\\.class$"),
            Pattern.compile("^mage/player/[^/]*MCTS[^/]*\\.class$")
    );

    /**
     * Direct-dependency artifact fragments that must never appear in the
     * bridge pom. Catches the declaration even before it resolves.
     */
    private static final List<Pattern> FORBIDDEN_POM_PATTERNS = List.of(
            Pattern.compile("(?i)<artifactId>\\s*mage-player-ai[^<]*</artifactId>")
    );

    @Test
    void noAiPlayerClassesOnBridgeClasspath() throws IOException {
        List<String> violations = new ArrayList<>();
        String classpath = System.getProperty("java.class.path", "");
        for (String entry : classpath.split(Pattern.quote(File.pathSeparator))) {
            if (entry.isBlank()) {
                continue;
            }
            Path path = Path.of(entry);
            if (Files.isDirectory(path)) {
                scanDirectory(path, path, violations);
            } else if (entry.endsWith(".jar") && Files.isRegularFile(path)) {
                scanJar(path, violations);
            }
        }
        assertTrue(violations.isEmpty(),
                () -> "AI player classes on bridge classpath (D17 violation): " + violations);
    }

    @Test
    void noAiPlayerDependencyInPom() throws IOException {
        // surefire's working directory is not guaranteed to be the module
        // basedir, so locate pom.xml from the test-classes directory instead.
        Path testClasses;
        try {
            testClasses = Path.of(
                    BridgeClasspathTest.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        } catch (Exception e) {
            throw new IOException("cannot locate test-classes directory", e);
        }
        Path pom = testClasses.getParent().getParent().resolve("pom.xml");
        assertTrue(Files.isRegularFile(pom), () -> "expected engine-bridge pom.xml at " + pom);
        String text = Files.readString(pom);
        List<String> hits = new ArrayList<>();
        for (Pattern pattern : FORBIDDEN_POM_PATTERNS) {
            if (pattern.matcher(text).find()) {
                hits.add(pattern.pattern());
            }
        }
        assertTrue(hits.isEmpty(), () -> "forbidden AI dependency declared in pom.xml: " + hits);
    }

    private static void scanDirectory(Path root, Path dir, List<String> violations) throws IOException {
        try (Stream<Path> stream = Files.list(dir)) {
            for (Path child : (Iterable<Path>) stream::iterator) {
                if (Files.isDirectory(child)) {
                    scanDirectory(root, child, violations);
                } else if (child.getFileName().toString().endsWith(".class")) {
                    checkEntry(root.relativize(child).toString().replace(File.separatorChar, '/'), violations);
                }
            }
        }
    }

    private static void scanJar(Path jar, List<String> violations) throws IOException {
        try (JarFile jarFile = new JarFile(jar.toFile())) {
            Enumeration<JarEntry> entries = jarFile.entries();
            while (entries.hasMoreElements()) {
                checkEntry(entries.nextElement().getName(), violations);
            }
        }
    }

    private static void checkEntry(String entryName, List<String> violations) {
        for (Pattern pattern : FORBIDDEN_CLASS_PATTERNS) {
            if (pattern.matcher(entryName).matches()) {
                violations.add(entryName);
                return;
            }
        }
    }
}
