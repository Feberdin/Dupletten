#!/usr/bin/env bash
# Zweck:
#   Fuehrt die vorhandenen Shell-Tests und die neuen Python-Webtests gemeinsam aus.
# Input/Output:
#   Nutzt optional `PYTHON_BIN`, startet beide Testsaetze und beendet sich mit
#   Fehlercode, falls ein Teil fehlschlaegt.
# Wichtige Invarianten:
#   - Die alte Shell-Prototyp-Logik bleibt weiter abgesichert.
#   - Die neue Web-App wird immer mitgetestet.
# Debugging:
#   Fuer mehr Details zuerst die beiden Teilkommandos einzeln ausfuehren:
#   `bash ./tests/run_tests.sh` und `python -m unittest discover -s tests -p 'test_*.py'`.

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(CDPATH= cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

printf '==> Shell-Tests\n'
bash "$SCRIPT_DIR/run_tests.sh"

printf '\n==> Python-Webtests\n'
cd "$PROJECT_ROOT"
"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py'
