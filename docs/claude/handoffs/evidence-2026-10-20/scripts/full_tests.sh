#!/usr/bin/env bash
# usage: full_tests.sh NAME "hunks"
S=/tmp/claude-0/-home-user/539e0cc6-b24b-52bf-b082-9d8e56b102aa/scratchpad
name=$1; hunks=$2
cd $S/mage-cand && git checkout -q -- . && for h in $hunks; do git apply $S/hunks/$h.patch || { echo "apply $h failed" > $S/res/ft_$name.done; exit 2; }; done
export MAVEN_OPTS="-Xmx3g"
nice -n 10 mvn -B -ntp -q -DskipTests -pl Mage install > $S/res/ft_${name}_install.log 2>&1 || { echo INSTALL_FAILED > $S/res/ft_$name.done; exit 1; }
nice -n 10 mvn -B -ntp -pl Mage.Tests test > $S/res/ft_$name.log 2>&1
echo "$name exit=$? | $(grep -E 'Tests run: [0-9]+, Failures' $S/res/ft_$name.log | tail -1)" > $S/res/ft_$name.done
