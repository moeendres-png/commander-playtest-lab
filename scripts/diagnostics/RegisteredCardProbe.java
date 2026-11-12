import com.google.gson.GsonBuilder;
import mage.cards.Card;
import mage.cards.CardImpl;
import mage.cards.CardSetInfo;
import mage.cards.ExpansionSet;
import mage.cards.Sets;
import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.cards.repository.CardScanner;
import mage.constants.Rarity;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** Local diagnostic only: registration/construction is not game behavior. */
public final class RegisteredCardProbe {
    private static boolean matchesResolvedIdentity(CardInfo info, Card card) {
        return info != null && card != null && info.getName().equals(card.getName());
    }

    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        if (args.length < 2) throw new IllegalArgumentException(
            "usage: RegisteredCardProbe <report-path> <engine-commit resolved from config/rules_engines.json>");
        if (Files.exists(Path.of("db"))) throw new IllegalStateException("Fresh DB required");
        List<String> scanErrors = new ArrayList<>();
        CardScanner.scan(scanErrors);
        Map<String,Object> report = new LinkedHashMap<>();
        report.put("measured_at", java.time.Instant.now().toString());
        report.put("engine_commit", args[1]);
        report.put("evidence", "LOCAL_OBSERVED_REGISTRATION_AND_CONSTRUCTION_ONLY");
        report.put("scan_errors", scanErrors);
        Map<String,Object> sets = new TreeMap<>();
        int setFailures = 0;
        for (String code : List.of("ECL", "FRA", "SPM")) {
            ExpansionSet set = Objects.requireNonNull(Sets.getInstance().get(code), code);
            List<String> failures = new ArrayList<>();
            Set<String> names = new TreeSet<>();
            int count = 0;
            for (ExpansionSet.SetCardInfo entry : set.getSetCardInfo()) {
                names.add(entry.getName()); count++;
                List<String> errors = new ArrayList<>();
                Card card = CardImpl.createCard(entry.getCardClass(), new CardSetInfo(
                    entry.getName(), code, entry.getCardNumber(), entry.getRarity(), entry.getGraphicInfo()), errors);
                CardInfo info = CardRepository.instance.findCard(code, entry.getCardNumber(), false);
                if (card == null || !errors.isEmpty() || info == null || info.createCard() == null
                        || !entry.getName().equals(card.getName()) || !entry.getName().equals(info.getName())) {
                    failures.add(entry.getName()+":"+entry.getCardNumber()+":"+errors);
                }
            }
            setFailures += failures.size();
            sets.put(code, Map.of("printing_rows",count,"distinct_names",names.size(),"failures",failures));
        }
        report.put("sets", sets);
        List<Map<String,Object>> cards = new ArrayList<>();
        for (String name : new TreeSet<>(CardRepository.instance.getNames())) {
            CardInfo info = CardRepository.instance.findCard(name, true);
            Card card = info == null ? null : info.createCard();
            Map<String,Object> row = new LinkedHashMap<>();
            row.put("name", name);
            row.put("resolved_name", info == null ? null : info.getName());
            row.put("constructed_name", card == null ? null : card.getName());
            row.put("constructed", card != null);
            row.put("identity_matches", matchesResolvedIdentity(info, card));
            cards.add(row);
        }
        report.put("cards", cards);
        boolean unknownRejected = CardRepository.instance.findCard("CPL fabricated negative control 1227", true) == null;
        List<String> constructorErrors = new ArrayList<>();
        Card invalid = CardImpl.createCard(String.class,
            new CardSetInfo("CPL invalid constructor", "ECL", "1227", Rarity.COMMON), constructorErrors);
        boolean invalidRejected = invalid == null && !constructorErrors.isEmpty();
        CardInfo forest = CardRepository.instance.findCard("Forest", true);
        CardInfo island = CardRepository.instance.findCard("Island", true);
        boolean matchingIdentityAccepted = matchesResolvedIdentity(forest, forest.createCard());
        boolean wrongIdentityRejected = !matchesResolvedIdentity(forest, island.createCard());
        report.put("negative_controls", Map.of("unknown_name_rejected",unknownRejected,
            "bad_constructor_rejected",invalidRejected,"wrong_constructed_identity_rejected",wrongIdentityRejected,
            "matching_identity_accepted",matchingIdentityAccepted));
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().serializeNulls().create().toJson(report)+"\n");
        System.out.println("public names="+cards.size()+"; scan errors="+scanErrors.size()+"; controls="+(unknownRejected&&invalidRejected));
        boolean allConstructed = cards.stream().allMatch(row -> Boolean.TRUE.equals(row.get("constructed"))
            && Boolean.TRUE.equals(row.get("identity_matches")));
        System.exit(scanErrors.isEmpty() && setFailures == 0 && allConstructed && unknownRejected
            && invalidRejected && wrongIdentityRejected && matchingIdentityAccepted ? 0 : 1);
    }
}
