"""Template filters, global context, error pages and the global login requirement."""

import logging

import sqlalchemy as sa
from flask import Flask, render_template, request, session, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from app.extensions import db, login_manager
from app.models import Property
from app.ui import formatting

logger = logging.getLogger(__name__)

ERROR_TEXTS = {
    400: ("Ungültige Anfrage", "Die Anfrage konnte nicht verarbeitet werden. Bitte laden Sie die Seite neu."),
    403: ("Kein Zugriff", "Diese Aktion ist nicht erlaubt."),
    404: ("Nicht gefunden", "Die angeforderte Seite oder der Eintrag existiert nicht."),
    500: ("Interner Fehler", "Es ist ein unerwarteter Fehler aufgetreten."),
}

# (group, [(label, endpoint, path prefixes that mark the item active)])
NAV = [
    (None, [("Übersicht", "main.dashboard", ("/",))]),
    (
        "Stammdaten",
        [
            ("Eigentümer", "stammdaten.eigentuemer_index", ("/eigentuemer/",)),
            (
                "Objekte & Wohneinheiten",
                "stammdaten.objekte_index",
                ("/objekte/", "/wohneinheiten/", "/mietverhaeltnisse/"),
            ),
            ("Mieter", "stammdaten.mieter_index", ("/mieter/",)),
        ],
    ),
    (
        "Messwesen",
        [
            ("Zähler & Zählerstände", "zaehler.zaehler_index", ("/zaehler/", "/zaehlerstaende/")),
            ("Zählertypen", "zaehler.zaehlertypen_index", ("/zaehlertypen/",)),
        ],
    ),
    (
        "Kosten",
        [
            ("Kostenpositionen", "kosten.kosten_index", ("/kosten/", "/belege/")),
            ("Verteilung", "kosten.verteilung_index", ("/verteilung/",)),
            ("Kostenarten", "kosten.kostenarten_index", ("/kostenarten/",)),
        ],
    ),
    ("Abrechnung", [("Abrechnungen", "abrechnung.abrechnungen_index", ("/abrechnungen/",))]),
    ("System", [("Benutzer", "system.benutzer_index", ("/benutzer/",))]),
]


def active_property_id() -> int | None:
    """Id of the active property (session), auto-selected if there is exactly one."""
    ids = db.session.scalars(sa.select(Property.id).order_by(Property.id)).all()
    chosen = session.get("active_property_id")
    if chosen in ids:
        return chosen
    return ids[0] if len(ids) == 1 else None


def register_ui(app: Flask) -> None:
    app.add_template_filter(formatting.fmt_date, "fmt_date")
    app.add_template_filter(formatting.fmt_datetime, "fmt_datetime")
    app.add_template_filter(formatting.fmt_decimal, "fmt_decimal")
    app.add_template_filter(formatting.fmt_money, "fmt_money")
    app.add_template_filter(formatting.fmt_enum, "fmt_enum")

    @app.before_request
    def require_login():
        if request.endpoint in (None, "static", "auth.login"):
            return None
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        return None

    @app.context_processor
    def inject_globals():
        ctx = {"test_mode": app.config["TEST_MODE"]}
        if current_user.is_authenticated:
            properties = db.session.scalars(sa.select(Property).order_by(Property.name)).all()
            ctx["properties"] = properties
            ctx["active_property_id"] = active_property_id()
            ctx["nav"] = [
                (group, [(label, url_for(endpoint), prefixes) for label, endpoint, prefixes in items])
                for group, items in NAV
            ]
        return ctx

    def render_error(code: int):
        title, text = ERROR_TEXTS.get(code, ERROR_TEXTS[500])
        return render_template("error.html", code=code, title=title, text=text), code

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        logger.warning("CSRF validation failed: %s", error.description)
        return render_error(400)

    for code in (400, 403, 404):
        app.register_error_handler(code, lambda error, code=code: render_error(code))

    @app.errorhandler(500)
    def server_error(error):
        logger.exception("Unhandled error: %s", error)
        db.session.rollback()
        return render_error(500)
