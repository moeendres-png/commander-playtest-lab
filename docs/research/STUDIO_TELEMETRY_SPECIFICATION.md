# Spezifikation: Pro-Karten-Telemetrie und Messdefinitionen im Commander Studio

- **Dokument-ID:** `STUDIO_TELEMETRY_SPECIFICATION`
- **Referenz:** GitHub-Issue #1205 (Arbeitspaket P3 / G10)
- **Status:** `NOT_MEASURED` (Stand 2026-11-12)
- **Verbindliche Vorgaben:** `AGENTS.md` (Evidenzsemantik: `UNKNOWN != PASS`, `NOT_MEASURED != 0`, Fail-Closed)

---

## 1. Hintergrund und Problemstellung

Im Rahmen von **BUILD, PLAY und SIMULATE** soll das Commander Studio reale Deckbau-Entscheidungen unterstützen. Neben aggregierten externen Signalen (EDHREC-Inclusion, Korpus-Kookkurrenz, EDHTop16-Turnierpenetration) soll die Simulations-Engine empirische Messwerte liefern, wie sich einzelne Karten im Spielverlauf tatsächlich verhalten.

Eine naive Betrachtung setzt oft globale Deck-Win-Rates mit der Qualität einzelner gezogener Karten gleich. Dies ist statistisch irreführend und methodisch unzulässig, solange keine kontrollierten Bedingungen (Counterfactuals / A/B-Tests mit adäquatem Stichprobenumfang) vorliegen.

Dieses Dokument definiert:
1. Welche Kennzahlen auf Kartenebene technisch aus der Engine und dem SQLite-Schema (`simulation_card`, `simulation_run`) ableitbar sind.
2. Welcher Stichprobenumfang für eine statistisch valide Differenzierung von Win-Rate-Deltas zwingend erforderlich ist (Power-Analyse).
3. Den aktuellen Messstatus im Repository (`NOT_MEASURED`).

---

## 2. Ableitbare Telemetrie-Felder pro Karte (Code-Stand)

Das Studio-Schema in `src/commander_lab/studio/store.py` (`simulation_card`) und die Berechnungslogik in `src/commander_lab/studio/simulations.py` (Zeilen 245–270) erfassen folgende Basiskennzahlen pro Karte und Simulationslauf:

| Schema-Feld | Typ | Tatsächliche Code-Berechnung (`simulations.py`) | Nenner / Bezug | Einschränkung / Abgrenzung |
|---|---|---|---|---|
| `games_completed` | `INTEGER` | Anzahl gültig beendeter Partien des Laufs | Gesamtlauf | Nur beendete Spiele (`len(completed)`) |
| `games_offered` | `INTEGER` | Anzahl Partien, in denen die Karte im Spielverlauf mindestens einmal legal wirkbar angeboten wurde | `games_completed` | **Kein physisches Ziehen gemessen:** Handeintritt und Verweildauer auf der Hand sind im Engine-Bridge-Event-Stream `NOT_MEASURED` (`docs/research/PLAYGROUP_LIVE_PHASE7_CARD_INSIGHTS_METRICS_SPEC_20261108.md`, Z. 41). |
| `games_cast_after_offer` | `INTEGER` | Anzahl Partien, in denen die angebotene Karte mindestens einmal tatsächlich gewirkt wurde | `games_offered` | Zählt Partien mit mindestens einem Cast, nicht die Zahl der Cast-Ereignisse. |
| `games_rotted` | `INTEGER` | `max(0, games_offered - games_cast_after_offer)` | `games_offered` | Reine Differenz: Karte wurde angeboten, aber in dieser Partie nie gewirkt. Bedeutet **nicht**, dass die Karte physisch auf der Hand verblieb. |
| `offered_castable` | `INTEGER` | Identisch mit `games_offered` (`simulations.py` Z. 257: `offered_castable: offered_games`) | `games_completed` | **Keine Zahl von Prioritätsfenstern.** Entspricht exakt `games_offered`. |
| `cast_count` | `INTEGER` | Summe aller erfolgreichen Wirkausführungen über alle Partien | - | Erfasst Mehrfachausführungen (Recursion, Bounce-Loops wie *Shrieking Drake*). |
| `mean_first_cast_round` | `REAL` | Arithmetisches Mittel von `first_cast_round` über alle Partien mit Cast | Partien mit Cast | Eigene Zugnummer des Piloten (*own turn count*, nicht globale Rundenzahl). |

### Abgeleitete Ratios und Kennzahlen

1. **Offer-Rate (\(R_{\text{offer}}\)):**
   $$R_{\text{offer}} = \frac{\text{games\_offered}}{\text{games\_completed}}$$
   Anteil der Partien, in denen die Karte dem Piloten mindestens einmal legal angeboten wurde.

