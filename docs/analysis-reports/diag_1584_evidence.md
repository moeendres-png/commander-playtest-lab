# Diagnose #1584 (Engine-Haenger): Beweisauszug

Stand 2026-11-19. Vollstaendige Diagnose als Kommentar in Issue #1584. Hier: Fix-Diff und Laufuebersicht.

## runs.txt
```
bf1033 "status": "failed" "frames": 1949 exit=0 wall=108.229664553  load=  load average: 4.64, 6.56, 5.20
a1024 "status": "finished" "frames": 2571 exit=0 wall=31.983042661  load=  load average: 3.63, 5.87, 5.11
bf1029v "status": "failed" "frames": 2855 exit=0 wall=104.965614221  load=  load average: 3.17, 5.52, 5.02
a1029v "status": "finished" "frames": 3404 exit=0 wall=36.681176398  load=  load average: 1.82, 4.46, 4.70

[exited with code 0]
orig-jar s1033a failed 1949 wall=122.8 (jstack q5s) ; s1024a failed 1402 wall=94.1
a1033 finished 2369 wall=32.1
b1 finished 2823 42 -
b1000 finished 2532 38 -
b1001 finished 2878 41 -
b1002 finished 2938 49 -
b1003 finished 3331 46 -
b1004 finished 4669 60 -
b1005 finished 3516 51 -
b1006 finished 2201 34 -
b1007 finished 2571 40 -
b1008 finished 2394 42 -
b1009 finished 2251 34 -
b1010 finished 3053 45 -
b1011 finished 2358 38 -
b1012 finished 4210 52 -
b1013 finished 2000 33 -
b1014 finished 1787 31 -
b1015 finished 2434 37 -
b1016 finished 2975 45 -
b1017 finished 2876 41 -
b1018 finished 2565 35 -
b1019 finished 2699 44 T43:atk=0->[] blkframes=0
b1020 finished 4883 51 -
b1021 finished 3074 52 -
b1022 finished 2244 36 -
b1023 finished 1964 35 -
b1025 finished 2374 36 -
b1026 finished 2721 47 -
b1027 finished 2792 39 -
b1028 finished 2224 35 -
b1029 finished 3378 44 T43:atk=0->[] blkframes=0
b1030 finished 3056 45 -
b1031 finished 1537 27 -
b1032 finished 2868 40 -
b1034 finished 3756 47 -
b1035 finished 2394 38 -
b1036 finished 2672 43 -
b1037 finished 2281 34 -
b1038 finished 2347 38 -
b1039 finished 6078 71 -
b2 finished 1603 30 -
b3 finished 2984 40 T40:atk=3->['Full Game Seat 2'] blkframes=0
b4 finished 2490 37 -
b5 finished 2466 33 -
b6 finished 4399 61 -
b7 finished 2468 38 -
b8 finished 2484 38 -
bf1029v failed 2855 41 T41:atk=1->['Full Game Seat 4'] blkframes=0
bf1033 failed 1949 31 T31:atk=1->['Quintorius, History Chaser'] blkframes=0
s1024a failed 1402 25 T25:atk=3->['Full Game Seat 4'] blkframes=0
s1033a failed 1949 31 T31:atk=1->['Quintorius, History Chaser'] blkframes=0
DIFF 3 ('finished', [0], '64e79011bad0', 2984) ('finished', [0], 'b134b9c73136', 3000)
identical 45 different 1
jars: orig 204dd9ad, before(main,javac) 1734cdb6, after 6c84bf6e
```

## fix_1584.diff
```diff
--- src_before/org/commanderlab/xmage/XmageFullGamePlayer.java	2026-11-19 10:38:10.637423088 +0000
+++ src_after/org/commanderlab/xmage/XmageFullGamePlayer.java	2026-11-19 10:38:21.089397908 +0000
@@ -42,6 +42,7 @@
 import mage.constants.Outcome;
 import mage.constants.RangeOfInfluence;
 import mage.constants.Zone;
+import mage.filter.common.FilterCreatureForCombatBlock;
 import mage.game.Game;
 import mage.game.combat.CombatGroup;
 import mage.game.stack.Spell;
@@ -3054,7 +3055,13 @@
             UUID defendingPlayerId
     ) {
         witness("declare_blocker");
-        List<Permanent> blockers = new ArrayList<>(getAvailableBlockers(game));
+        // #1584: the creatures that may block are the defending player's. A
+        // block controller other than the defender (ChooseBlockersEffect:
+        // Brutal Hordechief, Master Warcraft, Odric) declares them; its own
+        // creatures can never block here (CR 509.1a). Same set as
+        // getAvailableBlockers(game) when defendingPlayerId is this player.
+        List<Permanent> blockers = new ArrayList<>(game.getBattlefield().getAllActivePermanents(
+                new FilterCreatureForCombatBlock(), defendingPlayerId, game));
         // WS92-D5 twin-stable frame sequence (see selectAttackers):
         // declaration order among co-blockers carries no Rules content itself.
         blockers.sort(stablePermanentOrder(game));
```
