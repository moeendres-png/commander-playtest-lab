package org.commanderlab.xmage;

import com.google.gson.*;
import org.commanderlab.xmage.XmageDeckImporter;
import java.nio.file.*;
import java.util.*;

/** Local-only inputs; only aggregate counts go to stdout. */
public final class PrivateImportProbe {
    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        JsonArray names = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonArray();
        int imported = 0;
        List<Map<String,String>> failures = new ArrayList<>();
        for (JsonElement item : names) {
            String name = item.getAsString();
            List<String> main = new ArrayList<>(Collections.nCopies(98, "Forest"));
            main.add(name);
            try {
                XmageDeckImporter importer = new XmageDeckImporter();
                var result = importer.importCommanderDeck("local-probe", "local-probe", main, List.of("Kenrith, the Returned King"));
                var deck = importer.requireDeck(result.deckHandle());
                if (deck.getCards().size() != 99 || deck.getSideboard().size() != 1)
                    throw new IllegalStateException("Unexpected concrete deck size");
                imported++;
            } catch (RuntimeException e) {
                failures.add(Map.of("name",name,"error",e.getMessage()));
            }
        }
        boolean unknownRejected = false;
        boolean identityMismatchRejected = false;
        for (String control : List.of("CPL fabricated negative control 1227", "Forest // CPL wrong back identity")) {
            List<String> main = new ArrayList<>(Collections.nCopies(98, "Forest")); main.add(control);
            try { new XmageDeckImporter().importCommanderDeck("control", "control", main, List.of("Kenrith, the Returned King")); }
            catch (XmageDeckImporter.ImportException e) {
                if (control.startsWith("CPL")) unknownRejected = e.getMessage().startsWith("UNKNOWN_CARD_NAME");
                else identityMismatchRejected = e.getMessage().startsWith("CARD_IDENTITY_MISMATCH");
            }
        }
        Map<String,Object> report = new LinkedHashMap<>();
        report.put("attempted", names.size()); report.put("imported",imported); report.put("failures",failures);
        report.put("unknown_name_rejected",unknownRejected); report.put("identity_mismatch_rejected",identityMismatchRejected);
        Files.writeString(Path.of(args[1]), new GsonBuilder().setPrettyPrinting().create().toJson(report)+"\n");
        System.out.println("attempted="+names.size()+"; imported="+imported+"; failed="+failures.size()+"; controls="+(unknownRejected&&identityMismatchRejected));
        System.exit(failures.isEmpty() && unknownRejected && identityMismatchRejected ? 0 : 1);
    }
}
