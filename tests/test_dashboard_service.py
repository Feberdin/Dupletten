"""
Zweck:
    Tests fuer die Zusammenfuehrung von API-Daten, Fehlern und Duplikatgruppen
    im Dashboard-Service.
Input/Output:
    Nutzt Fake-Clients statt echter HTTP-Verbindungen und prueft den
    resultierenden `DashboardSnapshot`.
Wichtige Invarianten:
    - Ein Dienstfehler darf nur die betroffene Karte beeinflussen.
    - Fehlende Konfiguration muss als "disabled" erscheinen.
Debugging:
    Bei Fehlschlaegen die `services`-Liste aus dem Snapshot inspizieren.
"""

import unittest

from app.arr_client import ArrApiError
from app.dashboard_service import DashboardService
from app.models import MediaItem


def make_movie(arr_id: int, tmdb_id: int, title: str = "Dune Part Two") -> MediaItem:
    return MediaItem(
        source="radarr",
        media_type="movie",
        arr_id=arr_id,
        title=title,
        sort_title=title,
        year=2024,
        path=f"/movies/{title}-{arr_id}",
        external_id_name="tmdbId",
        external_id_value=tmdb_id,
        monitored=True,
        has_file=True,
        size_on_disk=2048,
        status="released",
        file_count=1,
        ended=None,
    )


def make_series(arr_id: int, tvdb_id: int, title: str = "The Office") -> MediaItem:
    return MediaItem(
        source="sonarr",
        media_type="series",
        arr_id=arr_id,
        title=title,
        sort_title=title,
        year=2005,
        path=f"/series/{title}-{arr_id}",
        external_id_name="tvdbId",
        external_id_value=tvdb_id,
        monitored=True,
        has_file=True,
        size_on_disk=4096,
        status="continuing",
        file_count=200,
        ended=False,
    )


class FakeRadarrClient:
    def __init__(self, movies):
        self.movies = movies
        self.service_config = type("Config", (), {"safe_base_url": "http://radarr:7878"})()

    def fetch_system_status(self):
        return {"version": "5.0.0"}

    def fetch_movies(self):
        return self.movies


class FakeSonarrClient:
    def __init__(self, series):
        self.series = series
        self.service_config = type("Config", (), {"safe_base_url": "http://sonarr:8989"})()

    def fetch_system_status(self):
        return {"version": "4.0.0"}

    def fetch_series(self):
        return self.series


class ErrorSonarrClient(FakeSonarrClient):
    def fetch_system_status(self):
        raise ArrApiError("Sonarr", "Sonarr ist nicht erreichbar.", "Bitte URL pruefen.")


class DashboardServiceTests(unittest.TestCase):
    def test_dashboard_loads_both_services(self):
        service = DashboardService(
            radarr_client=FakeRadarrClient([make_movie(1, 100), make_movie(2, 100)]),
            sonarr_client=FakeSonarrClient([make_series(1, 200), make_series(2, 200)]),
        )

        snapshot = service.load_dashboard()

        self.assertEqual(2, snapshot.total_duplicate_groups)
        self.assertEqual(2, len(snapshot.services))
        self.assertEqual("connected", snapshot.services[0].state)
        self.assertEqual("connected", snapshot.services[1].state)

    def test_dashboard_keeps_working_when_one_service_fails(self):
        service = DashboardService(
            radarr_client=FakeRadarrClient([make_movie(1, 100), make_movie(2, 100)]),
            sonarr_client=ErrorSonarrClient([]),
        )

        snapshot = service.load_dashboard()

        self.assertEqual(1, len(snapshot.movie_duplicates))
        self.assertEqual(0, len(snapshot.series_duplicates))
        self.assertEqual("error", snapshot.services[1].state)

    def test_dashboard_marks_missing_service_as_disabled(self):
        service = DashboardService(radarr_client=None, sonarr_client=None)

        snapshot = service.load_dashboard()

        self.assertEqual("disabled", snapshot.services[0].state)
        self.assertEqual("disabled", snapshot.services[1].state)


if __name__ == "__main__":
    unittest.main()
