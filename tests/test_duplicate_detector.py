"""
Zweck:
    Unit-Tests fuer die Erkennung von Radarr-/Sonarr-Duplikaten.
Input/Output:
    Baut synthetische `MediaItem`-Objekte und prueft die resultierenden
    Duplikatgruppen.
Wichtige Invarianten:
    - Sichere Regeln wie externe IDs muessen greifen.
    - Mehrere Gruende fuer dieselbe Gruppe duerfen nicht doppelt angezeigt werden.
Debugging:
    Bei Fehlschlaegen zuerst die erzeugten Gruppen und Gruende ausgeben und mit
    den Eingabedaten vergleichen.
"""

import unittest

from app.duplicate_detector import movie_duplicate_groups, series_duplicate_groups
from app.models import MediaItem


def make_item(**overrides):
    defaults = {
        "source": "radarr",
        "media_type": "movie",
        "arr_id": 1,
        "title": "Dune Part Two",
        "sort_title": "Dune Part Two",
        "year": 2024,
        "path": "/data/movies/Dune Part Two (2024)",
        "external_id_name": "tmdbId",
        "external_id_value": 693134,
        "monitored": True,
        "has_file": True,
        "size_on_disk": 1024,
        "status": "released",
        "file_count": 1,
        "ended": None,
    }
    defaults.update(overrides)
    if "sort_title" not in overrides:
        defaults["sort_title"] = defaults["title"]
    if "path" not in overrides:
        defaults["path"] = f"/data/{defaults['media_type']}/{defaults['title']}-{defaults['arr_id']}"
    return MediaItem(**defaults)


class MovieDuplicateGroupsTests(unittest.TestCase):
    def test_movie_duplicates_combine_multiple_reasons_for_same_pair(self):
        first = make_item(arr_id=10, path="/movies/Dune Part Two (2024)", size_on_disk=100)
        second = make_item(arr_id=11, path="/movies/Dune Part Two (2024)", size_on_disk=200)

        groups = movie_duplicate_groups([first, second])

        self.assertEqual(1, len(groups))
        self.assertEqual(2, groups[0].item_count)
        self.assertEqual(
            {"same_path", "same_tmdb_id", "same_title_year"},
            {reason.code for reason in groups[0].reasons},
        )

    def test_movie_duplicates_ignore_unique_titles(self):
        first = make_item(arr_id=10, title="Dune Part Two", external_id_value=693134)
        second = make_item(
            arr_id=11,
            title="Blade Runner 2049",
            year=2017,
            external_id_value=335984,
            path="/data/movies/Blade Runner 2049-11",
        )

        groups = movie_duplicate_groups([first, second])

        self.assertEqual([], groups)


class SeriesDuplicateGroupsTests(unittest.TestCase):
    def test_series_duplicates_detect_tvdb_match(self):
        first = make_item(
            source="sonarr",
            media_type="series",
            arr_id=30,
            title="The Office",
            sort_title="The Office",
            year=2005,
            path="/series/The Office",
            external_id_name="tvdbId",
            external_id_value=73244,
            file_count=187,
            ended=True,
        )
        second = make_item(
            source="sonarr",
            media_type="series",
            arr_id=31,
            title="The Office",
            sort_title="The Office",
            year=2005,
            path="/series/The Office Duplicate",
            external_id_name="tvdbId",
            external_id_value=73244,
            file_count=160,
            ended=True,
        )

        groups = series_duplicate_groups([first, second])

        self.assertEqual(1, len(groups))
        self.assertEqual({"same_tvdb_id", "same_title_year"}, {reason.code for reason in groups[0].reasons})


if __name__ == "__main__":
    unittest.main()
