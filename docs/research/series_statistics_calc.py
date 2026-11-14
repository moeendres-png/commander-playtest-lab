#!/usr/bin/env python3
"""Rechenskript zum Statistik-Plan fuer Deck-Vergleichs-Serien (Issue #1211).

Erzeugt alle Fallzahl-Tabellen von ``docs/research/SERIES_STATISTICS_PLAN.md``
aus den dort genannten Formeln (Normalapproximation, wie im Repo-Standard
``commander_lab.engine.rules.full_game_comparison.pairs_needed`` und
``power_table``) und prueft die im Dokument gedruckten Werte Zelle fuer Zelle
nach (Abschnitt "Verifikation" am Ende der Ausgabe). Keine Handzahlen: jede
Tabellenzelle des Plans steht unten als ``EXPECTED``-Konstante und wird mit
dem frisch gerechneten Wert verglichen; Abweichungen lassen das Skript mit
Exit-Code 1 enden.

Nur Standardbibliothek (``statistics.NormalDist`` fuer die Quantile), damit
das Skript ohne Projekt-Umgebung laeuft:

    python3 docs/research/series_statistics_calc.py

Evidenzklasse der Ergebnisse: ``MODELED`` (Formeln und Annahmen wie im Plan:
alpha = 0,05 zweiseitig, p0 = 1/s, rho = 0,25, DEFF = 1 + (s-1)*rho).
"""

from __future__ import annotations

import math
import sys
from statistics import NormalDist

NORM = NormalDist()
ALPHA = 0.05
POWERS = (0.80, 0.90)
DELTAS = (0.05, 0.10, 0.15)
SEATS = (2, 3, 4, 5, 6)
QS = (0.09, 0.20, 0.40)
RHO = 0.25
REPO_ANCHOR_SD = 0.63  # PLANNED_PAIR_SD in full_game_comparison.py (fuer q = 0,40)


def z(prob: float) -> float:
    return NORM.inv_cdf(prob)


def zsum(alpha: float, power: float) -> float:
    return z(1.0 - alpha / 2.0) + z(power)


# ---------------------------------------------------------------------------
# Ungepaart: zwei unabhaengige Arme (Plan Abschnitt 2.1)
# ---------------------------------------------------------------------------

def unpaired_n(seats: int, delta: float, power: float = 0.80, alpha: float = ALPHA) -> int:
    p0 = 1.0 / seats
    p1 = p0 + delta
    var = p0 * (1.0 - p0) + p1 * (1.0 - p1)
    return math.ceil(zsum(alpha, power) ** 2 * var / delta**2)


def detectable_unpaired(n: int, seats: int, power: float = 0.80, alpha: float = ALPHA) -> float:
    """Umkehrung von unpaired_n per Fixpunkt (p1 haengt von delta ab)."""
    p0 = 1.0 / seats
    delta = 0.25
    for _ in range(200):
        p1 = p0 + delta
        var = p0 * (1.0 - p0) + p1 * (1.0 - p1)
        new = zsum(alpha, power) * math.sqrt(var / n)
        if abs(new - delta) < 1e-12:
            return new
        delta = new
    return delta


# ---------------------------------------------------------------------------
# Gepaart: Paardifferenz d in {-1, 0, +1}, Var(d) ~= q (Plan Abschnitt 2.2)
# ---------------------------------------------------------------------------

def plan_sd(q: float) -> float:
    """Planungs-SD des Dokuments: Repo-Anker 0,63 fuer q = 0,40, sonst sqrt(q)."""
    return REPO_ANCHOR_SD if q == 0.40 else math.sqrt(q)


def paired_iid(delta: float, sd: float, power: float = 0.80, alpha: float = ALPHA) -> int:
    return math.ceil((zsum(alpha, power) * sd / delta) ** 2)


def deff(seats: int, rho: float = RHO) -> float:
    return 1.0 + (seats - 1) * rho


def paired_seeds(
    delta: float, q: float, seats: int, power: float = 0.80, alpha: float = ALPHA,
    sd: float | None = None,
) -> tuple[int, int, int]:
    """(iid-Paare, Cluster-Paare, Seeds) nach der Repo-Planungsmethode."""
    sd = plan_sd(q) if sd is None else sd
    iid = paired_iid(delta, sd, power, alpha)
    cluster_pairs = math.ceil(iid * deff(seats))
    return iid, cluster_pairs, math.ceil(cluster_pairs / seats)


def detectable_paired(pairs: int, sd: float, power: float = 0.80, alpha: float = ALPHA) -> float:
    return zsum(alpha, power) * sd / math.sqrt(pairs)


