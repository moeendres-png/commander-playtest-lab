import mage.cards.repository.CardInfo;
import mage.cards.repository.CardRepository;
import mage.cards.repository.CardScanner;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;

public class CardCheck {
    static String fold(String s) {
        return Normalizer.normalize(s, Normalizer.Form.NFD).replaceAll("\\p{M}", "");
    }
    public static void main(String[] a) throws Exception {
        List<String> errs = new ArrayList<>();
        CardScanner.scan(errs);
        int missing = 0, total = 0;
        for (String n : Files.readAllLines(Paths.get(a[0]))) {
            if (n.isBlank()) continue;
            total++;
            CardInfo ci = CardRepository.instance.findCard(n, true);
            if (ci == null) {
                String f = fold(n);
                if (!f.equals(n)) ci = CardRepository.instance.findCard(f, true);
            }
            if (ci == null) { missing++; System.out.println("MISSING\t" + n); }
        }
        System.out.println("SUMMARY total=" + total + " missing=" + missing + " scanErrors=" + errs.size());
    }
}
