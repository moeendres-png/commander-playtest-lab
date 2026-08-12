#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROVIDER="${ENGINE_PROVIDER:-xmage}"
SOURCE_ROOT="${ENGINE_SOURCE_PATH:-$ROOT/vendor/engine-source/$PROVIDER}"
BINARY_ROOT="${ENGINE_BINARY_PATH:-$ROOT/vendor/engine-binaries/$PROVIDER}"
MAVEN_VERSION="3.9.16"

case "$PROVIDER" in
  xmage)
    REPO="https://github.com/magefree/mage.git"
    COMMIT="06d166b098ad36b277edef01116472203d5a047e"
    REQUIRED_JAVA_MIN=8
    ;;
  forge)
    REPO="https://github.com/Card-Forge/forge.git"
    COMMIT="a37a865a53280dd8ad6fad3384d69611e8c5a42f"
    REQUIRED_JAVA_MIN=17
    ;;
  *) echo "ERROR: ENGINE_PROVIDER must be xmage or forge" >&2; exit 2 ;;
esac

command -v java >/dev/null || { echo "ERROR: Java is missing" >&2; exit 3; }
command -v javac >/dev/null || { echo "ERROR: javac is missing; install a JDK" >&2; exit 3; }
JAVA_MAJOR="$(java -version 2>&1 | sed -n '1s/.*version "\([0-9]*\).*/\1/p')"
[[ -n "$JAVA_MAJOR" && "$JAVA_MAJOR" -ge "$REQUIRED_JAVA_MIN" ]] || {
  echo "ERROR: $PROVIDER requires Java >= $REQUIRED_JAVA_MIN; observed ${JAVA_MAJOR:-unknown}" >&2; exit 3;
}
mkdir -p "$(dirname "$SOURCE_ROOT")" "$BINARY_ROOT" "$ROOT/.tools"

if [[ -f "$BINARY_ROOT/installation-identity.json" && -n "${ENGINE_START_COMMAND:-}" ]]; then
  echo "Existing offline binary identity found at $BINARY_ROOT."
  echo "Skipping source build; run scripts/verify_engine.sh for the real handshake."
  exit 0
fi

if [[ -d "$SOURCE_ROOT/.git" ]]; then
  CURRENT_REMOTE="$(git -C "$SOURCE_ROOT" remote get-url origin 2>/dev/null || true)"
  [[ "$CURRENT_REMOTE" == "$REPO" ]] || { echo "ERROR: unexpected source remote: $CURRENT_REMOTE" >&2; exit 4; }
  git -C "$SOURCE_ROOT" fetch --tags --prune || {
    echo "WARNING: fetch failed; continuing only if the pinned commit already exists locally" >&2;
  }
  git -C "$SOURCE_ROOT" cat-file -e "$COMMIT^{commit}" 2>/dev/null || {
    echo "ERROR: pinned commit $COMMIT is unavailable" >&2; exit 4;
  }
  git -C "$SOURCE_ROOT" checkout --detach "$COMMIT"
  OBSERVED="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
  [[ "$OBSERVED" == "$COMMIT" ]] || { echo "ERROR: commit mismatch: $OBSERVED" >&2; exit 4; }
elif [[ -d "$SOURCE_ROOT" && -f "$SOURCE_ROOT/.commander-lab-engine-source.json" ]]; then
  OBSERVED="$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["commit"])' "$SOURCE_ROOT/.commander-lab-engine-source.json")"
  [[ "$OBSERVED" == "$COMMIT" ]] || { echo "ERROR: offline source identity mismatch: $OBSERVED" >&2; exit 4; }
  echo "Using offline source snapshot with declared pinned commit $OBSERVED"
elif [[ -e "$SOURCE_ROOT" ]]; then
  echo "ERROR: existing source path has neither .git nor .commander-lab-engine-source.json" >&2; exit 4
else
  command -v git >/dev/null || { echo "ERROR: git is missing" >&2; exit 3; }
  echo "Cloning pinned $PROVIDER source into $SOURCE_ROOT"
  git clone "$REPO" "$SOURCE_ROOT"
  git -C "$SOURCE_ROOT" checkout --detach "$COMMIT"
  OBSERVED="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
  [[ "$OBSERVED" == "$COMMIT" ]] || { echo "ERROR: commit mismatch: $OBSERVED" >&2; exit 4; }
fi

if [[ -x "$SOURCE_ROOT/mvnw" ]]; then
  MVN=("$SOURCE_ROOT/mvnw")
elif command -v mvn >/dev/null; then
  MVN=(mvn)
elif [[ -x "$ROOT/.tools/apache-maven-$MAVEN_VERSION/bin/mvn" ]]; then
  MVN=("$ROOT/.tools/apache-maven-$MAVEN_VERSION/bin/mvn")
else
  echo "Maven is missing; installing project-local Maven $MAVEN_VERSION"
  "$ROOT/scripts/bootstrap_maven.sh" "$MAVEN_VERSION"
  MVN=("$ROOT/.tools/apache-maven-$MAVEN_VERSION/bin/mvn")
fi

LOG="$ROOT/artifacts/engine_setup/${PROVIDER}_build.log"
mkdir -p "$(dirname "$LOG")"
if [[ "$PROVIDER" == "xmage" ]]; then
  (cd "$SOURCE_ROOT" && "${MVN[@]}" -DskipTests package) 2>&1 | tee "$LOG"
else
  (cd "$SOURCE_ROOT" && "${MVN[@]}" -DskipTests package) 2>&1 | tee "$LOG"
fi
cat > "$BINARY_ROOT/installation-identity.json" <<EOF
{"provider":"$PROVIDER","commit":"$COMMIT","source_path":"$SOURCE_ROOT","built_with_java":"$JAVA_MAJOR","build_log":"$LOG","bridge_verified":false}
EOF

echo "Source build completed. A provider-specific JSONL bridge must now be configured."
echo "Set ENGINE_START_COMMAND or place a verified bridge under $BINARY_ROOT."
echo "Run: $ROOT/scripts/verify_engine.sh"
