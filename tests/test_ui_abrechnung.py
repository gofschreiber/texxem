"""Abrechnungen: creation, status workflow and deletion rules via the web interface."""

from datetime import date
from decimal import Decimal

import pytest

from tests.helpers import create_cost, create_statement, setup_house


def row(query, table, **where):
    clause = " AND ".join(f"{k} = :{k}" for k in where)
    rows = query(f"SELECT * FROM {table} WHERE {clause}", **where)
    assert len(rows) == 1, (table, where, rows)
    return rows[0]


def count(query, table):
    return query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]


@pytest.fixture
def house(admin, query):
    return setup_house(admin, query)


def change_status(admin, statement_id, target, *, follow=True):
    url = f"/abrechnungen/{statement_id}/status/{target}"
    page = admin.get(url)
    assert page.status_code == 200, f"{url} -> {page.status_code}"
    return admin.post(url, {}, form_url=url, follow=follow)


def status(query, statement_id):
    return row(query, "abrechnung", id=statement_id)["status"]


def test_create_statement_starts_as_draft(admin, query, house):
    response = admin.submit("/abrechnungen/neu", {"objekt_id": house["property"], "abrechnungsjahr": "2024"})
    assert admin.flashes(admin.soup(response)) == ["Abrechnung „Hauptstraße 12 2024“ wurde angelegt."]
    statement = row(query, "abrechnung", objekt_id=house["property"])
    assert (statement["abrechnungsjahr"], statement["status"]) == (2024, "ENTWURF")
    assert statement["erstellt_am"] is not None


def test_one_statement_per_property_and_year(admin, query, house):
    create_statement(admin, query, house["property"], 2024)
    response = admin.submit("/abrechnungen/neu", {"objekt_id": house["property"], "abrechnungsjahr": "2024"})
    assert response.status_code == 422
    assert "Für dieses Objekt und Jahr existiert bereits eine Abrechnung." in response.get_data(as_text=True)
    assert count(query, "abrechnung") == 1
    create_statement(admin, query, house["property"], 2025)
    assert count(query, "abrechnung") == 2


@pytest.mark.parametrize(
    "year,message",
    [
        ("1999", "Bitte ein Jahr zwischen 2000 und 2100 eingeben."),
        ("2101", "Bitte ein Jahr zwischen 2000 und 2100 eingeben."),
        ("abc", "Bitte eine ganze Zahl eingeben."),
        ("", "Bitte ausfüllen."),
    ],
)
def test_year_validation(admin, query, house, year, message):
    response = admin.submit("/abrechnungen/neu", {"objekt_id": house["property"], "abrechnungsjahr": year})
    assert response.status_code == 422
    assert message in response.get_data(as_text=True)
    assert count(query, "abrechnung") == 0


def test_statements_cannot_be_edited(admin, query, house):
    statement_id = create_statement(admin, query, house["property"])
    assert admin.get(f"/abrechnungen/{statement_id}/bearbeiten").status_code == 404


def test_status_workflow_forward_and_back(admin, query, house):
    statement_id = create_statement(admin, query, house["property"])

    response = change_status(admin, statement_id, "finalisiert")
    assert "hat jetzt den Status „Finalisiert“" in admin.flashes(admin.soup(response))[0]
    assert status(query, statement_id) == "FINALISIERT"

    change_status(admin, statement_id, "entwurf")
    assert status(query, statement_id) == "ENTWURF"

    change_status(admin, statement_id, "finalisiert")
    change_status(admin, statement_id, "versendet")
    assert status(query, statement_id) == "VERSENDET"


def test_confirmation_page_precedes_status_change(admin, query, house):
    statement_id = create_statement(admin, query, house["property"])
    page = admin.soup(admin.get(f"/abrechnungen/{statement_id}/status/finalisiert"))
    assert "auf „Finalisiert“ gesetzt werden" in page.select_one("form p").get_text()
    assert [b.get_text() for b in page.select(".form__actions > *")] == ["Finalisieren", "Abbrechen"]
    assert status(query, statement_id) == "ENTWURF", "GET does not change the status"


@pytest.mark.parametrize(
    "start,target",
    [
        ("ENTWURF", "versendet"),
        ("ENTWURF", "entwurf"),
        ("FINALISIERT", "finalisiert"),
        ("VERSENDET", "entwurf"),
        ("VERSENDET", "finalisiert"),
        ("ENTWURF", "unsinn"),
    ],
)
def test_invalid_transitions_are_rejected(admin, query, house, start, target):
    statement_id = create_statement(admin, query, house["property"])
    if start != "ENTWURF":
        change_status(admin, statement_id, "finalisiert")
    if start == "VERSENDET":
        change_status(admin, statement_id, "versendet")
    assert status(query, statement_id) == start
    url = f"/abrechnungen/{statement_id}/status/{target}"
    assert admin.get(url).status_code == 403
    assert admin.post(url, {}, form_url=f"/abrechnungen/{statement_id}").status_code == 403
    assert status(query, statement_id) == start


def test_status_change_requires_post(admin, query, house):
    statement_id = create_statement(admin, query, house["property"])
    admin.get(f"/abrechnungen/{statement_id}/status/finalisiert")
    assert status(query, statement_id) == "ENTWURF"


def test_delete_draft(admin, query, house):
    statement_id = create_statement(admin, query, house["property"])
    response = admin.delete(f"/abrechnungen/{statement_id}")
    assert "wurde gelöscht" in admin.flashes(admin.soup(response))[0]
    assert count(query, "abrechnung") == 0


