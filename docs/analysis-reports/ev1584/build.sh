#!/bin/bash
# usage: build.sh <src-tree-root (repo)> <outdir>   -> outdir/bridge.jar, outdir/classes, outdir/test-classes
set -euo pipefail
SRC=$1; OUT=$2; B=/tmp/claude-0/-home-user/ef006e8b-893c-5ebd-80a1-8743a09c7458/scratchpad/b1584
rm -rf $OUT/classes $OUT/test-classes $OUT/jar; mkdir -p $OUT/classes $OUT/test-classes $OUT/jar
# strip all bridge classes from the fat jar -> base classpath with pinned XMage + deps only
if [ ! -f $B/lib/base.jar ]; then
  cp $B/lib/orig.jar $B/lib/base.jar
  zip -q -d $B/lib/base.jar 'org/commanderlab/*' >/dev/null
fi
find $SRC/engine-bridge/src/main/java -name '*.java' > $OUT/main.list
javac -nowarn -encoding UTF-8 --release 17 -cp $B/lib/base.jar -d $OUT/classes @$OUT/main.list 2>&1 | grep -v "^Note:" || true
[ -d $SRC/engine-bridge/src/main/resources ] && cp -r $SRC/engine-bridge/src/main/resources/. $OUT/classes/
cp $B/lib/base.jar $OUT/bridge.jar
(cd $OUT/classes && zip -q -r -X $OUT/bridge.jar org)
find $SRC/engine-bridge/src/test/java -name '*.java' > $OUT/test.list
javac -nowarn -encoding UTF-8 --release 17 -cp $B/lib/base.jar:$OUT/classes:$B/lib/junit-console.jar -d $OUT/test-classes @$OUT/test.list 2>&1 | grep -v "^Note:" || true
[ -d $SRC/engine-bridge/src/test/resources ] && cp -r $SRC/engine-bridge/src/test/resources/. $OUT/test-classes/
sha256sum $OUT/bridge.jar
