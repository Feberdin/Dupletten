"""
Zweck:
    Startet die Web-Anwendung lokal oder im Container.
Input/Output:
    Liest Konfiguration aus Umgebungsvariablen, baut die App und startet den
    HTTP-Server.
Wichtige Invarianten:
    - Der Startweg ist fuer lokale Entwicklung und Docker identisch.
    - Debug-Modus bleibt bewusst aus, damit Verhalten reproduzierbar ist.
Debugging:
    Mit `LOG_LEVEL=DEBUG python -m app` starten und die Verbindungsmeldungen im
    Terminal beobachten.
"""

from .config import AppConfig
from .web import create_app


def main() -> None:
    """Warum existiert das?
    Der Container und lokale Starts brauchen einen sehr klaren, kurzen Einstieg.

    Was passiert hier?
    Wir lesen die Environment-Konfiguration, bauen die Flask-App und starten sie
    mit dem konfigurierten Host/Port.
    """

    config = AppConfig.from_env()
    app = create_app(config=config)
    app.run(host=config.host, port=config.port, debug=False)


if __name__ == "__main__":
    main()
