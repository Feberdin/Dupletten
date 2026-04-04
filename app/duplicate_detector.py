"""
Zweck:
    Ermittelt wahrscheinliche Duplikate innerhalb von Radarr- und Sonarr-
    Bibliotheken.
Input/Output:
    Nimmt Listen von `MediaItem`-Objekten und liefert gruppierte
    `DuplicateGroup`-Objekte mit nachvollziehbaren Gruenden zurueck.
Wichtige Invarianten:
    - Mehrere Erkennungsgruende fuer dieselbe Gruppe werden zusammengefuehrt.
    - Reihenfolge der Regeln ist bewusst von "sicher" nach "heuristisch".
    - Das Modul erkennt nur Duplikate; es loescht nie etwas.
Debugging:
    Wenn Gruppen unerwartet wirken, die normalisierten Schluessel mit den
    Originaltiteln vergleichen. Besonders wichtig bei Remakes oder Reboots mit
    demselben Namen.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .models import DuplicateGroup, DuplicateReason, MediaItem

TITLE_TOKEN_RE = re.compile(r"[^a-z0-9]+")

REASON_LABELS = {
    "same_path": "Gleicher Pfad",
    "same_tmdb_id": "Gleiche TMDb-ID",
    "same_tvdb_id": "Gleiche TVDb-ID",
    "same_title_year": "Gleicher Titel + Jahr",
}


def normalize_title(value: str) -> str:
    """Warum existiert das?
    Arr-Eintraege unterscheiden sich oft nur in Leerzeichen, Sonderzeichen oder
    Gross-/Kleinschreibung.

    Was passiert hier?
    Wir bilden einen robusten Vergleichswert. Beispiel:
        "The Office (US)" -> "the office us"
        "The.Office-US"   -> "the office us"
    """

    cleaned = TITLE_TOKEN_RE.sub(" ", value.casefold())
    return " ".join(cleaned.split())


def normalize_path(value: str) -> str:
    return value.strip().rstrip("/").casefold()


def movie_duplicate_groups(items: list[MediaItem]) -> list[DuplicateGroup]:
    return _build_duplicate_groups(
        items,
        rules=(
            ("same_path", lambda item: normalize_path(item.path)),
            ("same_tmdb_id", lambda item: f"tmdb:{item.external_id_value}" if item.external_id_value else ""),
            (
                "same_title_year",
                lambda item: f"{normalize_title(item.title)}|{item.year or 'unknown'}",
            ),
        ),
    )


def series_duplicate_groups(items: list[MediaItem]) -> list[DuplicateGroup]:
    return _build_duplicate_groups(
        items,
        rules=(
            ("same_path", lambda item: normalize_path(item.path)),
            ("same_tvdb_id", lambda item: f"tvdb:{item.external_id_value}" if item.external_id_value else ""),
            (
                "same_title_year",
                lambda item: f"{normalize_title(item.title)}|{item.year or 'unknown'}",
            ),
        ),
    )


def _build_duplicate_groups(
    items: list[MediaItem],
    rules: tuple[tuple[str, callable], ...],
) -> list[DuplicateGroup]:
    """Warum existiert das?
    Filme und Serien nutzen dieselbe Gruppierungs-Mechanik, aber andere
    Identifikatoren.

    Was passiert hier?
    Wir laufen jede Regel in definierter Reihenfolge durch und registrieren nur
    Gruppen mit mehr als einem Element.
    """

    registry: dict[tuple[str, ...], DuplicateGroup] = {}

    for reason_code, key_builder in rules:
        grouped_items: dict[str, list[MediaItem]] = defaultdict(list)
        for item in items:
            key = key_builder(item)
            if key:
                grouped_items[key].append(item)

        for key, candidates in grouped_items.items():
            if len(candidates) <= 1:
                continue
            _register_group(registry, candidates, reason_code, key)

    groups = list(registry.values())
    groups.sort(key=lambda group: (-group.item_count, group.label.casefold()))
    return groups


def _register_group(
    registry: dict[tuple[str, ...], DuplicateGroup],
    candidates: list[MediaItem],
    reason_code: str,
    key: str,
) -> None:
    sorted_items = sorted(candidates, key=lambda item: (item.sort_title.casefold(), item.path.casefold(), item.arr_id))
    signature = tuple(item.stable_key for item in sorted_items)
    reason = DuplicateReason(
        code=reason_code,
        label=REASON_LABELS.get(reason_code, reason_code),
        value=key,
    )

    if signature not in registry:
        registry[signature] = DuplicateGroup(
            source=sorted_items[0].source,
            media_type=sorted_items[0].media_type,
            label=_group_label(sorted_items),
            items=sorted_items,
            reasons=[reason],
        )
        return

    existing_codes = {existing_reason.code for existing_reason in registry[signature].reasons}
    if reason.code not in existing_codes:
        registry[signature].reasons.append(reason)


def _group_label(items: list[MediaItem]) -> str:
    first_item = items[0]
    if first_item.media_type == "movie":
        if first_item.year:
            return f"{first_item.title} ({first_item.year})"
        return first_item.title

    if first_item.year:
        return f"{first_item.title} ({first_item.year})"
    return first_item.title
