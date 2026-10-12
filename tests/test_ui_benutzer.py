"""Benutzerverwaltung via the web interface."""

import pytest

from tests.helpers import create


def row(query, **where):
    clause = " AND ".join(f"{k} = :{k}" for k in where)
    rows = query(f"SELECT * FROM benutzer WHERE {clause}", **where)
    assert len(rows) == 1, rows
    return rows[0]


def count(query):
    return query("SELECT COUNT(*) AS n FROM benutzer")[0]["n"]


USER = {"benutzername": "anna", "email": "anna@example.com", "passwort": "anna-geheim1", "aktiv": "1"}


def test_create_user_hashes_password_and_new_user_can_log_in(admin, query):
    create(admin, "/benutzer/neu", USER)
    user = row(query, benutzername="anna")
    assert user["email"] == "anna@example.com" and user["aktiv"] == 1
    assert user["passwort_hash"] != "anna-geheim1" and "anna-geheim1" not in user["passwort_hash"]
    assert user["letzter_login"] is None

    admin.logout()
    assert admin.login("anna", "anna-geheim1").status_code == 302
    assert row(query, benutzername="anna")["letzter_login"] is not None


def test_password_is_mandatory_when_creating(admin, query):
    response = admin.submit("/benutzer/neu", {**USER, "passwort": ""})
    assert response.status_code == 422
    assert "Bitte ausfüllen." in response.get_data(as_text=True)
    assert count(query) == 1


def test_short_password_is_rejected(admin, query):
    response = admin.submit("/benutzer/neu", {**USER, "passwort": "kurz"})
    assert response.status_code == 422
    assert "Mindestens 8 Zeichen erforderlich." in response.get_data(as_text=True)
    assert count(query) == 1


@pytest.mark.parametrize("field,value", [("benutzername", "admin"), ("email", "ADMIN@example.com")])
def test_username_and_email_must_be_unique(admin, query, field, value):
    response = admin.submit("/benutzer/neu", {**USER, field: value})
    assert response.status_code == 422
    assert "Ein Eintrag mit diesen Werten existiert bereits." in response.get_data(as_text=True)
    assert count(query) == 1


def test_password_is_never_shown_in_forms_or_details(admin, query):
    create(admin, "/benutzer/neu", USER)
    user_id = row(query, benutzername="anna")["id"]
    edit = admin.soup(admin.get(f"/benutzer/{user_id}/bearbeiten"))
    assert not edit.select_one("input[name=passwort]").get("value")
    assert row(query, id=user_id)["passwort_hash"] not in admin.get(f"/benutzer/{user_id}").get_data(as_text=True)


def test_edit_without_password_keeps_hash_and_changes_other_fields(admin, query):
    create(admin, "/benutzer/neu", USER)
    before = row(query, benutzername="anna")
    admin.submit(
        f"/benutzer/{before['id']}/bearbeiten",
        {"benutzername": "anna", "email": "neu@example.com", "passwort": "", "aktiv": "1"},
    )
    after = row(query, id=before["id"])
    assert after["email"] == "neu@example.com"
    assert after["passwort_hash"] == before["passwort_hash"]


def test_edit_with_password_replaces_hash(admin, query):
    create(admin, "/benutzer/neu", USER)
    before = row(query, benutzername="anna")
    admin.submit(
        f"/benutzer/{before['id']}/bearbeiten",
        {"benutzername": "anna", "email": "anna@example.com", "passwort": "voellig-neu-1", "aktiv": "1"},
    )
    assert row(query, id=before["id"])["passwort_hash"] != before["passwort_hash"]
    admin.logout()
    assert admin.login("anna", "anna-geheim1").status_code == 401
    assert admin.login("anna", "voellig-neu-1").status_code == 302


def test_deactivated_user_cannot_log_in(admin, query):
    create(admin, "/benutzer/neu", USER)
    user_id = row(query, benutzername="anna")["id"]
    admin.submit(
        f"/benutzer/{user_id}/bearbeiten", {"benutzername": "anna", "email": "anna@example.com", "passwort": ""}
    )
    assert row(query, id=user_id)["aktiv"] == 0
    admin.logout()
    assert admin.login("anna", "anna-geheim1").status_code == 401


def test_last_active_user_cannot_be_deactivated(admin, query):
    admin_id = row(query, benutzername="admin")["id"]
    response = admin.submit(
        f"/benutzer/{admin_id}/bearbeiten", {"benutzername": "admin", "email": "admin@example.com", "passwort": ""}
    )
    assert response.status_code == 422
    assert "Der letzte aktive Benutzer kann nicht deaktiviert werden." in response.get_data(as_text=True)
    assert row(query, id=admin_id)["aktiv"] == 1


def test_user_can_delete_other_user(admin, query):
    create(admin, "/benutzer/neu", USER)
    user_id = row(query, benutzername="anna")["id"]
    response = admin.delete(f"/benutzer/{user_id}")
    assert admin.flashes(admin.soup(response)) == ["Benutzer „anna“ wurde gelöscht."]
    assert count(query) == 1


def test_user_cannot_delete_self(admin, query):
    admin_id = row(query, benutzername="admin")["id"]
    soup = admin.soup(admin.get("/benutzer/"))
    own_actions = [a["aria-label"] for a in soup.select(f"#benutzer-{admin_id} .actions a")]
    assert own_actions == ["Anzeigen", "Bearbeiten"], "no delete action for the own account"
    assert admin.get(f"/benutzer/{admin_id}/loeschen").status_code == 403
    assert admin.post(f"/benutzer/{admin_id}/loeschen", {}, form_url="/benutzer/").status_code == 403
    assert count(query) == 1
    assert admin.get("/").status_code == 200, "still logged in"


def test_list_shows_status_and_last_login(admin, query):
    soup = admin.soup(admin.get("/benutzer/"))
    cells = [td.get_text(strip=True) for td in soup.select("tbody tr td")]
    assert cells[0] == "admin" and cells[2] == "Ja"
    assert cells[3] != "", "admin logged in, so a last login is shown"
