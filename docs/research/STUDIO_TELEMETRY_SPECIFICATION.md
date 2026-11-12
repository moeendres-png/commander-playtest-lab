# Spezifikation: Pro-Karten-Telemetrie und Messdefinitionen im Commander Studio

- **Dokument-ID:** `STUDIO_TELEMETRY_SPECIFICATION`
- **Referenz:** GitHub-Issue #1205 (Arbeitspaket P3 / G10)
- **Status:** `NOT_MEASURED` (Stand 2026-11-12)
- **Autor / Prüfer:** Ausführungs-Lane Gemini Flash 3.8 High
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

## 2. Ableitbare Telemetrie-Felder pro Karte

Das Studio-Schema in `src/commander_lab/studio/store.py` (`simulation_card`) und die Ereignis-Hooks des XMage-Full-Game-Lane-Bridges erfassen folgende Basiskennzahlen pro Karte und Simulationslauf:

| Schema-Feld | Typ | Definition / Messpunkt |
|---|---|---|
| `games_completed` | `INTEGER` | Gesamtzahl der gültig beendeten Spiele des Simulationslaufs (\(N_{\text{games}}\)). |
| `games_offered` | `INTEGER` | Anzahl der Spiele, in denen die Karte dem Piloten tatsächlich zur Verfügung stand (in der Eröffnungshand, regulär gezogen oder per Tutor in die Hand/Zone überführt). |
| `games_cast_after_offer` | `INTEGER` | Anzahl der Spiele, in denen die Karte nach Erhalt auch tatsächlich gewirkt (oder aktiviert) wurde. |
| `games_rotted` | `INTEGER` | Anzahl der Spiele, in denen die Karte auf der Hand verblieb („Handleiche“ / Dead Draw) und bis Spielende nie gewirkt wurde. |
| `offered_castable` | `INTEGER` | Anzahl von Prioritätsfenstern bzw. Zügen, in denen die Karte im legalen Sinne wirkbar war (ausreichend Mana, gültiges Timing, legale Ziele), unabhängig davon, ob der Pilot sie wirkte. |
| `cast_count` | `INTEGER` | Gesamtzahl der Ausführungen/Casts über alle Spiele (erfasst Recursion, Bounce-and-Replay, z. B. Loops von *Shrieking Drake*). |
| `mean_first_cast_round` | `REAL` | Durchschnittliche Spielrunde (Turn Number), in der die Karte zum ersten Mal erfolgreich gewirkt wurde. |

### Abgeleitete Ratios und Kennzahlen

Aus den Basisbeobachtungen lassen sich folgende dimensionslose Kennzahlen bilden:

1. **Offer-Rate (\(R_{\text{offer}}\)):**
   $$R_{\text{offer}} = \frac{\text{games\_offered}}{\text{games\_completed}}$$
   Wahrscheinlichkeit, dass die Karte in einem Spiel gesehen wird.

2. **Cast-Conversion-Rate (\(R_{\text{conv}}\)):**
   $$R_{\text{conv}} = \frac{\text{games\_cast\_after\_offer}}{\text{games\_offered}} \quad (\text{nur definiert für } \text{games\_offered} > 0)$$
   Gibt an, wie oft eine angebotene Karte tatsächlich gewirkt wird. Ein niedriger Wert signalisiert Situationalität oder zu hohe Kosten.

3. **Rot-Rate (\(R_{\text{rot}}\)):**
   $$R_{\text{rot}} = \frac{\text{games\_rotted}}{\text{games\_offered}} = 1 - R_{\text{conv}}$$
   Anteil der Spiele, in denen die Karte ungenutzt auf der Hand verrottet.

4. **Cast-Opportunity-Efficiency (\(E_{\text{cast}}\)):**
   $$E_{\text{cast}} = \frac{\text{games\_cast\_after\_offer}}{\text{offered\_castable}}$$
   Verhältnis zwischen tatsächlichem Ausspielen und theoretischen Gelegenheiten.

5. **Timing-Velocity (\(V_{\text{round}}\)):**
   Arithmetisches Mittel `mean_first_cast_round`. Dient zur Einordnung in Früh-, Mittel- oder Spätspiel.

---

## 3. Methodische Voraussetzungen: Power-Analyse für Win-Rate-Deltas

Soll einer Karte ein kausaler Einfluss auf den Spielerfolg zugeschrieben werden (z. B. *„Karte A erhöht die Win-Rate des Decks um mindestens 5 Prozentpunkte“*), muss ein statistischer Zweistichproben-Vergleich (Z-Test für Proportionen bzw. logistische Regression) gerechnet werden.

### 3.1 Statistische Parameter im 4-Spieler-Commander

- **Baseline-Win-Rate (Nullhypothese \(H_0\)):** In einem balancierten 4-Personen-Pod beträgt die erwartete Win-Rate:
  $$p_0 = 0{,}25 \quad (25\,\%)$$
- **Effektstärke (\(\Delta p\)):** Gesucht ist der Nachweis eines Mindestunterschieds von 5 Prozentpunkten:
  $$p_1 = 0{,}30 \quad (\Delta p = 0{,}05)$$
- **Signifikanzniveau (\(\alpha\)):** \(\alpha = 0{,}05\) (zweiseitig, kritischer Z-Wert \(Z_{\alpha/2} = 1{,}96\)).
- **Statistische Power (\(1 - \beta\)):** \(80\,\%\) (\(\beta = 0{,}20\), Z-Wert \(Z_\beta = 0{,}8416\)).

