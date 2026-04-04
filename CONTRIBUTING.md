# Zweck

- Diese Datei beschreibt, wie du das Docker-Webtool sicher weiterentwickelst.
- Input sind nachvollziehbare Code-Aenderungen; Output sind testbare Verbesserungen ohne ueberraschende Nebeneffekte.
- Wichtige Invariante: API-Lesen und spaetere Schreib-/Loeschaktionen bleiben strikt getrennt, bis die Regeln wirklich sauber sind.
- Debugging: Aenderungen immer zuerst gegen Stub-Tests und dann gegen echte Arr-Daten pruefen.

# Entwicklungsprinzipien

1. API-Zugriffe nur in `app/arr_client.py` kapseln.
2. Erkennungslogik nur in `app/duplicate_detector.py` erweitern.
3. Webrouten duenn halten; Fachlogik gehoert in Services.
4. Fuer neue Regeln immer mindestens einen Happy-Path und einen Negativtest ergaenzen.
5. Vor spaeteren Loeschfunktionen erst eine Vorschau und klare Sicherheitsbestaetigungen bauen.

# Setup

```bash
cd /Users/joachim.stiegler/Dupletten
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

# Tests

Nur Web-App:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Alles zusammen:

```bash
chmod +x ./tests/run_all_tests.sh ./tests/run_tests.sh
PYTHON_BIN=.venv/bin/python ./tests/run_all_tests.sh
```

# Docker-Check

```bash
docker compose up --build
```

# Style und Review

- Kommentare sollen Absicht und Risiken erklaeren, nicht nur Syntax.
- Fehlermeldungen immer mit konkreter Hilfestellung versehen.
- Keine API-Keys in Logs, Screenshots oder Commits.
- UI-Status muss fuer Nicht-Programmierer sofort lesbar bleiben.
- Neue Features erst mit JSON- und UI-Sicht pruefen, bevor Schreibaktionen eingebaut werden.
