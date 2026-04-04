"""
Zweck:
    Einfache Integrations-Tests fuer HTML- und JSON-Ausgabe der Web-App.
Input/Output:
    Startet die Flask-App mit einem Stub-Dashboard-Service und prueft die
    wichtigsten Routen.
Wichtige Invarianten:
    - `/` rendert auch ohne echte Arr-Zugriffe.
    - `/api/duplicates` gibt denselben Datenstand als JSON aus.
Debugging:
    Bei HTML-Problemen den Response-Body ausgeben und mit dem Template abgleichen.
"""

from datetime import datetime, timezone
import unittest

from app.config import AppConfig, ServiceConfig
from app.models import DashboardSnapshot, DuplicateGroup, DuplicateReason, MediaItem, ServiceSnapshot
from app.web import create_app


def make_movie_group() -> DuplicateGroup:
    item = MediaItem(
        source="radarr",
        media_type="movie",
        arr_id=1,
        title="Dune Part Two",
        sort_title="Dune Part Two",
        year=2024,
        path="/movies/Dune Part Two (2024)",
        external_id_name="tmdbId",
        external_id_value=693134,
        monitored=True,
        has_file=True,
        size_on_disk=4096,
        status="released",
        file_count=1,
        ended=None,
    )
    return DuplicateGroup(
        source="radarr",
        media_type="movie",
        label="Dune Part Two (2024)",
        items=[item, item],
        reasons=[DuplicateReason(code="same_tmdb_id", label="Gleiche TMDb-ID", value="tmdb:693134")],
    )


class StubDashboardService:
    def load_dashboard(self) -> DashboardSnapshot:
        return DashboardSnapshot(
            generated_at=datetime(2026, 4, 4, 10, 0, tzinfo=timezone.utc),
            movie_duplicates=[make_movie_group()],
            series_duplicates=[],
            services=[
                ServiceSnapshot(
                    name="Radarr",
                    configured=True,
                    state="connected",
                    message="Ok",
                    base_url="http://radarr:7878",
                    item_count=2,
                    duplicate_group_count=1,
                    version="5.0.0",
                ),
                ServiceSnapshot(
                    name="Sonarr",
                    configured=False,
                    state="disabled",
                    message="Nicht konfiguriert",
                    base_url="nicht konfiguriert",
                    item_count=0,
                    duplicate_group_count=0,
                    version="",
                ),
            ],
        )


class WebAppTests(unittest.TestCase):
    def setUp(self):
        config = AppConfig(
            host="127.0.0.1",
            port=8000,
            log_level="INFO",
            request_timeout_seconds=10.0,
            radarr=ServiceConfig(name="Radarr", base_url="", api_key=""),
            sonarr=ServiceConfig(name="Sonarr", base_url="", api_key=""),
        )
        self.app = create_app(config=config, dashboard_service=StubDashboardService())
        self.client = self.app.test_client()

    def test_index_renders_dashboard(self):
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        self.assertIn(b"Doppelte Filme", response.data)
        self.assertIn(b"Dune Part Two (2024)", response.data)

    def test_duplicates_api_returns_json(self):
        response = self.client.get("/api/duplicates")

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual(1, payload["total_duplicate_groups"])
        self.assertEqual("Radarr", payload["services"][0]["name"])


if __name__ == "__main__":
    unittest.main()
