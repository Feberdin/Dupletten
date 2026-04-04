"""
Zweck:
    Klare Datenmodelle fuer API-Ergebnisse, Duplikatgruppen und Dashboard-Daten.
Input/Output:
    Diese Klassen werden von API-Client, Duplikat-Erkennung, Web-Layer und
    JSON-Ausgabe gemeinsam genutzt.
Wichtige Invarianten:
    - Jedes Medienelement hat eine stabile, servicebezogene Identitaet.
    - Dashboard-Daten bleiben serialisierbar, damit UI und API denselben Stand
      nutzen koennen.
Debugging:
    Bei inkonsistenter Anzeige zuerst die serialisierte Ausgabe unter
    `/api/duplicates` mit den Dataclass-Feldern vergleichen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MediaItem:
    """Beschreibt einen Film- oder Serien-Eintrag aus Radarr oder Sonarr."""

    source: str
    media_type: str
    arr_id: int
    title: str
    sort_title: str
    year: int | None
    path: str
    external_id_name: str
    external_id_value: int | None
    monitored: bool
    has_file: bool
    size_on_disk: int
    status: str
    file_count: int
    ended: bool | None = None

    @property
    def stable_key(self) -> str:
        return f"{self.source}:{self.media_type}:{self.arr_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DuplicateReason:
    """Warum wurde eine Gruppe als Duplikat markiert?"""

    code: str
    label: str
    value: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DuplicateGroup:
    """Mehrere Arr-Eintraege, die wahrscheinlich dieselbe Serie oder denselben Film meinen."""

    source: str
    media_type: str
    label: str
    items: list[MediaItem]
    reasons: list[DuplicateReason] = field(default_factory=list)

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def total_size_on_disk(self) -> int:
        return sum(item.size_on_disk for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "media_type": self.media_type,
            "label": self.label,
            "item_count": self.item_count,
            "total_size_on_disk": self.total_size_on_disk,
            "reasons": [reason.to_dict() for reason in self.reasons],
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True)
class ServiceSnapshot:
    """Zustand eines einzelnen angebundenen Dienstes fuer die Dashboard-Karten."""

    name: str
    configured: bool
    state: str
    message: str
    base_url: str
    item_count: int
    duplicate_group_count: int
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DashboardSnapshot:
    """Gesamter, bereits berechneter Zustand fuer HTML und JSON."""

    generated_at: datetime
    movie_duplicates: list[DuplicateGroup]
    series_duplicates: list[DuplicateGroup]
    services: list[ServiceSnapshot]

    @property
    def total_duplicate_groups(self) -> int:
        return len(self.movie_duplicates) + len(self.series_duplicates)

    @property
    def total_duplicate_items(self) -> int:
        return sum(group.item_count for group in self.movie_duplicates + self.series_duplicates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_duplicate_groups": self.total_duplicate_groups,
            "total_duplicate_items": self.total_duplicate_items,
            "movie_duplicates": [group.to_dict() for group in self.movie_duplicates],
            "series_duplicates": [group.to_dict() for group in self.series_duplicates],
            "services": [service.to_dict() for service in self.services],
        }
