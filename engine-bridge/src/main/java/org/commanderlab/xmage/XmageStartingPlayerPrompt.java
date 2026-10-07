package org.commanderlab.xmage;

/**
 * The identities of the CR 103.2 starting-player prompt the compatibility
 * bridge actually answered, if it answered one.
 *
 * <p>{@code GameImpl.init} asks the choosing player to select the starting
 * player. When that answer is refused, the engine falls back to the first
 * available player in a pod of three or more (see
 * {@code GameImpl.init}), and the established {@code starting_player_id}
 * readback cannot tell that fallback apart from a real answer. The bridge
 * therefore records the chooser it answered for and the player it selected, so
 * the caller can require both to resolve to the declared seat (#572).</p>
 *
 * <p>An unanswered prompt leaves both identities null; that is a distinct,
 * non-credited state, never a default.</p>
 */
final class XmageStartingPlayerPrompt {

    private String chooserId;
    private String chosenId;

    /** Records the first answer; a second answer is an engine-contract violation. */
    synchronized void recordAnswer(String chooserId, String chosenId) {
        if (chooserId == null || chosenId == null) {
            throw new IllegalArgumentException("a prompt answer requires both identities");
        }
        if (this.chooserId != null || this.chosenId != null) {
            throw new IllegalStateException(
                    "the starting-player prompt was answered more than once"
            );
        }
        this.chooserId = chooserId;
        this.chosenId = chosenId;
    }

    synchronized String chooserId() {
        return chooserId;
    }

    synchronized String chosenId() {
        return chosenId;
    }
}
