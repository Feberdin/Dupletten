#!/usr/bin/env bash
# Zweck:
#   Kleine lokale Test-Suite fuer die Erkennungslogik und einen interaktiven
#   End-to-End-Durchlauf des Duplikat-Tools.
# Input/Output:
#   Fuehrt Assertions gegen Bibliotheksfunktionen und das CLI aus; gibt pro Test
#   PASS/FAIL sowie am Ende eine Gesamtzusammenfassung aus.
# Wichtige Invarianten:
#   - Tests arbeiten nur in temporaeren Verzeichnissen.
#   - Es werden keine echten Medienbibliotheken veraendert.
#   - Mindestens ein Negativtest prueft Fehlverhalten bei falschem Input.
# Debugging:
#   LOG_LEVEL=debug ./tests/run_tests.sh zeigt mehr Kontext. Bei Fehlern wird der
#   betroffene Testname inklusive erwarteter/erhaltener Werte ausgegeben.

set -u

SCRIPT_DIR="$(CDPATH= cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(CDPATH= cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
# shellcheck source=../lib/media_duplicates.sh
. "$PROJECT_ROOT/lib/media_duplicates.sh"

TESTS_PASSED=0
TESTS_FAILED=0

pass() {
  TESTS_PASSED=$((TESTS_PASSED + 1))
  printf 'PASS %s\n' "$1"
}

fail() {
  TESTS_FAILED=$((TESTS_FAILED + 1))
  printf 'FAIL %s: %s\n' "$1" "$2"
}

assert_equals() {
  local name="$1"
  local expected="$2"
  local actual="$3"

  if [ "$expected" = "$actual" ]; then
    pass "$name"
  else
    fail "$name" "erwartet '$expected', erhalten '$actual'"
  fi
}

assert_contains() {
  local name="$1"
  local needle="$2"
  local haystack="$3"

  case "$haystack" in
    *"$needle"*)
      pass "$name"
      ;;
    *)
      fail "$name" "Ausgabe enthaelt '$needle' nicht"
      ;;
  esac
}

# Die Unit-Tests decken die Kernheuristik ab, damit Refactorings spaeter die
# Zuordnung von Film- oder Serien-Dateien nicht unbemerkt aendern.
test_movie_duplicate_key() {
  local actual
  actual="$(movie_duplicate_key "/tmp/Dune Part Two (2024)/Dune.Part.Two.2024.2160p.mkv")"
  assert_equals "movie key" "movie|dune part two|2024" "$actual"
}

test_series_duplicate_key() {
  local actual
  actual="$(series_duplicate_key "/tmp/The Office/Season 01/The.Office.S01E01.1080p.mkv")"
  assert_equals "series key" "series|the office|s01e01" "$actual"
}

test_invalid_root_fails() {
  local output status
  output="$("$PROJECT_ROOT/bin/media_duplicates.sh" --movies-root "/definitiv/nicht/vorhanden" 2>&1)"
  status=$?

  if [ "$status" -ne 0 ]; then
    assert_contains "invalid root error" "Verzeichnis nicht gefunden" "$output"
  else
    fail "invalid root error" "Skript haette mit Fehlercode beenden muessen"
  fi
}

# Dieser Test prueft den Happy Path plus das interaktive Loeschen einer Kopie.
test_list_and_delete_duplicate_file() {
  local temp_root movies_root series_root output remaining_duplicate
  temp_root="$(mktemp -d "${TMPDIR:-/tmp}/media-duplicates-tests.XXXXXX")" || {
    fail "delete duplicate" "Temp-Verzeichnis konnte nicht erstellt werden"
    return
  }

  movies_root="$temp_root/movies"
  series_root="$temp_root/series"
  mkdir -p "$movies_root/Dune Part Two (2024)" "$movies_root/Dune Part Two (2024) copy" "$series_root/The Office/Season 01"

  printf 'largest-copy' > "$movies_root/Dune Part Two (2024)/Dune.Part.Two.2024.2160p.mkv"
  printf 'small' > "$movies_root/Dune Part Two (2024) copy/Dune.Part.Two.2024.1080p.mkv"
  printf 'episode-a' > "$series_root/The Office/Season 01/The.Office.S01E01.1080p.mkv"
  printf 'episode-b' > "$series_root/The Office/Season 01/The.Office.S01E02.1080p.mkv"

  output="$(printf '2\n\n' | "$PROJECT_ROOT/bin/media_duplicates.sh" --movies-root "$movies_root" --series-root "$series_root" 2>&1)"
  remaining_duplicate="$movies_root/Dune Part Two (2024) copy/Dune.Part.Two.2024.1080p.mkv"

  if [ ! -f "$remaining_duplicate" ]; then
    assert_contains "delete duplicate output" "Geloeschte Dateien: 1" "$output"
  else
    fail "delete duplicate output" "Gewaehlte Duplikat-Datei wurde nicht geloescht"
  fi

  rm -rf "$temp_root"
}

run_all_tests() {
  test_movie_duplicate_key
  test_series_duplicate_key
  test_invalid_root_fails
  test_list_and_delete_duplicate_file

  printf '\nErgebnis: %d erfolgreich, %d fehlgeschlagen\n' "$TESTS_PASSED" "$TESTS_FAILED"
  [ "$TESTS_FAILED" -eq 0 ]
}

run_all_tests