2. **Cast-Conversion-Rate (\(R_{\text{conv}}\)):**
   $$R_{\text{conv}} = \frac{\text{games\_cast\_after\_offer}}{\text{games\_offered}} \quad (\text{definiert für } \text{games\_offered} > 0)$$
   Anteil der Partien mit Angebot, in denen die Karte auch tatsächlich gewirkt wurde.

3. **Rot-Rate (\(R_{\text{rot}}\)):**
   $$R_{\text{rot}} = \frac{\text{games\_rotted}}{\text{games\_offered}} = 1 - R_{\text{conv}}$$
   Anteil der Partien mit Angebot, in denen kein Wirken stattfand.

4. **Timing-Velocity (\(V_{\text{round}}\)):**
   Arithmetisches Mittel `mean_first_cast_round` (eigene Spielrunden des Piloten).

> [!IMPORTANT]
> **Nicht gemessene Größen (`NOT_MEASURED`):**
> - Physische Handkarten-Ziehungen (*draw count*)
> - Dauer des Verbleibs auf der Hand (*turns in hand*)
> - Zahl durchlaufener Prioritätsfenster (*priority windows*)
> Diese Größen werden vom XMage-Bridge-Event-Stream aus Entkopplungs- und Geheimhaltungsgründen nicht pro Karte erfasst.

---

## 3. Methodische Voraussetzungen: Kausalmessung und Power-Analyse für Win-Rate-Deltas

Soll einer Karte ein kausaler Einfluss auf den Spielerfolg zugeschrieben werden (z. B. *„Karte A erhöht die Win-Rate des Decks um mindestens 5 Prozentpunkte gegenüber Alternative B“*), muss das Studiendesign methodisch sauber aufgesetzt sein.

### 3.1 Unzulässigkeit naiver In-Game-Vergleiche

Naive Gegenüberstellungen innerhalb desselben Simulationslaufs sind statistisch schwer verzerrt:
- **„Angeboten vs. Nicht angeboten“:** Eine Karte wird in längeren Spielen häufiger gesehen als in kurzen. Spiele, die bis Runde 10 dauern, weisen völlig andere Siegchancen und Matchup-Dynamiken auf als schnelle 5-Runden-Spiele.
- **„Gespielt vs. Nicht gezogen / Nicht gewirkt“:** Verursacht massiven Überlebenden-Effekt (*survivor bias*). Karten werden bevorzugt gewirkt, wenn der Pilot bereits Board-Kontrolle oder ausreichend Mana besitzt.
- **Keine Randomisierung:** Im laufenden Spiel wird eine Karte nicht zufällig zugeteilt, sondern unterliegt Mulligan-Entscheidungen, Draw-Spells und Spielsituationen.

### 3.2 Kausalmaß: Kontrafaktischer Deck-Tausch (A/B-Swap)

Das einzige methodisch saubere Maß für den individuellen Karteneffekt ist der **Deck-Tausch**:
1. Zwei Decklisten \(D_{\text{Test}}\) und \(D_{\text{Kontrolle}}\), die sich ausschließlich um die eine untersuchte Karte (bzw. den 1:1-Kartentausch) unterscheiden.
2. Identische Runden- und Zufalls-Seeds für beide Testreihen.
3. Identischer Tisch (gleiche 3 Gegner-Decks, gleiche Sitzplatzrotationen).
4. Das Siegmaß pro Arm ist definiert als:
   $$\text{Win-Rate} = \frac{\text{wins\_fractional}}{\text{games\_completed}}$$
5. Der kausale Effekt ist das beobachtete Delta:
   $$\Delta p = \text{Win-Rate}(D_{\text{Test}}) - \text{Win-Rate}(D_{\text{Kontrolle}})$$

### 3.3 Statistische Parameter im 4-Spieler-Commander

- **Baseline-Win-Rate (Nullhypothese \(H_0\)):** In einem balancierten 4-Personen-Pod beträgt die erwartete Win-Rate:
  $$p_0 = 0{,}25 \quad (25\,\%)$$
- **Effektstärke (\(\Delta p\)):** Gesucht ist der Nachweis eines Mindestunterschieds von 5 Prozentpunkten:
  $$p_1 = 0{,}30 \quad (\Delta p = 0{,}05)$$
- **Signifikanzniveau (\(\alpha\)):** \(\alpha = 0{,}05\) (zweiseitig, kritischer Z-Wert \(Z_{\alpha/2} = 1{,}96\)).
- **Statistische Power (\(1 - \beta\)):** \(80\,\%\) (\(\beta = 0{,}20\), Z-Wert \(Z_\beta = 0{,}8416\)).

### 3.4 Formel für den benötigten Stichprobenumfang

Für den unpaarigen Proportionenvergleich zweier unabhängiger Simulationsarme gilt für die Fallzahl pro Arm (\(n\)):