# ---------------------------------------------------------------------------
# Sequenzielle Looks: Lan-DeMets / O'Brien-Fleming (Plan Abschnitt 4)
# Replikation von sequential_look_alphas in full_game_comparison.py:
# a(t) = 2 - 2*Phi(z/sqrt(t)) = erfc(z/sqrt(2t)); Look-Level = Inkremente.
# ---------------------------------------------------------------------------

def look_levels(cumulative: list[int], alpha: float = ALPHA) -> list[float]:
    quantile = z(1.0 - alpha / 2.0)
    spent = [
        math.erfc(quantile / math.sqrt(2.0 * (count / cumulative[-1])))
        for count in cumulative[:-1]
    ] + [alpha]
    return [spent[0]] + [b - a for a, b in zip(spent, spent[1:])]


# ---------------------------------------------------------------------------
# Wilson-Intervall wie wilson_score_interval in studio/simulations.py
# ---------------------------------------------------------------------------

def wilson(p_hat: float, n: int, confidence: float = 0.95) -> tuple[float, float]:
    zz = 2.576 if confidence >= 0.99 else 1.95996
    denom = 1.0 + zz * zz / n
    center = (p_hat + zz * zz / (2.0 * n)) / denom
    spread = zz * math.sqrt(p_hat * (1.0 - p_hat) / n + zz * zz / (4.0 * n * n)) / denom
    return max(0.0, center - spread), min(1.0, center + spread)


# ---------------------------------------------------------------------------
# McNemar-Gegenprobe (Connor 1987), Form des Plan-Anhangs
# ---------------------------------------------------------------------------

def connor_total_pairs(delta: float, q: float, power: float = 0.80, alpha: float = ALPHA) -> float:
    pi = (1.0 + delta / q) / 2.0
    m = (z(1.0 - alpha / 2.0) * 0.5 + z(power) * math.sqrt(pi * (1.0 - pi))) ** 2 / (pi - 0.5) ** 2
    return m / q


def _binom_pmf_row(n: int, p: float) -> list[float]:
    """Binomial-PMF fuer k = 0..n per Rekurrenz (float, O(n))."""
    row = [0.0] * (n + 1)
    row[0] = (1.0 - p) ** n
    ratio = p / (1.0 - p)
    for k in range(n):
        row[k + 1] = row[k] * (n - k) / (k + 1) * ratio
    return row


