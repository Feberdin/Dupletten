# Zweck

- Dieses Repo enthaelt jetzt ein Docker-faehiges Webtool, das Radarr und Sonarr per API anbindet.
- Die erste Version zeigt doppelte Filme und Serien im Browser an.
- Die Struktur ist bewusst so angelegt, dass wir spaeter Aktionen wie „gesehen + 14 Tage spaeter loeschen“ darauf aufbauen koennen.

# Kurzer Plan

- Wir lesen Radarr und Sonarr getrennt per API ein.
- Jeder Dienst bekommt eine eigene Statuskarte mit klaren Fehlern.
- Filme werden zuerst ueber `TMDb-ID`, dann ueber normalisierten `Titel + Jahr` als Duplikate erkannt.
- Serien werden zuerst ueber `TVDb-ID`, dann ueber normalisierten `Titel + Jahr` erkannt.
- Das Webinterface zeigt pro Gruppe alle betroffenen Eintraege mit Pfad, Groesse und Dateianzahl.
- Die JSON-Route `/api/duplicates` liefert denselben Datenstand fuer spaetere Automatisierungen.
- Docker und lokale Starts nutzen dieselbe Environment-Konfiguration.
- Tests sichern Duplikatlogik, Dashboard-Aufbau und Web-Ausgabe ab.
- Der fruehere Shell-Prototyp bleibt im Repo und wird weiter mitgetestet.

# Annahmen

- Radarr und Sonarr sind ueber HTTP vom Container aus erreichbar.
- Du kennst jeweils die Basis-URL und den API-Key.
- Die erste Version erkennt doppelte Bibliothekseintraege in Arr, nicht jede moegliche Dateisystem-Dublette innerhalb eines einzelnen Eintrags.
- Spaeteres „gesehen + 14 Tage“ braucht zusaetzlich eine Quelle fuer den Wiedergabe-Status, zum Beispiel Plex, Jellyfin oder ein eigenes Watch-Flag.

# Dateibaum

```text
.
├── .dockerignore
├── .env.example
├── .gitignore
├── CONTRIBUTING.md
├── Dockerfile
├── README.md
├── app/
│   ├── __init__.py
│   ├── __main__.py
│   ├── arr_client.py
│   ├── config.py
│   ├── dashboard_service.py
│   ├── duplicate_detector.py
│   ├── models.py
│   ├── static/
│   │   └── styles.css
│   └── templates/
│       ├── base.html
│       └── index.html
├── bin/
│   └── media_duplicates.sh
├── docker-compose.yml
├── lib/
│   └── media_duplicates.sh
├── requirements.txt
└── tests/
    ├── run_all_tests.sh
    ├── run_tests.sh
    ├── test_dashboard_service.py
    ├── test_duplicate_detector.py
    └── test_web_app.py
```

# Zentrale Dateien

- `app/arr_client.py`: spricht mit Radarr und Sonarr und uebersetzt Fehler in verstaendliche Hinweise.
- `app/duplicate_detector.py`: eigentliche Erkennungslogik fuer doppelte Filme und Serien.
- `app/dashboard_service.py`: fuehrt Status, API-Daten und Duplikatgruppen zu einem Dashboard zusammen.
- `app/web.py`: HTML- und JSON-Routen.
- `Dockerfile` und `docker-compose.yml`: Container-Start.
- `.env.example`: Vorlage fuer URLs und API-Keys.

# Quickstart

## 1. Konfiguration anlegen

```bash
cd /Users/joachim.stiegler/Dupletten
cp .env.example .env
```

Dann `.env` mit deinen echten Werten fuellen:

```dotenv
RADARR_URL=http://dein-radarr-host:7878
RADARR_API_KEY=dein-echter-radarr-key
SONARR_URL=http://dein-sonarr-host:8989
SONARR_API_KEY=dein-echter-sonarr-key
```

## 2. Docker starten

```bash
docker compose up --build
```

Danach im Browser oeffnen:

```text
http://localhost:8080
```

# Lokaler Start ohne Docker

## Install

```bash
cd /Users/joachim.stiegler/Dupletten
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Start

```bash
cp .env.example .env
set -a
source .env
set +a
.venv/bin/python -m app
```

Dann im Browser:

```text
http://localhost:8000
```

# Konfiguration

- `APP_HOST`: Standard `0.0.0.0`
- `APP_PORT`: Standard `8000`
- `LOG_LEVEL`: `INFO` oder `DEBUG`
- `REQUEST_TIMEOUT_SECONDS`: Timeout fuer API-Requests
- `RADARR_URL`, `RADARR_API_KEY`
- `SONARR_URL`, `SONARR_API_KEY`

# So startest du es

1. `.env` mit echten Arr-Werten anlegen.
2. `docker compose up --build` starten.
3. `http://localhost:8080` im Browser oeffnen.
4. Erst die Statuskarten lesen.
5. Danach die Duplikatgruppen fuer Filme und Serien pruefen.

# So debugst du es

## Typische Fehler

- `Nicht konfiguriert`
  Ursache: URL oder API-Key fehlt.
  Fix: `.env` pruefen und Container neu starten.

- `HTTP 401` oder `HTTP 403`
  Ursache: API-Key falsch oder Dienst hinter falscher URL.
  Fix: API-Key in Radarr/Sonarr neu kopieren, URL pruefen.

- `nicht erreichbar`
  Ursache: Docker-Container kommt nicht an Radarr/Sonarr.
  Fix: Netzwerk, Hostname, Port und Reverse Proxy pruefen.

- Leere Listen trotz Verbindung
  Ursache: In Arr sind keine Dubletten nach den aktuellen Regeln vorhanden.
  Fix: Testweise `/api/duplicates` oeffnen und Rohdaten ansehen.

## Logs und Debug-Schalter

Docker:

```bash
docker compose logs -f
```

Lokal:

```bash
LOG_LEVEL=DEBUG .venv/bin/python -m app
```

# Tests lokal ausfuehren

## Web-App

```bash
cd /Users/joachim.stiegler/Dupletten
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## Alles zusammen

```bash
cd /Users/joachim.stiegler/Dupletten
chmod +x ./tests/run_all_tests.sh ./tests/run_tests.sh
PYTHON_BIN=.venv/bin/python ./tests/run_all_tests.sh
```

# Features der ersten Version

- Weboberflaeche fuer Radarr- und Sonarr-Duplikate
- Service-Status mit klarer Fehlerdarstellung
- JSON-Ausgabe unter `/api/duplicates`
- Docker-Start ueber `docker compose`
- Erweiterbare Struktur fuer spaetere Loesch-Workflows

# Geplanter Ausbau

- Quelle fuer „gesehen“ anbinden, zum Beispiel Plex oder Jellyfin
- Regel „geloescht 14 Tage nach gesehen“ als konfigurierbare Aktion
- Sichere Vorschau vor dem Loeschen
- Optionales Dateisystem-Scanning fuer Duplikate innerhalb eines einzelnen Arr-Eintrags

# Security-Hinweise

- API-Keys nur in `.env`, niemals committen.
- Das Tool liest in dieser Version nur Daten aus Radarr und Sonarr.
- Noch keine Loeschfunktion im Webtool aktivieren, bevor die Erkennung stabil genug fuer deine Bibliothek ist.

# Lizenz-Hinweis

- Aktuell ist keine eigene Lizenzdatei enthalten.
- Wenn du das Repo spaeter veroeffentlichst, ergaenze eine passende `LICENSE`.