@pytest.mark.parametrize("final_status", ["finalisiert", "versendet"])
def test_only_drafts_can_be_deleted(admin, query, house, final_status):
    statement_id = create_statement(admin, query, house["property"])
    change_status(admin, statement_id, "finalisiert")
    if final_status == "versendet":
        change_status(admin, statement_id, "versendet")

    assert admin.get(f"/abrechnungen/{statement_id}/loeschen").status_code == 403
    assert admin.post(f"/abrechnungen/{statement_id}/loeschen", {}, form_url="/abrechnungen/").status_code == 403
    assert count(query, "abrechnung") == 1
    soup = admin.soup(admin.get("/abrechnungen/?expand=all"))
    labels = [
        a.get("aria-label")
        for a in soup.select(
            f"#abrechnungen-{statement_id} > summary .actions a[aria-label], #abrechnungen-{statement_id} > .tree__summary .actions a[aria-label]"
        )
    ]
    assert "Löschen" not in labels and "Anzeigen" in labels


def test_tree_shows_statement_with_status_badge_and_status_action(admin, query, house):
    statement_id = create_statement(admin, query, house["property"], 2024)
    soup = admin.soup(admin.get("/abrechnungen/?expand=all"))
    node = soup.select_one(f"#abrechnungen-{statement_id}")
    summary = node.select_one(":scope > summary")
    assert "Abrechnung 2024" in summary.get_text()
    assert summary.select_one(".badge").get_text() == "Entwurf"
    actions = [a.get_text(strip=True) or a["aria-label"] for a in summary.select(".actions a")]
    assert actions == ["Finalisieren", "Anzeigen", "Löschen"], (
        "status action first, then the uniform view/edit/delete order"
    )
    assert "Noch keine Abrechnungspositionen" in node.select_one(".tree__empty").get_text()


def test_tree_shows_generated_positions_and_cost_lines(admin, query, house, app):
    """Positions are produced by the (future) calculation engine; the tree must display them."""
    from sqlalchemy import text

    statement_id = create_statement(admin, query, house["property"], 2024)
    with app.test_engine.begin() as conn:
        conn.execute(
            text(
                """INSERT INTO abrechnungsposition (abrechnung_id, mietverhaeltnis_id, zeitraum_von, zeitraum_bis, nutzungstage,
                       vorauszahlung_erhalten, kostenanteil_gesamt, saldo, zustelladresse_strasse, zustelladresse_plz, zustelladresse_ort)
                   VALUES (:s, :t, '2024-03-01', '2024-12-31', 306, 500, 650.25, 150.25, 'Hauptstraße 12', '12345', 'Musterstadt')"""
            ),
            {"s": statement_id, "t": house["tenancy"]},
        )
        item_id = conn.execute(text("SELECT id FROM abrechnungsposition")).scalar()
        conn.execute(
            text(
                "INSERT INTO abrechnungsposition_kostenart (abrechnungsposition_id, kostenart_id, verteilerschluessel_id, betrag) VALUES (:i, 1, 1, 650.25)"
            ),
            {"i": item_id},
        )
    soup = admin.soup(admin.get("/abrechnungen/?expand=all"))
    item = soup.select_one(f"#abrechnungsposition-{item_id}")
    assert "Mustermann, Erika" in item.get_text()
    assert "650,25 €" in item.get_text() and "150,25 €" in item.get_text()
    assert item.select_one(".badge").get_text() == "Nachzahlung"
    line = item.select_one(".tree__node--leaf")
    assert "Grundsteuer" in line.get_text() and "nach m²" in line.get_text()
    assert not line.select(".actions a"), "generated lines are read-only"

    detail = admin.soup(admin.get(f"/abrechnungen/{statement_id}"))
    assert "Die Positionen werden vom Abrechnungslauf" in detail.get_text()
    assert detail.select_one("tbody tr").select("td")[-2].get_text(strip=True) == "150,25 €"
    assert statement_id and Decimal("150.25")


def test_statement_with_items_cannot_be_deleted_while_draft_has_dependencies(admin, query, house, app):
    from sqlalchemy import text

    statement_id = create_statement(admin, query, house["property"], 2024)
    with app.test_engine.begin() as conn:
        conn.execute(
            text(
                """INSERT INTO abrechnungsposition (abrechnung_id, mietverhaeltnis_id, zeitraum_von, zeitraum_bis, nutzungstage,
                       kostenanteil_gesamt, saldo, zustelladresse_strasse, zustelladresse_plz, zustelladresse_ort)
                   VALUES (:s, :t, '2024-03-01', '2024-12-31', 306, 1, 1, 'a', '1', 'c')"""
            ),
            {"s": statement_id, "t": house["tenancy"]},
        )
    response = admin.delete(f"/abrechnungen/{statement_id}")
    assert "Wird noch verwendet von: 1 Abrechnungsposition" in admin.flashes(admin.soup(response))[0]
    assert count(query, "abrechnung") == 1


def test_dashboard_reports_drafts_and_previous_year_status(admin, query, house):
    last_year = date.today().year - 1
    statement_id = create_statement(admin, query, house["property"], last_year)
    soup = admin.soup(admin.get("/"))
    assert f"Abrechnung {last_year}" in soup.select_one(".card").get_text()
    assert soup.select_one(".card .badge").get_text() == "Entwurf"
    hint = soup.select_one(".hints a")
    assert hint["href"] == f"/abrechnungen/{statement_id}"
    assert admin.get(hint["href"]).status_code == 200
    change_status(admin, statement_id, "finalisiert")
    assert not admin.soup(admin.get("/")).select(".hints")


def test_cost_for_statement_year_remains_independent_data(admin, query, house):
    create_cost(admin, query, house["property"])
    statement_id = create_statement(admin, query, house["property"], 2024)
    assert count(query, "kosten") == 1 and status(query, statement_id) == "ENTWURF"
