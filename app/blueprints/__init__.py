from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.blueprints import (
        abrechnung,
        auth,
        kosten,
        main,
        stammdaten,
        system,
        zaehler,
    )

    for module in (auth, main, stammdaten, zaehler, kosten, abrechnung, system):
        app.register_blueprint(module.bp)
