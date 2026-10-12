"""Login, logout, access protection and CSRF — driven through the web interface."""

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User

PROTECTED = [
    "/",
    "/eigentuemer/",
    "/objekte/",
    "/mieter/",
    "/zaehler/",
    "/kosten/",
    "/verteilung/",
    "/abrechnungen/",
    "/benutzer/",
    "/eigentuemer/neu",
    "/passwort",
]


def add_user(app, username="admin", email="admin@example.com", password="geheim123", active=True):
    with app.app_context():
        user = User(username=username, email=email, active=active)
        user.password_hash = generate_password_hash(password, method="pbkdf2:sha256:1000")
        db.session.add(user)
        db.session.commit()
        db.session.remove()


@pytest.mark.parametrize("url", PROTECTED)
def test_anonymous_access_redirects_to_login_with_return_path(ui, url):
    response = ui.get(url)
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login?next=")


def test_anonymous_post_is_not_executed(ui, query):
    response = ui.post("/eigentuemer/neu", {"name": "X"}, form_url="/login")
    assert response.status_code == 302
    assert query("SELECT COUNT(*) AS n FROM eigentuemer")[0]["n"] == 0


def test_login_page_layout(ui):
    soup = ui.soup(ui.get("/login"))
    assert soup.select_one("form input[name=login]")
    assert soup.select_one("form input[name=password]")
    assert soup.select_one("form input[name=csrf_token]")
    assert not soup.select(".app__nav"), "navigation is only shown to logged-in users"


def test_successful_login_by_username_sets_last_login_and_redirects(app, ui, query):
    add_user(app)
    assert query("SELECT letzter_login FROM benutzer")[0]["letzter_login"] is None
    response = ui.login("admin", "geheim123")
    assert response.status_code == 302 and ui.location(response) == "/"
    assert query("SELECT letzter_login FROM benutzer")[0]["letzter_login"] is not None
    page = ui.get("/")
    assert page.status_code == 200
    assert "admin" in ui.soup(page).select_one(".app__username").get_text()


def test_login_by_email_and_return_to_requested_page(app, ui):
    add_user(app)
    ui.get("/mieter/")
    response = ui.post(
        "/login",
        {"login": "admin@example.com", "password": "geheim123", "next": "/mieter/"},
        form_url="/login?next=/mieter/",
    )
    assert response.status_code == 302 and ui.location(response) == "/mieter/"


def test_open_redirect_is_not_followed(app, ui):
    add_user(app)
    response = ui.post(
        "/login", {"login": "admin", "password": "geheim123", "next": "https://evil.example/"}, form_url="/login"
    )
    assert ui.location(response) == "/"


@pytest.mark.parametrize("login,password", [("admin", "falsch"), ("nobody", "geheim123"), ("", "")])
def test_invalid_credentials_are_rejected_generically(app, ui, query, login, password):
    add_user(app)
    response = ui.login(login, password)
    assert response.status_code == 401
    assert "Anmeldedaten ungültig." in ui.flashes(ui.soup(response))[0]
    assert query("SELECT letzter_login FROM benutzer")[0]["letzter_login"] is None
    assert ui.get("/").status_code == 302


def test_inactive_user_cannot_log_in(app, ui):
    add_user(app, active=False)
    response = ui.login("admin", "geheim123")
    assert response.status_code == 401
    assert ui.get("/").status_code == 302


def test_post_without_csrf_token_is_rejected(app, ui):
    add_user(app)
    response = ui.post("/login", {"login": "admin", "password": "geheim123"}, token=False)
    assert response.status_code == 400
    assert ui.get("/").status_code == 302


def test_write_without_csrf_token_is_rejected_and_nothing_is_saved(admin, query):
    response = admin.post(
        "/eigentuemer/neu",
        {"name": "Ohne Token", "rechtsform": "KG", "strasse": "a", "plz": "1", "ort": "b"},
        token=False,
    )
    assert response.status_code == 400
    assert query("SELECT COUNT(*) AS n FROM eigentuemer")[0]["n"] == 0


def test_logout_ends_session(admin):
    assert admin.get("/").status_code == 200
    response = admin.logout()
    assert response.status_code == 302 and admin.location(response) == "/login"
    assert admin.get("/").status_code == 302


def test_logout_requires_post(admin):
    assert admin.get("/logout").status_code == 405
    assert admin.get("/").status_code == 200


def test_change_password(admin, query, app):
    old_hash = query("SELECT passwort_hash FROM benutzer")[0]["passwort_hash"]
    response = admin.post(
        "/passwort",
        {"current_password": "geheim123", "new_password": "neuesPasswort1", "repeat_password": "neuesPasswort1"},
        follow=True,
    )
    assert response.status_code == 200
    assert "Das Passwort wurde geändert." in admin.flashes(admin.soup(response))[0]
    assert query("SELECT passwort_hash FROM benutzer")[0]["passwort_hash"] != old_hash
    admin.logout()
    assert admin.login("admin", "geheim123").status_code == 401
    assert admin.login("admin", "neuesPasswort1").status_code == 302


@pytest.mark.parametrize(
    "current,new,repeat,field",
    [
        ("falsch", "neuesPasswort1", "neuesPasswort1", "current_password"),
        ("geheim123", "kurz", "kurz", "new_password"),
        ("geheim123", "neuesPasswort1", "anders1234", "repeat_password"),
    ],
)
def test_change_password_validation(admin, query, current, new, repeat, field):
    old_hash = query("SELECT passwort_hash FROM benutzer")[0]["passwort_hash"]
    response = admin.post("/passwort", {"current_password": current, "new_password": new, "repeat_password": repeat})
    assert response.status_code == 422
    assert admin.soup(response).select_one(f"#{field}").find_parent(class_="form__field").select_one(".form__error")
    assert query("SELECT passwort_hash FROM benutzer")[0]["passwort_hash"] == old_hash


def test_unknown_page_renders_german_error_page(admin):
    response = admin.get("/gibt-es-nicht")
    assert response.status_code == 404
    assert "Nicht gefunden" in response.get_data(as_text=True)
