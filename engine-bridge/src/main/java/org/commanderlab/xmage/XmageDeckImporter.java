package org.commanderlab.xmage;

import mage.cards.decks.Deck;
import mage.cards.decks.DeckCardInfo;
import mage.cards.decks.DeckCardLists;
import mage.cards.decks.DeckValidatorError;
import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.cards.repository.CardScanner;
import mage.deck.Commander;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;
import java.util.regex.Pattern;

public final class XmageDeckImporter {

    private static final Pattern COMBINING_MARKS = Pattern.compile("\\p{M}+");

    public record ImportResult(
            String deckHandle,
            String deckId,
            String deckHash,
            int mainboardCount,
            int commanderCount
    ) {
    }

    public static final class ImportException extends RuntimeException {

        public ImportException(String message) {
            super(message);
        }

        public ImportException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    private enum RepositoryState {
        NEW,
        READY,
        POISONED
    }

    private static final Object REPOSITORY_LOCK = new Object();

    private static volatile RepositoryState repositoryState =
            RepositoryState.NEW;

    private static volatile Throwable repositoryFailure;

    private final Map<String, Deck> decksByHandle =
            new ConcurrentHashMap<>();

    public ImportResult importCommanderDeck(
            String deckId,
            String deckHash,
            List<String> requestedMainboard,
            List<String> requestedCommanders
    ) {
        String validatedDeckId =
                requireText(deckId, "deck_id");

        String validatedDeckHash =
                requireText(deckHash, "deck_hash");

        if (requestedMainboard == null) {
            throw new ImportException(
                    "INVALID_DECK: mainboard must not be null"
            );
        }

        if (requestedCommanders == null) {
            throw new ImportException(
                    "INVALID_DECK: commander_names must not be null"
            );
        }

        List<String> mainboard =
                new ArrayList<>(requestedMainboard);

        List<String> commanders =
                new ArrayList<>(requestedCommanders);

        if (commanders.size() < 1 || commanders.size() > 2) {
            throw new ImportException(
                    "INVALID_COMMANDER_COUNT: expected 1 or 2 commanders; "
                            + "observed " + commanders.size()
            );
        }

        int totalCards =
                mainboard.size() + commanders.size();

        if (totalCards != 100) {
            throw new ImportException(
                    "INVALID_DECK_SIZE: Commander deck must contain "
                            + "exactly 100 cards; observed "
                            + totalCards
            );
        }

        ensureRepositoryReady();

        DeckCardLists deckCardLists =
                new DeckCardLists();

        deckCardLists.setName(validatedDeckId);

        for (int index = 0; index < mainboard.size(); index++) {
            String oracleName =
                    requireText(
                            mainboard.get(index),
                            "mainboard[" + index + "]"
                    );

            deckCardLists
                    .getCards()
                    .add(resolveMechanicalCard(oracleName));
        }

        for (int index = 0; index < commanders.size(); index++) {
            String oracleName =
                    requireText(
                            commanders.get(index),
                            "commander_names[" + index + "]"
                    );

            /*
             * XMage Commander validation represents commander cards
             * in DeckCardLists.sideboard.
             */
            deckCardLists
                    .getSideboard()
                    .add(resolveMechanicalCard(oracleName));
        }

        Deck realDeck;

        try {
            /*
             * Real XMage cards only:
             * ignoreErrors = false
             * mockCards = false
             */
            realDeck =
                    Deck.load(
                            deckCardLists,
                            false,
                            false
                    );
        } catch (Exception exc) {
            throw new ImportException(
                    "XMAGE_DECK_LOAD_FAILED: "
                            + exc.getMessage(),
                    exc
            );
        }

        if (realDeck == null) {
            throw new ImportException(
                    "XMAGE_DECK_LOAD_FAILED: "
                            + "Deck.load returned null"
            );
        }

        Commander validator =
                new Commander();

        if (!validator.validate(realDeck)) {
            String details =
                    validator
                            .getErrorsListSorted()
                            .stream()
                            .map(
                                    XmageDeckImporter
                                            ::formatValidationError
                            )
                            .collect(
                                    Collectors.joining(" | ")
                            );

            if (details.isBlank()) {
                details =
                        "XMage Commander validator returned false "
                                + "without details";
            }

            throw new ImportException(
                    "COMMANDER_VALIDATION_FAILED: "
                            + details
            );
        }

        String deckHandle;

        do {
            deckHandle =
                    "xmage-deck-"
                            + UUID.randomUUID();
        } while (
                decksByHandle.putIfAbsent(
                        deckHandle,
                        realDeck
                ) != null
        );

        return new ImportResult(
                deckHandle,
                validatedDeckId,
                validatedDeckHash,
                mainboard.size(),
                commanders.size()
        );
    }

    Deck requireDeck(String deckHandle) {
        String validatedHandle =
                requireText(
                        deckHandle,
                        "deck_handle"
                );

        Deck deck =
                decksByHandle.get(validatedHandle);

        if (deck == null) {
            throw new ImportException(
                    "UNKNOWN_DECK_HANDLE: "
                            + validatedHandle
            );
        }

        return deck;
    }

    int storedDeckCount() {
        return decksByHandle.size();
    }

