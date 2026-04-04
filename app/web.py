"""
Zweck:
    Flask-Weboberflaeche fuer die Anzeige von Arr-Duplikaten.
Input/Output:
    Baut Routen, Template-Helfer und die Verdrahtung zwischen Konfiguration,
    Dashboard-Service und HTML/JSON-Ausgabe.
Wichtige Invarianten:
    - HTML und JSON stammen aus derselben Datenquelle.
    - Fehler in einem Arr-Dienst werden als UI-Status dargestellt, nicht als
      undurchsichtiger 500er fuer die ganze Seite.
Debugging:
    `/api/duplicates` ist die schnellste Stelle, um zu pruefen, ob Problem in
    Datenbeschaffung oder Template-Rendering liegt.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests
from flask import Flask, current_app, jsonify, render_template

from .arr_client import ArrApiClient
from .config import AppConfig
from .dashboard_service import DashboardService


def create_app(
    config: AppConfig | None = None,
    dashboard_service: DashboardService | None = None,
) -> Flask:
    """Warum existiert das?
    Tests, lokale Entwicklung und Docker sollen dieselbe App initialisieren.

    Was passiert hier?
    Wir konfigurieren Logging, bauen die Abhaengigkeiten und registrieren die
    Webrouten sowie Template-Filter.
    """

    resolved_config = config or AppConfig.from_env()
    _configure_logging(resolved_config.log_level)

    app = Flask(__name__)
    app.config["APP_CONFIG"] = resolved_config
    app.config["DASHBOARD_SERVICE"] = dashboard_service or _build_dashboard_service(resolved_config)

    @app.template_filter("bytesize")
    def bytesize_filter(value: int) -> str:
        return _format_bytes(value)

    @app.template_filter("timestamp")
    def timestamp_filter(value: datetime) -> str:
        target = value.astimezone(timezone.utc)
        return target.strftime("%Y-%m-%d %H:%M:%S UTC")

    @app.route("/")
    def index():
        dashboard = current_app.config["DASHBOARD_SERVICE"].load_dashboard()
        return render_template("index.html", dashboard=dashboard)

    @app.route("/api/duplicates")
    def duplicates_api():
        dashboard = current_app.config["DASHBOARD_SERVICE"].load_dashboard()
        return jsonify(dashboard.to_dict())

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


def _build_dashboard_service(config: AppConfig) -> DashboardService:
    session = requests.Session()
    session.headers.update({"User-Agent": "Feberdin-arr-duplicates/1.0"})

    radarr_client = None
    if config.radarr.enabled:
        radarr_client = ArrApiClient(
            service_config=config.radarr,
            session=session,
            timeout_seconds=config.request_timeout_seconds,
        )

    sonarr_client = None
    if config.sonarr.enabled:
        sonarr_client = ArrApiClient(
            service_config=config.sonarr,
            session=session,
            timeout_seconds=config.request_timeout_seconds,
        )

    return DashboardService(radarr_client=radarr_client, sonarr_client=sonarr_client)


def _configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value or 0)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"
