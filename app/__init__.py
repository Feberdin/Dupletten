"""
Zweck:
    Einstiegspunkt fuer das Docker-Webtool, das Radarr und Sonarr per API
    abfragt und Duplikate im Browser anzeigt.
Input/Output:
    Exportiert `create_app`, damit der Webserver und Tests dieselbe App-Fabrik
    verwenden koennen.
Wichtige Invarianten:
    - Die Web-App wird immer ueber dieselbe Fabrik aufgebaut.
    - Konfiguration und Service-Injektion bleiben dadurch testbar.
Debugging:
    Wenn Start oder Routing Probleme machen, zuerst `app/web.py` und
    `app/config.py` mit `LOG_LEVEL=DEBUG` pruefen.
"""

from .web import create_app

__all__ = ["create_app"]
