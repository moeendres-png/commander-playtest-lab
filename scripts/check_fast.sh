#!/usr/bin/env bash
# Fast local pre-push check mirroring the lint steps of .github/workflows/ci.yml
# plus targeted pytest for changed files. Not a CI replacement; no gate effect.

set -uo pipefail

LINT_COMMANDS=(
  "ruff check ."
  "ruff format --check --diff ."
  "mypy src/commander_lab"
  "python -m compileall -q src tests"
)

base_ref="${CHECK_FAST_BASE:-}"
while (($# > 0)); do
  case "$1" in
    --list-commands) printf '%s\n' "${LINT_COMMANDS[@]}"; exit 0 ;;
    --base) (($# >= 2)) || { echo "Missing argument for --base" >&2; exit 2; }; base_ref="$2"; shift 2 ;;
    -h|--help) echo "Usage: scripts/check_fast.sh [--list-commands] [--base <git-ref>]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

PYTHON_CMD="python"
command -v "$PYTHON_CMD" >/dev/null 2>&1 || PYTHON_CMD="python3"

now_ms() {
  local ts
  ts="$(date +%s%3N 2>/dev/null || true)"
  [[ "$ts" =~ ^[0-9]+$ ]] && printf '%s' "$ts" || printf '%s000' "$(date +%s)"
}

format_seconds() { printf '%d.%ds' "$(($1 / 1000))" "$((($1 % 1000) / 100))"; }

total_steps=0
failed_steps=0
overall_start_ms="$(now_ms)"

run_step() {
  local label="$1" start_ms end_ms elapsed rc tmp_out
  shift
  total_steps=$((total_steps + 1))
  start_ms="$(now_ms)"
  tmp_out="$(mktemp)"
  "$@" >"$tmp_out" 2>&1
  rc=$?
  end_ms="$(now_ms)"
  elapsed="$(format_seconds $((end_ms - start_ms)))"
  if ((rc == 0)); then
    printf '[PASS] %s (%s)\n' "$label" "$elapsed"
  else
    failed_steps=$((failed_steps + 1))
    printf '[FAIL] %s (exit %d, %s)\n' "$label" "$rc" "$elapsed"
    sed 's/^/  | /' "$tmp_out"
  fi
  rm -f "$tmp_out"
}

run_step "ruff check ." ruff check .
run_step "ruff format --check --diff ." ruff format --check --diff .
run_step "mypy src/commander_lab" mypy src/commander_lab
run_step "python -m compileall -q src tests" "$PYTHON_CMD" -m compileall -q src tests

collect_changed_files() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0
  local resolved_base="$base_ref"
  if [[ -z "$resolved_base" ]] && git rev-parse --verify --quiet origin/main >/dev/null 2>&1; then
    resolved_base="origin/main"
  fi
  if [[ -n "$resolved_base" && "$resolved_base" != "HEAD" ]] && git rev-parse --verify --quiet "$resolved_base" >/dev/null 2>&1; then
    git diff --name-only "${resolved_base}...HEAD" 2>/dev/null || true
  fi
  git diff --name-only 2>/dev/null || true
  git diff --cached --name-only 2>/dev/null || true
  git ls-files --others --exclude-standard 2>/dev/null || true
}

resolve_changed_tests() {
  local changed_file base_name stem parent_dir parent_name match
  while IFS= read -r changed_file; do
    [[ "$changed_file" == *.py ]] || continue
    base_name="${changed_file##*/}"
    if [[ "$changed_file" == tests/* ]]; then
      [[ "$base_name" == test_*.py && -f "$changed_file" ]] && printf '%s\n' "$changed_file"
      continue
    fi
    stem="${base_name%.py}"
    [[ "$stem" == "__init__" || "$stem" == "__main__" || ! -d tests ]] && continue
    while IFS= read -r match; do
      [[ -n "$match" ]] && printf '%s\n' "${match#./}"
    done < <(find tests -type f -name "test_${stem}.py" 2>/dev/null)
    parent_dir="${changed_file%/*}"
    parent_name="${parent_dir##*/}"
    case "$parent_name" in
      ""|"."|"src"|"scripts"|"commander_lab") ;;
      *)
        while IFS= read -r match; do
          [[ -n "$match" ]] && printf '%s\n' "${match#./}"
        done < <(find tests -type f -name "test_${parent_name}_${stem}.py" 2>/dev/null)
        ;;
    esac
  done < <(collect_changed_files | LC_ALL=C sort -u)
}

changed_tests=()
while IFS= read -r test_path; do
  [[ -n "$test_path" ]] && changed_tests+=("$test_path")
done < <(resolve_changed_tests | LC_ALL=C sort -u)

if ((${#changed_tests[@]} > 0)); then
  run_step "pytest (${#changed_tests[@]} changed test file(s))" "$PYTHON_CMD" -m pytest -q "${changed_tests[@]}"
else
  total_steps=$((total_steps + 1))
  printf '[PASS] pytest (0 changed test files, 0.0s)\n'
fi

overall_elapsed="$(format_seconds $(($(now_ms) - overall_start_ms)))"
passed_steps=$((total_steps - failed_steps))
if ((failed_steps == 0)); then
  printf 'SUMMARY: PASS (%d/%d steps, %s)\n' "$passed_steps" "$total_steps" "$overall_elapsed"
  exit 0
fi
printf 'SUMMARY: FAIL (%d/%d steps passed, %d failed, %s)\n' "$passed_steps" "$total_steps" "$failed_steps" "$overall_elapsed"
exit 1
