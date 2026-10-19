package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

import java.util.Set;

/**
 * K3: PrincipalView contract leak test.
 *
 * <p>Verifies that two principals viewing the same game state receive views
 * that differ ONLY in declared private fields. If a private field appears in
 * an opponent's view, the test fails (red).
 */
class PrincipalViewLeakTest {

    private static final String ALICE = "alice-principal-id";
    private static final String BOB = "bob-principal-id";

    @Test
    void publicFieldsAreNotPrivate() {
        for (String field : PrincipalView.PUBLIC_FIELDS) {
            assertTrue(!PrincipalView.isPrivateField(field),
                    "Public field '" + field + "' must not be classified as private");
        }
    }

    @Test
    void privateFieldsAreNotPublic() {
        for (String field : PrincipalView.PRIVATE_FIELDS) {
            assertTrue(!PrincipalView.isPublicField(field),
                    "Private field '" + field + "' must not be classified as public");
        }
    }

    @Test
    void viewingOwnStateAllowsPrivateFields() {
        // Alice viewing her own state: private fields are OK
        Set<String> aliceView = Set.of("battlefield", "hand", "life");
        assertDoesNotThrow(() ->
                PrincipalView.assertNoLeak(ALICE, aliceView, ALICE)
        );
    }

    @Test
    void opponentViewMustNotContainPrivateFields() {
        // Bob viewing Alice's state: 'hand' is private → must throw
        Set<String> bobViewOfAlice = Set.of("battlefield", "hand", "life");
        IllegalStateException ex = assertThrows(
                IllegalStateException.class,
                () -> PrincipalView.assertNoLeak(BOB, bobViewOfAlice, ALICE)
        );
        assertTrue(ex.getMessage().contains("PRINCIPAL_VIEW_LEAK"));
        assertTrue(ex.getMessage().contains("hand"));
    }

    @Test
    void opponentViewWithOnlyPublicFieldsPasses() {
        // Bob viewing Alice's state with only public fields: OK
        Set<String> bobViewOfAlice = Set.of("battlefield", "graveyard", "life");
        assertDoesNotThrow(() ->
                PrincipalView.assertNoLeak(BOB, bobViewOfAlice, ALICE)
        );
    }

    @Test
    void twoPrincipalsDifferOnlyInPrivateFields() {
        // Simulate: Alice and Bob view the same game state
        // Alice's view of her own hand (private) vs Bob's view (no hand)
        Set<String> aliceView = Set.of("battlefield", "hand", "library", "life");
        Set<String> bobView = Set.of("battlefield", "life"); // no hand, no library

        // The difference must be subset of PRIVATE_FIELDS
        Set<String> diff = new java.util.HashSet<>(aliceView);
        diff.removeAll(bobView);
        for (String field : diff) {
            assertTrue(PrincipalView.isPrivateField(field),
                    "View difference contains non-private field: '" + field + "' — " +
                    "views must differ ONLY in declared private fields");
        }
    }
}
