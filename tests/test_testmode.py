"""Test mode: the app runs on the `_test` database with identical structure, live data stays untouched."""

from pathlib import Path

import pytest
import sqlalchemy as sa

from app import create_app
from app.config import Config, load_config
from tests.helpers import create_owner

STRUCTURE_QUERIES = {
    "columns": """
        SELECT table_name, column_name, ordinal_position, column_default, is_nullable,
               column_type, extra, character_set_name, collation_name
        FROM information_schema.columns WHERE table_schema = :db
        ORDER BY table_name, ordinal_position""",
    "indexes": """
        SELECT table_name, index_name, seq_in_index, column_name, non_unique
        FROM information_schema.statistics WHERE table_schema = :db
        ORDER BY table_name, index_name, seq_in_index""",
    "foreign_keys": """
        SELECT k.table_name, k.constraint_name, k.column_name, k.referenced_table_name,
               k.referenced_column_name, r.update_rule, r.delete_rule
        FROM information_schema.key_column_usage k
        JOIN information_schema.referential_constraints r
          ON r.constraint_schema = k.constraint_schema AND r.constraint_name = k.constraint_name
        WHERE k.table_schema = :db AND k.referenced_table_name IS NOT NULL
        ORDER BY k.table_name, k.constraint_name, k.ordinal_position""",
    "check_constraints": """
        SELECT table_name, constraint_name, check_clause
        FROM information_schema.check_constraints WHERE constraint_schema = :db
        ORDER BY table_name, constraint_name""",
    "tables": """
        SELECT table_name, engine, table_collation FROM information_schema.tables
        WHERE table_schema = :db ORDER BY table_name""",
}


def test_app_runs_on_test_database(app, query):
    live = load_config().database.name
    assert app.config["TEST_MODE"] is True
    assert app.config["DATABASE_NAME"] == f"{live}_test"
    assert query("SELECT DATABASE() AS db")[0]["db"] == f"{live}_test"


def test_test_banner_is_shown(ui):
    page = ui.get("/login")
    assert "TESTMODUS" in page.get_data(as_text=True)
    assert ui.soup(page).select_one(".test-banner")


def test_uploads_use_separate_directory(app):
    assert Path(app.config["UPLOAD_DIRECTORY"]).name == "_test"


def test_log_file_has_test_suffix():
    log_dir = load_config().logging.directory
    assert list(log_dir.glob("app_*_test.log")), "test mode must write app_<timestamp>_test.log"


def test_start_is_refused_on_non_test_database(monkeypatch):
    """Safety net: test mode must never run on a database that is not a `_test` database."""
    monkeypatch.setattr(Config, "for_test_mode", lambda self: self)
    with pytest.raises(RuntimeError, match="Refusing to start in test mode"):
        create_app(test_mode=True)


@pytest.mark.parametrize("aspect", sorted(STRUCTURE_QUERIES))
def test_test_database_has_exact_same_structure_as_live_database(app, query, aspect):
    live = load_config().database.name
    live_rows = query(STRUCTURE_QUERIES[aspect], db=live)
    test_rows = query(STRUCTURE_QUERIES[aspect], db=f"{live}_test")
    assert live_rows, f"live database '{live}' has no {aspect}; run `flask db upgrade` first"
    assert test_rows == live_rows


def test_catalog_seed_data_is_identical(query):
    live = load_config().database.name
    for table in ("kostenart", "verteilerschluessel", "zaehlertyp"):
        assert query(f"SELECT * FROM `{live}_test`.{table} ORDER BY id") == query(
            f"SELECT * FROM `{live}`.{table} ORDER BY id"
        )


def test_ui_changes_do_not_touch_live_database(admin, query):
    live = load_config().database.name
    tables = ("eigentuemer", "objekt", "benutzer")
    before = {t: query(f"SELECT COUNT(*) AS n FROM `{live}`.{t}")[0]["n"] for t in tables}

    create_owner(admin, query)

    assert query("SELECT COUNT(*) AS n FROM eigentuemer")[0]["n"] == 1
    after = {t: query(f"SELECT COUNT(*) AS n FROM `{live}`.{t}")[0]["n"] for t in tables}
    assert after == before


def test_data_is_reset_between_tests(query):
    """The autouse fixture resets data tables and re-seeds the extensible catalog."""
    assert query("SELECT COUNT(*) AS n FROM eigentuemer")[0]["n"] == 0
    assert query("SELECT COUNT(*) AS n FROM benutzer")[0]["n"] == 0
    assert [r["bezeichnung"] for r in query("SELECT bezeichnung FROM zaehlertyp ORDER BY id")] == [
        "Heizung",
        "Warmwasser",
        "Kaltwasser",
        "Allgemeinstrom",
    ]
    assert sa.text  # keep import used for type-checkers