def exact_sign_power(n_pairs: int, q: float, delta: float, alpha: float = ALPHA) -> float:
    """Exakte Power des Zeichentests (McNemar) per Binomial-Enumeration.

    M ~ Bin(N, q) diskordante Paare, davon gewinnt die Variante unter H1
    den Anteil pi = (1 + delta/q)/2. Ablehnung: exakter zweiseitiger
    Zeichentest auf den M Diskordanten zum Niveau alpha; wegen der
    Symmetrie von Bin(m, 1/2) ist die Ablehnungsregion {k <= c} ∪ {k >= m-c}
    mit dem groessten c, fuer das 2*P(X <= c) <= alpha gilt.
    """
    pi = (1.0 + delta / q) / 2.0
    p_m_row = _binom_pmf_row(n_pairs, q)
    power = 0.0
    for m in range(1, n_pairs + 1):
        if p_m_row[m] == 0.0:
            continue
        null_row = _binom_pmf_row(m, 0.5)
        cdf = 0.0
        cutoff = -1
        for k in range(0, (m - 1) // 2 + 1):
            cdf += null_row[k]
            if 2.0 * cdf <= alpha:
                cutoff = k
            else:
                break
        if cutoff < 0:
            continue
        alt_row = _binom_pmf_row(m, pi)
        tail = sum(alt_row[: cutoff + 1]) + sum(alt_row[m - cutoff:])
        power += p_m_row[m] * tail
    return power


# ---------------------------------------------------------------------------
# Tabellen (Ausgabe)
# ---------------------------------------------------------------------------

def fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def table_unpaired(power: float) -> str:
    lines = [f"Ungepaart, Partien je Arm (Power {power:.0%}, alpha = 0,05):",
             "| Plätze | p0 | Δ = 5 pp | Δ = 10 pp | Δ = 15 pp |",
             "|---|---|---|---|---|"]
    for s in SEATS:
        row = " | ".join(fmt_int(unpaired_n(s, d, power)) for d in DELTAS)
        lines.append(f"| {s} | {1.0 / s:.1%} | {row} |")
    return "\n".join(lines)


def table_paired_seeds(power: float) -> str:
    lines = [f"Gepaart, Seeds je Platzzahl (Power {power:.0%}, alpha = 0,05, rho = 0,25):",
             "| Δ | q | Paare (iid) | " + " | ".join(f"{s} Pl." for s in SEATS) + " |",
             "|---|---|---|" + "---|" * len(SEATS)]
    for d in DELTAS:
        for q in QS:
            if d > q:
                continue
            iid = paired_iid(d, plan_sd(q), power)
            seeds = " | ".join(str(paired_seeds(d, q, s, power)[2]) for s in SEATS)
            lines.append(f"| {d:.0%} | {q:.2f} | {fmt_int(iid)} | {seeds} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Verifikation gegen die gedruckten Werte des Plans (Stand der Ergaenzung)
# ---------------------------------------------------------------------------

FAILURES: list[str] = []


def check(label: str, computed: float, expected: float, tol: float = 0.0) -> None:
    ok = abs(computed - expected) <= tol
    if not ok:
        FAILURES.append(f"{label}: gerechnet {computed}, Dokument {expected}")
    print(f"  [{'OK' if ok else 'ABWEICHUNG'}] {label}: {computed} (Dokument: {expected})")


def verify() -> None:
    print("\n== Verifikation gegen SERIES_STATISTICS_PLAN.md ==")

    print("-- Abschnitt 2.1, ungepaart, Power 80 %")
    expected_unpaired = {
        (2, 0.05): 1562, (2, 0.10): 385, (2, 0.15): 167,
        (3, 0.05): 1440, (3, 0.10): 368, (3, 0.15): 165,
        (4, 0.05): 1248, (4, 0.10): 326, (4, 0.15): 150,
        (5, 0.05): 1091, (5, 0.10): 291, (5, 0.15): 136,
        (6, 0.05): 969, (6, 0.10): 263, (6, 0.15): 124,
    }
    for (s, d), want in expected_unpaired.items():
        check(f"ungepaart s={s} Δ={d:.0%}", unpaired_n(s, d), want)

    print("-- Abschnitt 2.1, Power-90 %-Anker (4 Plätze, 5 pp, Faktor)")
    check("ungepaart s=4 Δ=5% Power 90 %", unpaired_n(4, 0.05, 0.90), 1671)
    factor90 = (zsum(ALPHA, 0.90) / zsum(ALPHA, 0.80)) ** 2
    check("Faktor Power 90/80", round(factor90, 2), 1.34, tol=0.005)

    print("-- Abschnitt 2.2, gepaart: iid-Paare und Seeds")
    expected_paired = {
        # (Δ, q): (iid, {seats: seeds})
        (0.05, 0.09): (283, {2: 177, 3: 142, 4: 124, 5: 114, 6: 107}),
        (0.05, 0.20): (628, {2: 393, 3: 314, 4: 275, 5: 252, 6: 236}),
        (0.05, 0.40): (1247, {2: 780, 3: 624, 4: 546, 5: 499, 6: 468}),
        (0.10, 0.20): (157, {2: 99, 3: 79, 4: 69, 5: 63, 6: 59}),
        (0.10, 0.40): (312, {2: 195, 3: 156, 4: 137, 5: 125, 6: 117}),
        (0.15, 0.20): (70, {2: 44, 3: 35, 4: 31, 5: 28, 6: 27}),
        (0.15, 0.40): (139, {2: 87, 3: 70, 4: 61, 5: 56, 6: 53}),
    }
    for (d, q), (want_iid, want_seeds) in expected_paired.items():
        iid, _, _ = paired_seeds(d, q, 4)
        check(f"gepaart Δ={d:.0%} q={q:.2f} iid", iid, want_iid)
        for s, want in want_seeds.items():
            check(f"gepaart Δ={d:.0%} q={q:.2f} Seeds s={s}", paired_seeds(d, q, s)[2], want)

    print("-- Abschnitt 2.2, exakte Varianz statt Naeherung (Δ=15 pp, q=0,20)")
    exact_sd = math.sqrt(0.20 - 0.15**2)
    check("iid exakt (Var = q - Δ²)", paired_iid(0.15, exact_sd), 62)
    check("iid Naeherung (Var = q)", paired_iid(0.15, math.sqrt(0.20)), 70)

    print("-- Abschnitt 0, Zusammenfassung (4 Plätze)")
    for d, want in ((0.05, 2184), (0.10, 571), (0.15, 263)):
        check(f"ungepaart x DEFF Δ={d:.0%}", math.ceil(unpaired_n(4, d) * deff(4)), want)
    check("gepaart q=0,20 Seeds", paired_seeds(0.05, 0.20, 4)[2], 275)
    check("gepaart q=0,40 Seeds", paired_seeds(0.05, 0.40, 4)[2], 546)

    print("-- Abschnitt 2.3, Beispiel (4 Plätze, 10 pp, q=0,20)")
    iid, cluster_pairs, seeds = paired_seeds(0.10, 0.20, 4)
    check("Beispiel iid", iid, 157)
    check("Beispiel Cluster-Paare", cluster_pairs, 275)
    check("Beispiel Seeds", seeds, 69)
    check("Beispiel Partien gesamt", seeds * 4 * 2, 552)

    print("-- Abschnitt 2.4, Laufzeiten bei 225 Partien/Stunde (≈-Werte)")
    check("10 pp q=0,20 Stunden", round(552 / 225, 1), 2.5, tol=0.05)
    check("5 pp ungepaart Stunden", round(2496 / 225), 11, tol=0.5)
    check("5 pp gepaart q=0,40 Stunden", round(4368 / 225), 19, tol=0.5)

    print("-- Abschnitt 2.5, erkennbare Differenzen (pp, Toleranz 0,1)")
    for n, want in ((30, 33.5), (40, 29.2), (80, 20.7)):
        check(f"ungepaart n={n}/Arm", round(detectable_unpaired(n, 4) * 100, 1), want, tol=0.1)
    check("gepaart 40 Paare iid", round(detectable_paired(40, REPO_ANCHOR_SD) * 100, 1), 27.9, tol=0.1)
    check(
        "gepaart 40 Paare Cluster",
        round(detectable_paired(40, REPO_ANCHOR_SD) * math.sqrt(deff(4)) * 100, 1),
        36.9, tol=0.1,
    )

    print("-- Abschnitt 2.6, mehrere Looks / Varianten (Seeds, 4 Plätze, σ = √q)")
    alpha_last, alpha_bonf = 0.026, 0.026 / 5
    expected_26 = {
        # (q, Δ): (alt α=0,05, (a) α=0,026, (b) α=0,0052)
        (0.40, 0.05): (550, 659, 926), (0.40, 0.10): (138, 165, 232), (0.40, 0.15): (62, 74, 104),
        (0.20, 0.05): (275, 330, 463), (0.20, 0.10): (69, 83, 116), (0.20, 0.15): (31, 37, 52),
    }
    for (q, d), (w_old, w_a, w_b) in expected_26.items():
        sd = math.sqrt(q)
        check(f"2.6 q={q:.2f} Δ={d:.0%} alt", paired_seeds(d, q, 4, alpha=ALPHA, sd=sd)[2], w_old)
        check(f"2.6 q={q:.2f} Δ={d:.0%} (a)", paired_seeds(d, q, 4, alpha=alpha_last, sd=sd)[2], w_a)
        check(f"2.6 q={q:.2f} Δ={d:.0%} (b)", paired_seeds(d, q, 4, alpha=alpha_bonf, sd=sd)[2], w_b)
    for alpha, wants in ((ALPHA, (1248, 326, 150)), (alpha_last, (1497, 391, 179)),
                         (alpha_bonf, (2103, 549, 252))):
        for d, want in zip(DELTAS, wants):
            check(f"2.6 ungepaart iid α={alpha} Δ={d:.0%}", unpaired_n(4, d, alpha=alpha), want)

    print("-- Abschnitt 3, Varianzgewinn und Break-even")
    gains = {(0.05, 0.09): 4.5, (0.05, 0.20): 2.0, (0.05, 0.40): 1.0,
             (0.10, 0.20): 2.2, (0.10, 0.40): 1.1}
    for (d, q), want in gains.items():
        p0, p1 = 0.25, 0.25 + d
        gain = (p0 * (1 - p0) + p1 * (1 - p1)) / (q - d**2)
        check(f"Gewinn Δ={d:.0%} q={q:.2f}", round(gain, 1), want, tol=0.05)
    breakeven = {(4, 0.05): 0.3975, (4, 0.10): 0.415, (4, 0.15): 0.4275,
                 (5, 0.05): 0.3475, (5, 0.10): 0.37, (5, 0.15): 0.3875,
                 (6, 0.05): 0.3086, (6, 0.10): 0.3344, (6, 0.15): 0.3553,
                 (2, 0.05): 0.4975, (2, 0.10): 0.49, (2, 0.15): 0.4775}
    for (s, d), want in breakeven.items():
        p0, p1 = 1.0 / s, 1.0 / s + d
        rhs = p0 * (1 - p0) + p1 * (1 - p1)
        check(f"Break-even s={s} Δ={d:.0%}", round(rhs, 4), want, tol=0.00005)
    for s, want in ((2, 0.38), (3, 0.33), (4, 0.28), (5, 0.24), (6, 0.21)):
        p0 = 1.0 / s
        check(f"q unter H0 (φ=0,25) s={s}", round(2 * p0 * (1 - p0) * 0.75, 2), want, tol=0.005)

    print("-- Abschnitt 4, Look-Level (Lan-DeMets/OBF, alpha = 0,05)")
    lv = look_levels([30, 60, 90, 120])
    for got, want in zip(lv, (0.0001, 0.0055, 0.0181, 0.0264)):
        check("Look-Level 120/30", round(got, 4), want, tol=0.00005)
    lv2 = look_levels([1, 2])
    check("Look-Level 2 Looks, erster", round(lv2[0], 4), 0.0056, tol=0.00005)
    check("Look-Level 2 Looks, letzter", round(lv2[1], 4), 0.0444, tol=0.00005)
    lv8 = look_levels([20, 40, 60, 80, 100, 120, 140, 160])
    for got, want in zip(lv8, (0.0000, 0.0001, 0.0013, 0.0042, 0.0076, 0.0105, 0.0125, 0.0139)):
        check("Look-Level 160/20", round(got, 4), want, tol=0.00005)

    print("-- Abschnitt 6, Pod-Streuung (Zaehlungen 2/12, 3/12, 0/12)")
    shares = [2 / 12, 3 / 12, 0 / 12]
    mean = sum(shares) / 3
    sd_sample = math.sqrt(sum((x - mean) ** 2 for x in shares) / 2)
    check("Pod-SD (Stichprobe)", round(sd_sample, 3), 0.127, tol=0.0005)
    check("Binomial-SD bei n=12", round(math.sqrt(mean * (1 - mean) / 12), 3), 0.100, tol=0.0005)

    print("-- Abschnitt 8, Multiplizitaets-Faktoren")
    for k, want in ((1, 1.00), (2, 1.21), (5, 1.49), (10, 1.70), (99, 2.38)):
        factor = (zsum(ALPHA / k, 0.80) / zsum(ALPHA, 0.80)) ** 2
        check(f"Faktor K={k}", round(factor, 2), want, tol=0.005)

    print("-- Abschnitt 8, Wilson-Intervalle bei p̂ = 25 % (Prozent, 1 Dezimale)")
    expected_wilson = {12: (8.9, 53.2), 30: (13.0, 42.7), 50: (15.1, 38.5),
                       100: (17.5, 34.3), 200: (19.5, 31.4), 400: (21.0, 29.5),
                       1248: (22.7, 27.5)}
    for n, (wlo, whi) in expected_wilson.items():
        lo, hi = wilson(0.25, n)
        check(f"Wilson n={n} unten", round(lo * 100, 1), wlo, tol=0.05)
        check(f"Wilson n={n} oben", round(hi * 100, 1), whi, tol=0.05)

    print("-- Anhang, McNemar-Gegenprobe (Connor): Abweichung nach unten")
    worst = 0.0
    for d in DELTAS:
        for q in QS:
            if d >= q:
                continue
            repo = paired_iid(d, plan_sd(q))
            connor = connor_total_pairs(d, q)
            deviation = (repo - connor) / repo
            worst = max(worst, deviation)
            print(f"    Δ={d:.0%} q={q:.2f}: Connor {connor:.0f} vs. Repo {repo} "
                  f"({deviation:+.1%})")
    print(f"    groesste Abweichung nach unten: {worst:.1%} (Dokument: 'hoechstens rund 20 %')")
    if worst > 0.22:
        FAILURES.append(f"Connor-Abweichung {worst:.1%} > rund 20 %")

    print("-- Zusatz: exakte Zeichentest-Power an zwei Planungszellen (Normalapprox. = 80 %)")
    for n_pairs, q, d in ((628, 0.20, 0.05), (139, 0.40, 0.15)):
        p_exact = exact_sign_power(n_pairs, q, d)
        print(f"    N={n_pairs} Paare, q={q:.2f}, Δ={d:.0%}: exakte Power {p_exact:.1%}")


def main() -> int:
    print(table_unpaired(0.80))
    print()
    print(table_unpaired(0.90))
    print()
    print(table_paired_seeds(0.80))
    print()
    print(table_paired_seeds(0.90))
    verify()
    if FAILURES:
        print(f"\n{len(FAILURES)} ABWEICHUNG(EN):")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print("\nAlle geprueften Zellen des Plans reproduziert (Verifikation bestanden).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
