package org.commanderlab.xmage;

import java.util.ArrayList;
import java.util.List;

/**
 * WS60 singleton Commander deck construction.
 *
 * <p>Every deck is exactly 100 cards, singleton except basics, with color
 * identity covered by its commander(s). The importer re-validates all of
 * this through XMage's Commander validator; these builders fail fast on
 * count mistakes before import.</p>
 */
final class Ws60Decks {

    private Ws60Decks() {
    }

    /** Builds a mainboard from alternating (name, count) pairs. */
    static List<String> mainboard(Object... nameAndCount) {
        if (nameAndCount.length % 2 != 0) {
            throw new IllegalArgumentException("name/count pairs required");
        }
        List<String> out = new ArrayList<>();
        for (int i = 0; i < nameAndCount.length; i += 2) {
            String name = (String) nameAndCount[i];
            int count = (Integer) nameAndCount[i + 1];
            for (int copy = 0; copy < count; copy++) {
                out.add(name);
            }
        }
        return List.copyOf(out);
    }

    static Ws60Driver.SeatDeck seat(List<String> commanders, List<String> mainboard) {
        if (mainboard.size() + commanders.size() != 100) {
            throw new IllegalArgumentException("deck must total 100: main=" + mainboard.size()
                    + " commanders=" + commanders.size());
        }
        return new Ws60Driver.SeatDeck(List.copyOf(commanders), mainboard);
    }

    static List<String> basics(String land, int count) {
        List<String> out = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            out.add(land);
        }
        return out;
    }

    // ------------------------------------------------------------------
    // Commanders (all implemented; none Commander-banned; partner pairs
    // verified with PartnerAbility).
    // ------------------------------------------------------------------

    static final String THRASIOS = "Thrasios, Triton Hero";
    static final String TYMNA = "Tymna the Weaver";
    static final String ROGRAKH = "Rograkh, Son of Rohgahh";
    static final String KRAUM = "Kraum, Ludevic's Opus";
    static final String TANA = "Tana, the Bloodsower";
    static final String IKRA = "Ikra Shidiqi, the Usurper";
    static final String GHALTA_PRIMAL = "Ghalta, Primal Hunger";
    static final String GHALTA_TYRANT = "Ghalta, Stampede Tyrant";
    static final String ISHAI = "Ishai, Ojutai Dragonspeaker";
    static final String AYARA = "Ayara, First of Locthwain";

    /** Idle single-color seat: 99 basics + matching commander (never cast). */
    static Ws60Driver.SeatDeck idle(String land, String commander) {
        return seat(List.of(commander), basics(land, 99));
    }
}
