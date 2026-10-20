#!/usr/bin/env bash
# usage: make_variant.sh NAME GROUP[,GROUP...]   (groups: nested p2 trig p1 single; empty = none)
set -euo pipefail
S=/tmp/claude-0/-home-user/539e0cc6-b24b-52bf-b082-9d8e56b102aa/scratchpad
name=$1; groups=${2:-}
V=$S/var/$name; rm -rf "$V"; mkdir -p "$V/tree" "$V/classes"
cd "$S/mage-pin"
for f in Mage/src/main/java/mage/abilities/AbilitiesImpl.java Mage/src/main/java/mage/abilities/TriggeredAbilities.java \
         Mage/src/main/java/mage/cards/CardImpl.java Mage/src/main/java/mage/game/GameState.java Mage/src/main/java/mage/players/PlayerImpl.java; do
  mkdir -p "$V/tree/$(dirname $f)"; cp "$f" "$V/tree/$f"
done
declare -A G=( [nested]="nested_mana nested_playable" [p2]="p2" [trig]="trig" [p1]="p1" [single]="singleton_def singleton_use1 singleton_use2" )
for g in ${groups//,/ }; do for h in ${G[$g]}; do patch -s -p1 -d "$V/tree" < "$S/hunks/$h.patch"; done; done
files=$(find "$V/tree" -name '*.java')
javac -nowarn --release 8 -proc:none -cp "$S/jars/base.jar" -d "$V/classes" $files 2>&1 | grep -v "^Note:\|^warning\|^1 warning\|^Picked up" || true
cp "$S/jars/base.jar" "$S/jars/$name.jar"
jar uf "$S/jars/$name.jar" -C "$V/classes" .
echo "variant $name groups=[$groups] -> $(sha256sum $S/jars/$name.jar | cut -c1-16)"
