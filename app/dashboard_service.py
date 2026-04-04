"""
Zweck:
    Baut den kompletten Dashboard-Zustand aus API-Daten und Duplikat-Erkennung.
Input/Output:
    Ruft Arr-Clients auf, faengt Fehler pro Dienst ab und gibt ein
    `DashboardSnapshot` fuer UI und JSON zurueck.
Wichtige Invarianten:
    - Ein kaputter Dienst darf den anderen nicht mitreissen.
    - Fehlende Konfiguration fuehrt zu einem klaren "disabled"-Status.
    - Die Weboberflaeche bekommt immer ein vollstaendiges Snapshot-Objekt.
Debugging:
    Wenn nur Teile der Seite leer sind, die Service-Karten lesen: dort steht,
    ob Konfiguration fehlt oder ein API-Fehler aufgetreten ist.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .arr_client import ArrApiClient, ArrApiError
from .duplicate_detector import movie_duplicate_groups, series_duplicate_groups
from .models import DashboardSnapshot, DuplicateGroup, MediaItem, ServiceSnapshot


class DashboardService:
    """Warum existiert das?
    Die Webroute soll moeglichst wenig Fachlogik enthalten.

    Was passiert hier?
    Wir holen Daten je Dienst, berechnen Duplikate und formen daraus ein
    Snapshot-Objekt fuer HTML und JSON.
    """

    def __init__(
        self,
        radarr_client: ArrApiClient | None = None,
        sonarr_client: ArrApiClient | None = None,
    ) -> None:
        self.radarr_client = radarr_client
        self.sonarr_client = sonarr_client

    def load_dashboard(self) -> DashboardSnapshot:
        services: list[ServiceSnapshot] = []
        movie_groups: list[DuplicateGroup] = []
        series_groups: list[DuplicateGroup] = []

        radarr_snapshot, radarr_movies = self._load_radarr()
        services.append(radarr_snapshot)
        movie_groups.extend(radarr_movies)

        sonarr_snapshot, sonarr_series = self._load_sonarr()
        services.append(sonarr_snapshot)
        series_groups.extend(sonarr_series)

        return DashboardSnapshot(
            generated_at=datetime.now(timezone.utc),
            movie_duplicates=movie_groups,
            series_duplicates=series_groups,
            services=services,
        )

    def _load_radarr(self) -> tuple[ServiceSnapshot, list[DuplicateGroup]]:
        if self.radarr_client is None:
            return (
                ServiceSnapshot(
                    name="Radarr",
                    configured=False,
                    state="disabled",
                    message="Nicht konfiguriert. Bitte RADARR_URL und RADARR_API_KEY setzen.",
                    base_url="nicht konfiguriert",
                    item_count=0,
                    duplicate_group_count=0,
                    version="",
                ),
                [],
            )

        try:
            status = self.radarr_client.fetch_system_status()
            items = self.radarr_client.fetch_movies()
        except ArrApiError as exc:
            return (
                ServiceSnapshot(
                    name="Radarr",
                    configured=True,
                    state="error",
                    message=exc.full_message,
                    base_url=self.radarr_client.service_config.safe_base_url,
                    item_count=0,
                    duplicate_group_count=0,
                    version="",
                ),
                [],
            )

        groups = movie_duplicate_groups(items)
        return (
            ServiceSnapshot(
                name="Radarr",
                configured=True,
                state="connected",
                message="Verbindung erfolgreich. Filmbibliothek wurde geladen.",
                base_url=self.radarr_client.service_config.safe_base_url,
                item_count=len(items),
                duplicate_group_count=len(groups),
                version=str(status.get("version") or ""),
            ),
            groups,
        )

    def _load_sonarr(self) -> tuple[ServiceSnapshot, list[DuplicateGroup]]:
        if self.sonarr_client is None:
            return (
                ServiceSnapshot(
                    name="Sonarr",
                    configured=False,
                    state="disabled",
                    message="Nicht konfiguriert. Bitte SONARR_URL und SONARR_API_KEY setzen.",
                    base_url="nicht konfiguriert",
                    item_count=0,
                    duplicate_group_count=0,
                    version="",
                ),
                [],
            )

        try:
            status = self.sonarr_client.fetch_system_status()
            items = self._load_sonarr_series()
        except ArrApiError as exc:
            return (
                ServiceSnapshot(
                    name="Sonarr",
                    configured=True,
                    state="error",
                    message=exc.full_message,
                    base_url=self.sonarr_client.service_config.safe_base_url,
                    item_count=0,
                    duplicate_group_count=0,
                    version="",
                ),
                [],
            )

        groups = series_duplicate_groups(items)
        return (
            ServiceSnapshot(
                name="Sonarr",
                configured=True,
                state="connected",
                message="Verbindung erfolgreich. Serienbibliothek wurde geladen.",
                base_url=self.sonarr_client.service_config.safe_base_url,
                item_count=len(items),
                duplicate_group_count=len(groups),
                version=str(status.get("version") or ""),
            ),
            groups,
        )

    def _load_sonarr_series(self) -> list[MediaItem]:
        """Warum existiert das?
        Der Name ist etwas expliziter als ein nackter Direktaufruf im Loader.

        Was passiert hier?
        Wir lesen Serien aus Sonarr. Die Hilfsfunktion trennt den API-Zugriff
        sichtbar vom Fehler-Handling darueber.
        """

        if self.sonarr_client is None:
            return []
        return self.sonarr_client.fetch_series()