### 3.2 Formel für den benötigten Stichprobenumfang

Für den unpaarigen Proportionenvergleich gilt für die Fallzahl pro Gruppe (\(n\)):

$$n = \frac{\left(Z_{\alpha/2} + Z_\beta\right)^2 \cdot \left[p_0(1 - p_0) + p_1(1 - p_1)\right]}{(\Delta p)^2}$$

Einsetzen der Werte:
$$\left(Z_{\alpha/2} + Z_\beta\right)^2 = (1{,}960 + 0{,}8416)^2 = (2{,}8016)^2 \approx 7{,}849$$

$$p_0(1 - p_0) = 0{,}25 \cdot 0{,}75 = 0{,}1875$$
$$p_1(1 - p_1) = 0{,}30 \cdot 0{,}70 = 0{,}2100$$
$$\text{Summe der Varianzen} = 0{,}1875 + 0{,}2100 = 0{,}3975$$

$$(\Delta p)^2 = (0{,}05)^2 = 0{,}0025$$

$$n = \frac{7{,}849 \cdot 0{,}3975}{0{,}0025} = \frac{3{,}120}{0{,}0025} \approx 1{.}248 \text{ Spiele pro Gruppe}$$

### 3.3 Konsequenz für die Simulation

- Um einen Win-Rate-Unterschied von \(+5\,\%\) mit \(80\,\%\) Power nachzuweisen, müssen mindestens **1.248 Spiele** der Bedingung *„Karte gezogen/gewirkt“* und **1.248 Spiele** der Kontrollbedingung *„Karte nicht im Deck bzw. nicht gezogen“* ausgewertet werden.
- Gesamtzahl erforderlicher Volllauf-Spiele: **mindestens 2.500 Partien** pro zu testender Kartenvariation.
- Wird eine Karte nur in \(50\,\%\) aller Spiele regulär gezogen (\(R_{\text{offer}} \approx 0{,}5\)), erhöht sich der Gesamt-Simulationsbedarf für diese einzelne Karte auf:
  $$N_{\text{total}} = \frac{1{.}248}{0{,}5} \approx 2{.}500 \text{ Spiele je Deck-Konfiguration}$$

---

## 4. Status im Repository: NOT_MEASURED

### 4.1 Ist-Bestand im StudioStore

Im aktuellen `StudioStore` (`~/.local/share/commander-studio/studio.sqlite3`) befinden sich:
- `simulation_run`: 3 Läufe (`chulane:mixed`, `chulane:optimized`, `chulane:precon`) mit je **12 Spielen**.
- `simulation_card`: 192 Zeilen (reine Explorationsläufe für das Schema).

### 4.2 Begründung für NOT_MEASURED

1. **Unzureichender Stichprobenumfang (\(N = 12 \ll 2{.}500\)):** Bei \(N = 12\) beträgt der \(95\,\%\)-Konfidenzintervall-Radius für eine beobachtete Win-Rate \(\pm 25\) Prozentpunkte. Ein Win-Rate-Delta von 5 Prozentpunkten liegt vollständig im Rauschen.
2. **Keine kontrafaktischen Kontrollgruppen:** Die 12 Spiele wurden nicht als isolierte A/B-Swaps (Deck mit Karte vs. Deck ohne Karte bei identischen Seeds und Gegner-Pods) durchgeführt.
3. **Regel- und Evidenzkonformität nach AGENTS.md:** 
   Gemäß `AGENTS.md` (§ 4) gilt:
   > `UNKNOWN != PASS`, `NOT_RUN != PASS`, `CODE_DERIVED != RUNTIME_VERIFIED`.
   
   Es ist ausdrücklich verboten, aus unzureichenden oder fehlenden Messungen einen Standardwert (wie `0.0` oder `Default Tier C`) zu fabrizieren.
4. **Ergebnis:** Das Telemetrie-Signal für individuelle Karten im Tierlist- und Scoring-System wird verbindlich als **`NOT_MEASURED`** geführt.

---

## 5. Implementierungs- und Integrationsregeln für Folgeschritte

Wenn künftige Simulations-Kampagnen (M5/Studio-Batch-Execution) Telemetriedaten erzeugen, gelten folgende Bindungen:

1. **Schwellenwert-Gate:** Ein Karten-Win-Rate-Delta darf erst in Scoring- oder Tierlist-Funktionen einfließen, wenn `games_offered >= 1000` und die Power-Bedingung erfüllt ist.
2. **Trennung von Deskription und Kausalität:** 
   - Deskriptive Werte wie `R_conv`, `R_rot` und `mean_first_cast_round` dürfen ab `games_offered >= 50` als *deskriptive Beobachtung* (`DataClass.DERIVED_DESCRIPTIVE`) angezeigt werden.
   - Kausale Urteile (*„Karte macht das Deck stärker“*) bleiben bis zum Erreichen der statistischen Power als `NOT_MEASURED` bzw. `UNKNOWN` deklariert.
3. **Keine synthetische Auffüllung:** Fehlende Telemetrie darf in UI und Algorithmen nicht mit 0 ersetzt werden, sondern muss explizit als `Status: NOT_MEASURED` ausgewiesen werden.
