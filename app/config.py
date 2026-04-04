"""
Zweck:
    Zentrale, explizite Konfiguration fuer das Radarr-/Sonarr-Duplikat-Tool.
Input/Output:
    Liest Umgebungsvariablen ein und gibt typsichere Konfigurationsobjekte
    fuer Webserver und API-Anbindung zurueck.
Wichtige Invarianten:
    - URLs werden immer ohne abschliessenden Slash gespeichert.
    - Fehlende API-Keys oder URLs deaktivieren nur den betroffenen Dienst,
      statt die gesamte App unklar scheitern zu lassen.
Debugging:
    Bei Konfigurationsproblemen `.env`, `docker-compose.yml` und die
    zusammengefasste Statusanzeige im UI pruefen.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _clean_string(value: str | None) -> str:
    """Warum existiert das?
    Environment-Variablen enthalten oft Leerzeichen oder leere Strings.

    Was passiert hier?
    Wir trimmen den Wert und vereinheitlichen `None` zu einem leeren String,
    damit spaetere Pruefungen simpel und eindeutig bleiben.
    """

    return (value or "").strip()


def _clean_base_url(value: str | None) -> str:
    cleaned = _clean_string(value)
    return cleaned.rstrip("/")


def _read_int(name: str, default: int) -> int:
    raw_value = _clean_string(os.getenv(name))
    if not raw_value:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"Ungueltige Ganzzahl in {name}: '{raw_value}'. "
            "Bitte nur numerische Ports oder Timeouts setzen."
        ) from exc


def _read_float(name: str, default: float) -> float:
    raw_value = _clean_string(os.getenv(name))
    if not raw_value:
        return default

    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"Ungueltiger Dezimalwert in {name}: '{raw_value}'. "
            "Bitte einen numerischen Timeout-Wert setzen."
        ) from exc


@dataclass(frozen=True)
class ServiceConfig:
    """Beschreibt einen Arr-Dienst, den wir optional anbinden koennen."""

    name: str
    base_url: str
    api_key: str

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    @property
    def safe_base_url(self) -> str:
        return self.base_url or "nicht konfiguriert"


@dataclass(frozen=True)
class AppConfig:
    """Enthaelt alle Laufzeitwerte fuer Webserver und API-Zugriffe."""

    host: str
    port: int
    log_level: str
    request_timeout_seconds: float
    radarr: ServiceConfig
    sonarr: ServiceConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Warum existiert das?
        Docker und lokale Starts sollen dieselbe Konfigurationsquelle benutzen.

        Was passiert hier?
        Wir lesen alle benoetigten Umgebungsvariablen einmal zentral ein und
        validieren numerische Werte fruehzeitig.
        """

        return cls(
            host=_clean_string(os.getenv("APP_HOST")) or "0.0.0.0",
            port=_read_int("APP_PORT", 8000),
            log_level=(_clean_string(os.getenv("LOG_LEVEL")) or "INFO").upper(),
            request_timeout_seconds=_read_float("REQUEST_TIMEOUT_SECONDS", 10.0),
            radarr=ServiceConfig(
                name="Radarr",
                base_url=_clean_base_url(os.getenv("RADARR_URL")),
                api_key=_clean_string(os.getenv("RADARR_API_KEY")),
            ),
            sonarr=ServiceConfig(
                name="Sonarr",
                base_url=_clean_base_url(os.getenv("SONARR_URL")),
                api_key=_clean_string(os.getenv("SONARR_API_KEY")),
            ),
        )
