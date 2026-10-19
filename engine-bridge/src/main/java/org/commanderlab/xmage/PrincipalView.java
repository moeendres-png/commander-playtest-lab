package org.commanderlab.xmage;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * Central contract for principal-scoped views.
 *
 * <p>A PrincipalView defines exactly what a viewing principal may see in a game
 * state. Fields are classified as:
 * <ul>
 *   <li>PUBLIC: visible to all principals (e.g., battlefield, graveyard, life totals)</li>
 *   <li>PRIVATE: visible only to the owning principal (e.g., hand, library order, face-down cards)</li>
 * </ul>
 *
 * <p>The leak test (PrincipalViewLeakTest) verifies that two principals viewing
 * the same game state receive views that differ ONLY in PRIVATE fields. If a
 * PRIVATE field appears in an opponent's view, the test fails.
 *
 * <p>This is the Java-side counterpart to the Python
 * {@code FullGameHiddenInformationAudit} (which verifies at runtime per decision).
 */
public final class PrincipalView {

    /**
     * Fields that are public (visible to all principals).
     * These must never contain hidden information.
     */
    public static final Set<String> PUBLIC_FIELDS = Collections.unmodifiableSet(new HashSet<>(Set.of(
            // Board state (public)
            "battlefield",
            "graveyard",
            "exile",
            "command",
            "stack",
            // Player public state
            "life",
            "poison_counters",
            "commander_damage",
            // Game public state
            "active_player_id",
            "priority_player_id",
            "turn_number",
            "phase",
            "step"
    )));

    /**
     * Fields that are private (visible only to the owning principal).
     * These must NEVER appear in an opponent's view.
     */
    public static final Set<String> PRIVATE_FIELDS = Collections.unmodifiableSet(new HashSet<>(Set.of(
            // Hidden zones
            "hand",
            "library",
            // Face-down permanents (morph, etc.)
            "face_down_cards",
            // Private decision context
            "legal_options_full",
            "private_game_log"
    )));

    private PrincipalView() {
        // Utility class
    }

    /**
     * Returns true if the field is declared as private.
     */
    public static boolean isPrivateField(String fieldName) {
        return PRIVATE_FIELDS.contains(fieldName);
    }

    /**
     * Returns true if the field is declared as public.
     */
    public static boolean isPublicField(String fieldName) {
        return PUBLIC_FIELDS.contains(fieldName);
    }

    /**
     * Validates that a view for {@code viewerId} does not contain private fields
     * belonging to another principal.
     *
     * @param viewerId the principal viewing the state
     * @param viewFieldNames the field names present in the view
     * @param ownerId the principal who owns the private fields (null if viewing own state)
     * @throws IllegalStateException if a leak is detected
     */
    public static void assertNoLeak(String viewerId, Set<String> viewFieldNames, String ownerId) {
        if (viewerId == null || ownerId == null || viewerId.equals(ownerId)) {
            // Viewing own state: private fields are allowed
            return;
        }
        for (String field : viewFieldNames) {
            if (isPrivateField(field)) {
                throw new IllegalStateException(
                        "PRINCIPAL_VIEW_LEAK: private field '" + field +
                        "' visible to viewer " + viewerId +
                        " (owner: " + ownerId + ")"
                );
            }
        }
    }
}
