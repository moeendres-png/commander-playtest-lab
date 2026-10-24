# Alt/Neu-Vergleich: v11-Korpus (M4, Kontrolle neu gerechnet) vs. v13-Baseline (M1)

Populationen unterscheiden sich (v11: M4-Spiele um zwei Custom-Decks,
v13: reine Precon-Pods) — die Tabelle ist die geforderte Nebeneinander-
stellung, keine Effektmessung. Alt-Werte sind die in dieser Arbeit
reproduzierten Kontrollwerte (control_v11.json, gleiche Definitionen).

| Kennzahl | v11 (alt) | v13 (neu) |
|---|---|---|
| Spiele | 1971 | 100 |
| Entscheidungen | 6051869 | 317212 |
| amount: n / Index-0 | 108 / 0.0 | 25 / 0.0 |
| announce_x: n / Index-0 | 3099 / 0.0 | 995 / 0.0 |
| choice: n / Index-0 | 97920 / 0.3354 | 4535 / 0.2077 |
| choose_object: n / Index-0 | 64743 / 0.3905 | 2772 / 0.329 |
| choose_use: n / Index-0 | 52768 / 0.9722 | 3448 / 0.9081 |
| declare_attacker: n / Index-0 | 115581 / 0.2932 | 8590 / 0.4654 |
| declare_blocker: n / Index-0 | 44419 / 0.1735 | 2160 / 0.306 |
| mana_payment: n / Index-0 | 1123371 / 0.0232 | 55302 / 0.0217 |
| mode: n / Index-0 | 15490 / 0.3668 | 346 / 0.4942 |
| mulligan: n / Index-0 | 14175 / 0.5562 | 676 / 0.5917 |
| multi_amount: n / Index-0 | 2381 / 0.0 | 629 / 0.0 |
| pile: n / Index-0 | 0 / None | 19 / 0.0 |
| priority: n / Index-0 | 4373551 / 0.9296 | 230087 / 0.9248 |
| replacement_effect: n / Index-0 | 1048 / 0.146 | 50 / 0.68 |
| target: n / Index-0 | 116674 / 0.416 | 5281 / 0.3761 |
| target_amount: n / Index-0 | 894 / 0.3848 | 58 / 0.0517 |
| trigger_order: n / Index-0 | 25647 / 0.5447 | 2239 / 0.6378 |
| Prioritaet Anteil | 72.3 % | 72.5 % |
| Mulligan-Keep gesamt (direkt gezaehlt) | 0.5559 (8788/15809) | 0.5917 (400/676) |
| Cancelled / 1.000 | 4.298 | 3.786 |

Hinweis: Die Positions-Buckets in control_v11.json sind fuer den Alt-Korpus
nicht belastbar (Bucket-Summe 14.175 vs. direkt gezaehlte 15.809 Mulligan-
Entscheidungen) — die Gesamtwerte oben sind direkt aus den Frames gezaehlt.
