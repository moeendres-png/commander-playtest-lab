#!/usr/bin/env bash
# usage: variant_test.sh NAME "hunk hunk ..."   (installs Mage with those hunks over the pin, runs RoomCardTest+ShayCormacTest)
S=/tmp/claude-0/-home-user/539e0cc6-b24b-52bf-b082-9d8e56b102aa/scratchpad
name=$1; hunks=$2
cd $S/mage-cand && git checkout -q -- . && for h in $hunks; do git apply $S/hunks/$h.patch || { echo "apply $h failed"; exit 2; }; done
export MAVEN_OPTS="-Xmx3g"
nice -n 10 mvn -B -ntp -q -DskipTests -pl Mage install > $S/res/vt_${name}_install.log 2>&1 || { echo "$name INSTALL_FAILED"; exit 1; }
nice -n 10 mvn -B -ntp -pl Mage.Tests test -Dtest='RoomCardTest,ShayCormacTest' -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false > $S/res/vt_${name}.log 2>&1
echo "$name: $(grep -E 'Tests run:.*Skipped' $S/res/vt_${name}.log | tail -1)"