$$n = \frac{\left(Z_{\alpha/2} + Z_\beta\right)^2 \cdot \left[p_0(1 - p_0) + p_1(1 - p_1)\right]}{(\Delta p)^2}$$

Einsetzen der Werte:
$$\left(Z_{\alpha/2} + Z_\beta\right)^2 = (1{,}960 + 0{,}8416)^2 = (2{,}8016)^2 \approx 7{,}849$$

$$p_0(1 - p_0) = 0{,}25 \cdot 0{,}75 = 0{,}1875$$
$$p_1(1 - p_1) = 0{,}30 \cdot 0{,}70 = 0{,}2100$$
$$\text{Summe der Varianzen} = 0{,}1875 + 0{,}2100 = 0{,}3975$$

$$(\Delta p)^2 = (0{,}05)^2 = 0{,}0025$$

$$n = \frac{7{,}849 \cdot 0{,}3975}{0{,}0025} = \frac{3{,}120}{0{,}0025} \approx 1{.}248 \text{ beendete Spiele pro Arm}$$

### 3.5 Konsequenz für die Simulation

- Um einen Win-Rate-Unterschied von \(+5\,\%\) mit \(80\,\%\) Power nachzuweisen, müssen mindestens **1.248 Spiele** für Deck \(D_{\text{Test}}\) und mindestens **1.248 Spiele** für Deck \(D_{\text{Kontrolle}}\) unter identischen Bedingungen simuliert werden.
- Gesamtzahl erforderlicher Volllauf-Spiele: **mindestens 2.496 Partien** pro 1-Karten-Vergleich.

---

## 4. Status im Repository: NOT_MEASURED

### 4.1 Ist-Bestand im StudioStore

Im lokalen `StudioStore` (`~/.local/share/commander-studio/studio.sqlite3`) befinden sich *(lokale, ungeprüfte Beobachtung aus einer Test-Instanz, im Repository nicht testiert)*:
- `simulation_run`: 3 Läufe (`chulane:mixed`, `chulane:optimized`, `chulane:precon`) mit je **12 Spielen**.
- `simulation_card`: 192 Zeilen (reine Schema-Exploration).

### 4.2 Begründung für NOT_MEASURED

1. **Unzureichender Stichprobenumfang (\(N = 12 \ll 2{.}496\)):** Bei \(N = 12\) beträgt der \(95\,\%\)-Konfidenzintervall-Radius für eine beobachtete Win-Rate \(\pm 24{,}5\) Prozentpunkte. Ein Win-Rate-Delta von 5 Prozentpunkten liegt vollständig im statistischen Rauschen.
2. **Keine kontrafaktischen A/B-Swaps:** Die vorhandenen Läufe testen unterschiedliche Gesamtdecks gegeneinander, keine isolierten 1-Karten-Swaps.
3. **Regel- und Evidenzkonformität nach AGENTS.md:** 
   Gemäß `AGENTS.md` (§ 4) gilt:
   > `UNKNOWN != PASS`, `NOT_RUN != PASS`, `CODE_DERIVED != RUNTIME_VERIFIED`.
   
   Es ist unzulässig, aus unzureichenden oder fehlenden Messungen einen Standardwert (wie `0.0` oder `Default Tier C`) zu fabrizieren.
4. **Ergebnis:** Das Telemetrie-Signal für individuelle Karten im Tierlist- und Scoring-System wird verbindlich als **`NOT_MEASURED`** geführt.

---

## 5. Implementierungs- und Integrationsregeln für Folgeschritte

Wenn künftige Simulations-Kampagnen (M5/Studio-Batch-Execution) Telemetriedaten erzeugen, gelten folgende Bindungen:

1. **Schwellenwert-Gate (Vorschlag):** Ein kausales Karten-Win-Rate-Delta darf erst in Scoring- oder Tierlist-Funktionen einfließen, wenn beide Arme des Deck-Tauschs mindestens je \(n = 1{.}248\) beendete Spiele aufweisen und das \(95\,\%\)-Konfidenzintervall den Nullpunkt ausschließt.
2. **Trennung von Deskription und Kausalität:** 
   - Rein deskriptive Werte wie \(R_{\text{conv}}\), \(R_{\text{rot}}\) und `mean_first_cast_round` dürfen (Vorschlag: ab `games_offered >= 50`) als deskriptive Beobachtung (`"DERIVED_DESCRIPTIVE"`) angezeigt werden.
   - Kausale Urteile (*„Karte macht das Deck stärker“*) bleiben bis zum Erreichen der statistischen Power als `NOT_MEASURED` bzw. `UNKNOWN` deklariert.
3. **Keine synthetische Auffüllung:** Fehlende Telemetrie darf in UI und Algorithmen nicht mit 0 ersetzt werden, sondern muss explizit als `Status: NOT_MEASURED` ausgewiesen werden.
