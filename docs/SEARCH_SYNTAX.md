# Studio-Suchsyntax (Pool- und Tierlisten-Suche)

Die Kartensuche im **Deckbau-Pool** (`index.html`, `#q`) und in der **Tierliste** (`tierliste.html`, `#q`) nutzt `src/commander_lab/studio/static/search.js` (`StudioSearch`).

Solange keine Feld-Operatoren, Anführungszeichen oder Negationen (`-`) verwendet werden, arbeitet die Suche als reine Freitext-Rangsuche:

1. **Rang 0:** Exakter Kartenname (`Sol Ring`)
2. **Rang 1:** Kartenname beginnt mit der Eingabe (`Sol Ringlet`)
3. **Rang 2:** Ein Wort im Kartennamen beginnt mit der Eingabe (`Arcane Sol Ringer`, `Zealous Sol Ringer`)
4. **Rang 3:** Kartenname enthält die Eingabe (`Awesol Ring Pack`)
5. **Rang 4:** Typenzeile oder Oracle-Text enthält die Eingabe (`Thran Dynamo`)

Innerhalb desselben Rangs wird alphabetisch nach Kartenname sortiert.

---

## Unterstützte Felder und Operatoren

Mehrere Ausdrücke werden standardmäßig mit **UND** verknüpft und können mit `or`, Klammern `(...)`, Gruppen-Negation `-(...)` sowie Freitext-Begriffen kombiniert werden (z. B. `(t:artifact or t:creature) mv<=2 -(t:land or r:removal)`).

Die Operator-Präzedenz ist fest definiert als: **Klammern `(...)` > Negation `-` > UND (Leerzeichen) > `or`**.

| Feld / Kürzel | Bedeutung | Erlaubte Operatoren | Beispiele |
| :--- | :--- | :--- | :--- |
| `t:`, `type:`, `typ:` | Typenzeile / Kartengruppe (inkl. deutsche Aliase wie `kreatur`, `spontanzauber`, `hexerei`, `artefakt`, `verzauberung`, `land`) | `:`, `=`, `!=` | `t:creature`, `t:elf`, `t:kreatur`, `-t:land` |
| `subtype:`, `sub:`, `untertyp:` | Untertyp nach dem Gedankenstrich der Typenzeile (`none` / `keine` für Karten ohne Untertyp) | `:`, `=`, `!=` | `subtype:elf`, `sub:druid`, `-subtype:human` |
| `super:`, `supertype:`, `übertyp:` | Obertyp vor dem Haupttyp (`basic`, `legendary`, `snow`, `world`, `ongoing`; auch `legende`, `standard`, `schnee`) | `:`, `=`, `!=` | `super:legendary`, `super:basic`, `-super:legendary` |
| `kw:`, `keyword:`, `keywords:` | Scryfall-Schlüsselwortfähigkeit (`none` / `keine` für Karten ohne Schlüsselwörter) | `:`, `=`, `!=` | `kw:flying`, `kw:vigilance`, `-kw:trample` |
| `o:`, `oracle:`, `text:` | Oracle-Regeltext (Teilwort oder Phrase in `"..."`) | `:`, `=`, `!=` | `o:flash`, `o:"draw a card"` |
| `n:`, `name:` | Kartenname | `:`, `=`, `!=` | `n:chulane`, `n:"teller of tales"` |
| `r:`, `role:`, `rolle:`, `fn:` | Funktionsrolle der Karte (`none` / `keine` / `-` für Karten ohne Rolle) | `:`, `=`, `!=` | `r:ramp`, `r:draw`, `r:removal`, `r:none` |
| `otag:`, `cat:`, `category:` | Oracle-Tag / Kategorie / Funktionsrolle (inkl. Original-Tagger-Tag) | `:`, `=`, `!=` | `otag:ramp`, `cat:card-draw`, `-otag:removal` |
| `l:`, `label:`, `tag:`, `marke:` | Eigene Archetyp-Marke der Karte (`none` / `keine` / `-` für unmarkierte Karten) | `:`, `=`, `!=` | `l:bounce`, `l:combo`, `l:none` |
| `c:`, `color:`, `farbe:` | Farbe(n) (`W`, `U`, `B`, `R`, `G`, `C` / `colorless` / `farblos`, Gilden-/Shard-Namen wie `simic`, `bant`). `:` prüft, ob die Karte alle genannten Farben enthält. | `:`, `=`, `!=`, `<`, `<=`, `>`, `>=` | `c:g`, `c:gu`, `c=gu`, `c:colorless` |
| `id:`, `ci:`, `identity:` | Farbidentität. `:` und `<=` prüfen, ob die Farbidentität der Karte eine Teilmenge der angegebenen Farben ist. | `:`, `=`, `!=`, `<`, `<=`, `>`, `>=` | `id:gu`, `id<=gwu`, `ci=c` |
| `mv`, `cmc`, `manawert` | Manawert (Zahl oder `even`/`gerade` bzw. `odd`/`ungerade`) | `:`, `=`, `!=`, `<`, `<=`, `>`, `>=` | `mv<=2`, `mv=0`, `cmc>4`, `mv:even` |
| `is:`, `has:` | Karteneigenschaft (`legendary`/`commander`, `basic`, `gamechanger`/`gc`, `fav`/`favorit`, `free`/`frei`, `excluded`) | `:`, `=`, `!=` | `is:legendary`, `is:fav`, `is:free`, `-is:gamechanger` |

---

## Logik, Phrasensuche und Negation

- **ODER-Verknüpfung (`or`) & Klammern (`(...)`):** `sol ring or mana crypt` liefert die Vereinigungsmenge beider Begriffe. Klammern steuern die Gruppierung (`(t:artifact or t:creature) mv<=2`).
- **Gruppen-Negation (`-(...)`):** `-(t:land or mv>=4)` schließt jede Karte aus, auf die der geklammerte Ausdruck zutrifft.
- **Alleinstehende Phrasen (`"..."`):** Eine in doppelte Anführungszeichen gesetzte Phrase ohne Feldpräfix (z. B. `"Sol Ring"` oder `"draw a card"`) sucht nach der exakten zusammenhängenden Zeichenkette in Name, Typenzeile oder Oracle-Text und sortiert Treffer weiterhin nach dem Standard-Freitext-Ranking.
- **Negation (`-`):** Ein vorangestelltes Minuszeichen schließt Treffer aus — sowohl bei Feldern (`-t:land`, `-r:ramp`, `-mv>3`) als auch bei Wörtern oder Phrasen (`-island`, `-"sol ring"`).

---

## Sichtbare Syntax-Hinweise bei Fehleingaben

Unbekannte Felder (z. B. `foo:bar`), fehlende Werte (`t:`, `mv>=`), nicht unterstützte Operatoren (`t>creature`, `||`, `&&`, `!t:land`), ungültige Zahlen-/Farbwerte (`mv>abc`, `c:xyz`), unausgeglichene oder leere Klammern (`(t:creature`, `t:creature)`, `()`, `-()`), verwaiste `or`-Operatoren (`or t:land`, `t:land or`), leere Phrasen (`""`) oder nicht geschlossene Anführungszeichen (`"draw a card`) erzeugen **keine stille Leerliste**, sondern blenden oberhalb der Kartenliste einen sichtbaren Hinweis (`#search-syntax-error`) mit der genauen Fehlerursache und gültigen Beispielen ein.