    private static DeckCardInfo resolveMechanicalCard(
            String oracleName
    ) {
        /*
         * Simulation runtime intentionally ignores the user's physical
         * printing. Any real XMage printing of the same mechanical card
         * is sufficient.
         *
         * returnAnySet=true limits lookup to one available printing.
         */
        CardInfo cardInfo =
                CardRepository.instance.findCard(
                        oracleName,
                        true
                );

        /*
         * Some XMage registrations use an ASCII spelling where current
         * Oracle/source data carries a diacritic (for example Gríma -> Grima).
         * This is deliberately narrower than fuzzy matching: only canonical
         * Unicode combining marks are ignored, and the fallback is accepted
         * only when exactly one engine card name has the same folded identity.
         */
        if (cardInfo == null) {
            String foldedRequested =
                    foldDiacritics(oracleName);

            List<String> equivalentNames =
                    CardRepository.instance
                            .getNames()
                            .stream()
                            .filter(
                                    engineName ->
                                            foldDiacritics(engineName)
                                                    .equals(foldedRequested)
                            )
                            .distinct()
                            .sorted()
                            .limit(2)
                            .toList();

            if (equivalentNames.size() > 1) {
                throw new ImportException(
                        "AMBIGUOUS_CARD_NAME_ALIAS: requested "
                                + oracleName
                                + " matches multiple XMage identities after "
                                + "diacritic folding: "
                                + equivalentNames
                );
            }

            if (equivalentNames.size() == 1) {
                cardInfo =
                        CardRepository.instance.findCard(
                                equivalentNames.get(0),
                                true
                        );
            }
        }

        if (cardInfo == null) {
            throw new ImportException(
                    "UNKNOWN_CARD_NAME: "
                            + oracleName
            );
        }

        /*
         * Fail closed if XMage resolves a genuinely different mechanical
         * identity. A unique diacritic-only spelling difference is accepted
         * because it binds to the same engine card registration. Set code and
         * collector number remain outside the simulation contract.
         */
        if (!oracleName.equals(cardInfo.getName())
                && !foldDiacritics(oracleName)
                        .equals(foldDiacritics(cardInfo.getName()))) {
            throw new ImportException(
                    "CARD_IDENTITY_MISMATCH: requested "
                            + oracleName
                            + " but XMage resolved "
                            + cardInfo.getName()
            );
        }

        return new DeckCardInfo(
                cardInfo.getName(),
                cardInfo.getCardNumber(),
                cardInfo.getSetCode()
        );
    }

    /**
     * Ensures the engine card repository is initialized exactly once per
     * process (fail closed on preinitialized-unverified or failed scans).
     * Shared with card materialization so every resolution path observes
     * identical readiness semantics.
     */
    static void ensureRepositoryReady() {
        RepositoryState current =
                repositoryState;

        if (current == RepositoryState.READY) {
            return;
        }

        if (current == RepositoryState.POISONED) {
            throw poisonedRepositoryException();
        }

        synchronized (REPOSITORY_LOCK) {
            if (repositoryState == RepositoryState.READY) {
                return;
            }

            if (repositoryState == RepositoryState.POISONED) {
                throw poisonedRepositoryException();
            }

            /*
             * CardScanner sets its own scanned flag before completing.
             * Therefore an externally preinitialized scanner cannot be
             * treated as verified B2 initialization.
             */
            if (CardScanner.scanned) {
                ImportException failure =
                        new ImportException(
                                "XMAGE_CARD_REPOSITORY_"
                                        + "PREINITIALIZED_UNVERIFIED"
                        );

                repositoryFailure = failure;
                repositoryState =
                        RepositoryState.POISONED;

                throw failure;
            }

            List<String> scannerErrors =
                    new ArrayList<>();

            try {
                CardScanner.scan(scannerErrors);
            } catch (RuntimeException | Error exc) {
                repositoryFailure = exc;
                repositoryState =
                        RepositoryState.POISONED;

                throw new ImportException(
                        "XMAGE_CARD_REPOSITORY_INIT_FAILED",
                        exc
                );
            }

            if (!scannerErrors.isEmpty()) {
                String details =
                        scannerErrors
                                .stream()
                                .limit(20)
                                .collect(
                                        Collectors.joining(" | ")
                                );

                ImportException failure =
                        new ImportException(
                                "XMAGE_CARD_REPOSITORY_SCAN_ERRORS"
                                        + " (count="
                                        + scannerErrors.size()
                                        + "): "
                                        + details
                        );

                repositoryFailure = failure;
                repositoryState =
                        RepositoryState.POISONED;

                throw failure;
            }

            repositoryState =
                    RepositoryState.READY;
        }
    }

    private static ImportException
            poisonedRepositoryException() {

        if (repositoryFailure == null) {
            return new ImportException(
                    "XMAGE_CARD_REPOSITORY_POISONED"
            );
        }

        return new ImportException(
                "XMAGE_CARD_REPOSITORY_POISONED",
                repositoryFailure
        );
    }

    private static String formatValidationError(
            DeckValidatorError error
    ) {
        String cardName =
                error.getCardName() == null
                        ? ""
                        : error.getCardName();

        return "type=" + error.getErrorType()
                + ",group=" + error.getGroup()
                + ",card=" + cardName
                + ",message=" + error.getMessage();
    }

    private static String foldDiacritics(String value) {
        return COMBINING_MARKS
                .matcher(
                        Normalizer.normalize(
                                value,
                                Normalizer.Form.NFD
                        )
                )
                .replaceAll("");
    }

    private static String requireText(
            String value,
            String fieldName
    ) {
        if (value == null || value.isBlank()) {
            throw new ImportException(
                    "INVALID_FIELD: "
                            + fieldName
                            + " must be nonblank"
            );
        }

        return value.trim();
    }
}