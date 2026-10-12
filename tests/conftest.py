import shutil
from pathlib import Path

import pytest
import sqlalchemy as sa
from flask_migrate import downgrade, upgrade
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from tests.ui import UI

METER_TYPE_SEED = [
    (1, "Heizung", "kWh"),
    (2, "Warmwasser", "m³"),
    (3, "Kaltwasser", "m³"),
    (4, "Allgemeinstrom", "kWh"),
]
CATALOG_TABLES = {"kostenart", "verteilerschluessel", "zaehlertyp", "alembic_version"}


def reset_data(engine) -> None:
    """Back to the seed state: all data tables empty, extensible catalog re-seeded."""
    with engine.begin() as conn:
        conn.execute(sa.text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in db.metadata.sorted_tables:
            if table.name not in CATALOG_TABLES:
                conn.execute(sa.text(f"TRUNCATE TABLE `{table.name}`"))
        conn.execute(sa.text("TRUNCATE TABLE zaehlertyp"))
        for type_id, name, unit in METER_TYPE_SEED:
            conn.execute(
                sa.text("INSERT INTO zaehlertyp (id, bezeichnung, einheit, aktiv) VALUES (:i, :n, :u, 1)"),
                {"i": type_id, "n": name, "u": unit},
            )
        conn.execute(sa.text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture(scope="session")
def app():
    """The application in test mode on the freshly migrated `<name>_test` database."""
    application = create_app(test_mode=True)
    assert application.config["DATABASE_NAME"].endswith("_test")
    with application.app_context():
        downgrade(revision="base")
        upgrade()
        engine = db.engine
    application.test_engine = engine
    yield application
    reset_data(engine)
    shutil.rmtree(Path(application.config["UPLOAD_DIRECTORY"]), ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_database(app):
    reset_data(app.test_engine)
    yield


@pytest.fixture
def query(app):
    """Run SQL on a fresh connection (independent of the application's sessions)."""

    def run(sql: str, **params) -> list[dict]:
        with app.test_engine.connect() as conn:
            return [dict(row) for row in conn.execute(sa.text(sql), params).mappings()]

    return run


@pytest.fixture
def session(app):
    """ORM session inside an app context, for model-level tests."""
    with app.app_context():
        yield db.session
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def ui(app):
    """Anonymous browser-like client (https, cookies kept)."""
    return UI(app.test_client())


@pytest.fixture
def admin(app, ui):
    """Operator account created directly in the database and logged in through the login page."""
    from app.models import User

    with app.app_context():
        user = User(username="admin", email="admin@example.com")
        user.password_hash = generate_password_hash("geheim123", method="pbkdf2:sha256:1000")
        db.session.add(user)
        db.session.commit()
        db.session.remove()
    ui.login("admin", "geheim123")
    return ui
