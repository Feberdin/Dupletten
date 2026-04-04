"""
Zweck:
    Kapselt alle HTTP-Zugriffe auf Radarr und Sonarr an einer Stelle.
Input/Output:
    Nimmt Service-Konfiguration entgegen, ruft die Arr-APIs auf und mappt die
    Antworten in `MediaItem`-Objekte.
Wichtige Invarianten:
    - API-Keys werden nie in Fehlermeldungen oder Logs ausgegeben.
    - Jeder HTTP-Fehler wird in eine handlungsorientierte Meldung uebersetzt.
    - Die Mapping-Logik bleibt bewusst schmal und direkt an den API-Feldern.
Debugging:
    Mit `LOG_LEVEL=DEBUG` die aufgerufenen Endpunkte und Rueckgabemengen
    beobachten. Fuer tiefe API-Probleme dieselben URLs testweise mit `curl`
    gegen Radarr/Sonarr aufrufen.
"""

from __future__ import annotations

import logging
from json import JSONDecodeError
from typing import Any

import requests

from .config import ServiceConfig
from .models import MediaItem

LOGGER = logging.getLogger(__name__)


class ArrApiError(RuntimeError):
    """Freundlicher Wrapper fuer Bedienungs- und Systemfehler gegen die Arr-APIs."""

    def __init__(self, service_name: str, message: str, remediation: str = "") -> None:
        self.service_name = service_name
        self.message = message
        self.remediation = remediation
        super().__init__(self.full_message)

    @property
    def full_message(self) -> str:
        if self.remediation:
            return f"{self.message} {self.remediation}"
        return self.message


class ArrApiClient:
    """Warum existiert das?
    Die Weboberflaeche soll nichts ueber Header, URLs oder HTTP-Fehler wissen.

    Was passiert hier?
    Wir bauen saubere Requests fuer einen Arr-Dienst und mappen die Antworten in
    unsere eigenen Modelle.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        session: requests.Session | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.service_config = service_config
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    @property
    def service_name(self) -> str:
        return self.service_config.name

    def fetch_system_status(self) -> dict[str, Any]:
        return self._get_json("/api/v3/system/status")

    def fetch_movies(self) -> list[MediaItem]:
        payload = self._get_json("/api/v3/movie")
        return [self._movie_from_payload(item) for item in payload]

    def fetch_series(self) -> list[MediaItem]:
        payload = self._get_json("/api/v3/series")
        return [self._series_from_payload(item) for item in payload]

    def _get_json(self, path: str) -> Any:
        if not self.service_config.base_url:
            raise ArrApiError(
                self.service_name,
                f"{self.service_name}-URL fehlt.",
                "Bitte die passende *_URL in deiner .env setzen.",
            )

        if not self.service_config.api_key:
            raise ArrApiError(
                self.service_name,
                f"{self.service_name}-API-Key fehlt.",
                "Bitte den passenden *_API_KEY in deiner .env setzen.",
            )

        url = f"{self.service_config.base_url}{path}"
        LOGGER.debug("Rufe %s-Endpunkt ab: %s", self.service_name, url)

        try:
            response = self.session.get(
                url,
                headers={"X-Api-Key": self.service_config.api_key},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise ArrApiError(
                self.service_name,
                f"{self.service_name} ist nicht erreichbar ({exc.__class__.__name__}).",
                f"Pruefe URL, Port, Reverse Proxy und ob der Container das Zielnetz erreicht: {self.service_config.safe_base_url}",
            ) from exc

        if response.status_code in (401, 403):
            raise ArrApiError(
                self.service_name,
                f"{self.service_name} hat den API-Zugriff verweigert (HTTP {response.status_code}).",
                "Pruefe, ob der API-Key stimmt und ob die URL wirklich auf Radarr/Sonarr zeigt.",
            )

        if response.status_code >= 400:
            raise ArrApiError(
                self.service_name,
                f"{self.service_name} antwortet mit HTTP {response.status_code} auf {path}.",
                "Bitte URL, Reverse Proxy und Authentifizierung pruefen.",
            )

        try:
            payload = response.json()
        except JSONDecodeError as exc:
            raise ArrApiError(
                self.service_name,
                f"{self.service_name} hat keine gueltige JSON-Antwort fuer {path} geliefert.",
                "Bitte pruefen, ob eventuell eine HTML-Loginseite oder ein Proxy-Fehler zurueckkommt.",
            ) from exc

        LOGGER.debug("%s lieferte %s Elemente fuer %s", self.service_name, _payload_size(payload), path)
        return payload

    def _movie_from_payload(self, item: dict[str, Any]) -> MediaItem:
        statistics = item.get("statistics") or {}
        return MediaItem(
            source="radarr",
            media_type="movie",
            arr_id=int(item.get("id", 0)),
            title=item.get("title") or "Unbekannter Film",
            sort_title=item.get("sortTitle") or item.get("title") or "Unbekannter Film",
            year=_safe_int(item.get("year")),
            path=item.get("path") or "",
            external_id_name="tmdbId",
            external_id_value=_safe_int(item.get("tmdbId")),
            monitored=bool(item.get("monitored", False)),
            has_file=bool(item.get("hasFile", False)),
            size_on_disk=_safe_int(item.get("sizeOnDisk")) or _safe_int(statistics.get("sizeOnDisk")) or 0,
            status=item.get("status") or "unknown",
            file_count=_safe_int(statistics.get("movieFileCount")) or (1 if item.get("hasFile") else 0),
            ended=None,
        )

    def _series_from_payload(self, item: dict[str, Any]) -> MediaItem:
        statistics = item.get("statistics") or {}
        return MediaItem(
            source="sonarr",
            media_type="series",
            arr_id=int(item.get("id", 0)),
            title=item.get("title") or "Unbekannte Serie",
            sort_title=item.get("sortTitle") or item.get("title") or "Unbekannte Serie",
            year=_safe_int(item.get("year")),
            path=item.get("path") or "",
            external_id_name="tvdbId",
            external_id_value=_safe_int(item.get("tvdbId")),
            monitored=bool(item.get("monitored", False)),
            has_file=(_safe_int(statistics.get("episodeFileCount")) or 0) > 0,
            size_on_disk=_safe_int(statistics.get("sizeOnDisk")) or 0,
            status=item.get("status") or "unknown",
            file_count=_safe_int(statistics.get("episodeFileCount")) or 0,
            ended=bool(item.get("ended", False)),
        )


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _payload_size(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        return len(payload.keys())
    return 1
