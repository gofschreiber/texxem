"""Kostenpositionen, Belege, Verteilung, Kostenarten via the web interface."""

import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tests.helpers import (
    create_cost,
    create_statement,
    setup_house,
)


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


class TestCost:
    def test_create_stores_all_values(self, admin, query, house):
        cost_id = create_cost(admin, query, house["property"], cost_type_id=1, beschreibung="Jahresbescheid")
        cost = row(query, "kosten", id=cost_id)
        assert cost["objekt_id"] == house["property"] and cost["kostenart_id"] == 1
        assert cost["betrag_gesamt"] == Decimal("1200.00")
        assert (cost["rechnungsdatum"], cost["leistungszeitraum_von"], cost["leistungszeitraum_bis"]) == (
            date(2024, 5, 1),
            date(2024, 1, 1),
            date(2024, 12, 31),
        )
        assert cost["abgrenzungsart"] == "ABFLUSSPRINZIP"
        assert (cost["lieferant"], cost["beschreibung"]) == ("Stadtwerke", "Jahresbescheid")

    def test_flash_message_names_cost_item(self, admin, query, house):
        response = admin.submit(
            "/kosten/neu",
            {
                "objekt_id": house["property"],
                "kostenart_id": 1,
                "betrag_gesamt": "99,90",
                "rechnungsdatum": "2024-02-02",
                "leistungszeitraum_von": "2024-01-01",
                "leistungszeitraum_bis": "2024-12-31",
                "abgrenzungsart": "PERIODENGERECHT_TAGESGENAU",
            },
        )
        assert admin.flashes(admin.soup(response)) == [
            "Kostenposition „Grundsteuer, 99,90 € (02.02.2024)“ wurde angelegt."
        ]
        assert row(query, "kosten", betrag_gesamt="99.90")["abgrenzungsart"] == "PERIODENGERECHT_TAGESGENAU"

    @pytest.mark.parametrize(
        "overrides,message",
        [
            (
                {"leistungszeitraum_von": "2024-12-31", "leistungszeitraum_bis": "2024-01-01"},
                "Das Ende des Leistungszeitraums darf nicht vor dem Beginn liegen.",
            ),
            ({"betrag_gesamt": "0"}, "Der Betrag darf nicht 0 sein."),
            ({"betrag_gesamt": "100000000,00"}, "Wert ist zu groß"),
            ({"betrag_gesamt": "12,345"}, "Maximal 2 Nachkommastellen erlaubt."),
            ({"abgrenzungsart": "SONSTIGES"}, "Bitte einen gültigen Eintrag auswählen."),
            ({"kostenart_id": "99"}, "Bitte einen gültigen Eintrag auswählen."),
        ],
    )
    def test_validation(self, admin, query, house, overrides, message):
        data = {
            "objekt_id": house["property"],
            "kostenart_id": 1,
            "betrag_gesamt": "100",
            "rechnungsdatum": "2024-05-01",
            "leistungszeitraum_von": "2024-01-01",
            "leistungszeitraum_bis": "2024-12-31",
            "abgrenzungsart": "ABFLUSSPRINZIP",
            **overrides,
        }
        response = admin.submit("/kosten/neu", data)
        assert response.status_code == 422
        assert message in response.get_data(as_text=True)
        assert count(query, "kosten") == 0

    def test_negative_amount_credit_note_is_allowed(self, admin, query, house):
        cost_id = create_cost(admin, query, house["property"], amount="-50,00")
        assert row(query, "kosten", id=cost_id)["betrag_gesamt"] == Decimal("-50.00")

    def test_edit_and_delete(self, admin, query, house):
        cost_id = create_cost(admin, query, house["property"])
        admin.submit(
            f"/kosten/{cost_id}/bearbeiten",
            {
                "objekt_id": house["property"],
                "kostenart_id": 8,
                "betrag_gesamt": "1300,50",
                "rechnungsdatum": "2024-05-01",
                "leistungszeitraum_von": "2024-01-01",
                "leistungszeitraum_bis": "2024-12-31",
                "abgrenzungsart": "ABFLUSSPRINZIP",
            },
        )
        cost = row(query, "kosten", id=cost_id)
        assert (cost["kostenart_id"], cost["betrag_gesamt"], cost["lieferant"]) == (8, Decimal("1300.50"), None)
        admin.delete(f"/kosten/{cost_id}")
        assert count(query, "kosten") == 0

    def test_tree_groups_by_year_and_cost_type(self, admin, query, house):
        c1 = create_cost(admin, query, house["property"], cost_type_id=1, invoice="2024-05-01")
        c2 = create_cost(admin, query, house["property"], cost_type_id=1, amount="300,00", invoice="2024-06-01")
        c3 = create_cost(admin, query, house["property"], cost_type_id=8, amount="80,00", invoice="2023-12-01")
        soup = admin.soup(admin.get("/kosten/?expand=all"))
        prop = soup.select_one(f"#objekte-{house['property']}")
        year_ids = [d["id"] for d in prop.select(":scope > .tree__children > details")]
        assert year_ids == [f"jahr-{house['property']}-2024", f"jahr-{house['property']}-2023"], "newest year first"
        grundsteuer = prop.select_one(f"#kostenart-{house['property']}-2024-1")
        assert [n["id"] for n in grundsteuer.select(".tree__node--leaf, details") if n["id"].startswith("kosten-")] == [
            f"kosten-{c2}",
            f"kosten-{c1}",
        ]
        assert "1.500,00 €" in grundsteuer.select_one("summary").get_text(), "cost type node shows the sum"
        assert prop.select_one(f"#kosten-{c3}") is not None

    def test_tree_add_action_prefills_property_and_cost_type(self, admin, query, house):
        create_cost(admin, query, house["property"], cost_type_id=1)
        soup = admin.soup(admin.get("/kosten/?expand=all"))
        add = soup.select_one(f"#kostenart-{house['property']}-2024-1 > summary a.btn--secondary")
        assert add.get_text() == "+ Kostenposition"
        form = admin.soup(admin.get(add["href"]))
        assert form.select_one("select[name=objekt_id] option[selected]")["value"] == str(house["property"])
        assert form.select_one("select[name=kostenart_id] option[selected]")["value"] == "1"


class TestReceipt:
    @pytest.fixture
    def cost(self, admin, query, house):
        return create_cost(admin, query, house["property"])

    def upload(self, admin, cost_id, content=b"%PDF-1.4 test", name="rechnung 2024.pdf", mime="application/pdf"):
        url = f"/belege/neu?kosten_id={cost_id}&next=/kosten/{cost_id}"
        return admin.post(
            "/belege/neu",
            {"kosten_id": cost_id, "next": f"/kosten/{cost_id}", "file": (io.BytesIO(content), name, mime)},
            form_url=url,
            follow=True,
            content_type="multipart/form-data",
        )

    def test_upload_stores_file_and_database_row(self, admin, query, app, cost):
        response = self.upload(admin, cost)
        assert response.status_code == 200
        assert admin.flashes(admin.soup(response)) == ["Beleg „rechnung 2024.pdf“ wurde angelegt."]
        receipt = row(query, "kosten_beleg", kosten_id=cost)
        assert receipt["dateiname"] == "rechnung 2024.pdf" and receipt["mime_type"] == "application/pdf"
        assert receipt["hochgeladen_am"] is not None
        stored = Path(app.config["UPLOAD_DIRECTORY"]) / receipt["speicherreferenz"]
        assert receipt["speicherreferenz"].startswith(f"{cost}/") and ".." not in receipt["speicherreferenz"]
        assert stored.read_bytes() == b"%PDF-1.4 test"
        assert "_test" in stored.parts, "test mode writes below uploads/_test"

    def test_download_returns_the_file(self, admin, query, cost):
        self.upload(admin, cost, content=b"hello beleg")
        receipt = row(query, "kosten_beleg", kosten_id=cost)
        response = admin.get(f"/belege/{receipt['id']}/download")
        assert response.status_code == 200
        assert response.data == b"hello beleg"
        assert "rechnung 2024.pdf" in response.headers["Content-Disposition"]

    def test_hostile_file_name_is_neutralised(self, admin, query, app, cost):
        self.upload(admin, cost, name="../../etc/passwd")
        receipt = row(query, "kosten_beleg", kosten_id=cost)
        assert receipt["dateiname"] == "passwd"
        assert ".." not in receipt["speicherreferenz"]
        assert (Path(app.config["UPLOAD_DIRECTORY"]) / receipt["speicherreferenz"]).exists()

    def test_missing_file_is_rejected(self, admin, query, cost):
        response = admin.post(
            "/belege/neu",
            {"kosten_id": cost, "next": f"/kosten/{cost}"},
            form_url=f"/belege/neu?kosten_id={cost}",
            content_type="multipart/form-data",
        )
        assert response.status_code == 422
        assert "Bitte eine Datei auswählen." in response.get_data(as_text=True)
        assert count(query, "kosten_beleg") == 0

    def test_unknown_cost_is_rejected(self, admin, query, cost):
        response = self.upload(admin, 9999)
        assert response.status_code == 422
        assert count(query, "kosten_beleg") == 0

    def test_delete_removes_row_and_file(self, admin, query, app, cost):
        self.upload(admin, cost)
        receipt = row(query, "kosten_beleg", kosten_id=cost)
        stored = Path(app.config["UPLOAD_DIRECTORY"]) / receipt["speicherreferenz"]
        assert stored.exists()
        response = admin.delete(f"/belege/{receipt['id']}", next_url=f"/kosten/{cost}")
        assert admin.flashes(admin.soup(response)) == ["Beleg „rechnung 2024.pdf“ wurde gelöscht."]
        assert count(query, "kosten_beleg") == 0
        assert not stored.exists()

    def test_receipts_are_not_editable(self, admin, query, cost):
        self.upload(admin, cost)
        receipt_id = row(query, "kosten_beleg", kosten_id=cost)["id"]
        assert admin.get(f"/belege/{receipt_id}/bearbeiten").status_code == 404

    def test_cost_with_receipt_cannot_be_deleted(self, admin, query, cost):
        self.upload(admin, cost)
        response = admin.delete(f"/kosten/{cost}")
        assert "Wird noch verwendet von: 1 Beleg" in admin.flashes(admin.soup(response))[0]
        assert count(query, "kosten") == 1

    def test_detail_and_tree_show_receipt_with_actions(self, admin, query, cost):
        self.upload(admin, cost)
        receipt_id = row(query, "kosten_beleg", kosten_id=cost)["id"]
        detail = admin.soup(admin.get(f"/kosten/{cost}"))
        assert detail.select_one("a[href*='/belege/neu']").get_text() == "+ Beleg hochladen"
        assert detail.select_one(f"#belege-{receipt_id}") is not None
        tree = admin.soup(admin.get("/kosten/?expand=all"))
        labels = [a["aria-label"] for a in tree.select(f"#belege-{receipt_id} .actions a")]
        assert labels == ["Anzeigen", "Löschen"]


class TestDistribution:
    """Verteilung: configuration of the allocation key per cost type and property."""

    def data(self, house, **overrides):
        return {
            "objekt_id": house["property"],
            "kostenart_id": 4,
            "verteilerschluessel_id": 1,
            "zaehlertyp_id": "",
            "gueltig_ab": "2024-01-01",
            **overrides,
        }

    def test_tree_lists_all_17_cost_types_unconfigured(self, admin, house):
        soup = admin.soup(admin.get("/verteilung/"))
        types = soup.select(f"#objekte-{house['property']} > .tree__children > .tree__node")
        assert len(types) == 17
        assert all("nicht konfiguriert" in t.get_text() for t in types)
        assert "2 Nr. 4: Kosten der Heizungsanlage" in types[3].get_text()

    def test_create_heating_with_base_cost_split(self, admin, query, house):
        response = admin.submit(
            "/verteilung/neu",
            self.data(
                house,
                ist_verbrauchsabhaengig="1",
                zaehlertyp_id=1,
                grundkosten_anteil_prozent="30",
                verteilerschluessel_id=5,
            ),
        )
        assert response.status_code == 200
        cfg = row(query, "objekt_kostenart_konfiguration", kostenart_id=4)
        assert (cfg["verteilerschluessel_id"], cfg["ist_verbrauchsabhaengig"], cfg["zaehlertyp_id"]) == (5, 1, 1)
        assert cfg["grundkosten_anteil_prozent"] == Decimal("30.00")
        assert cfg["gueltig_ab"] == date(2024, 1, 1) and cfg["gueltig_bis"] is None

    def test_create_simple_area_based_configuration(self, admin, query, house):
        admin.submit("/verteilung/neu", self.data(house, kostenart_id=1))
        cfg = row(query, "objekt_kostenart_konfiguration", kostenart_id=1)
        assert (
            cfg["verteilerschluessel_id"],
            cfg["ist_verbrauchsabhaengig"],
            cfg["grundkosten_anteil_prozent"],
            cfg["zaehlertyp_id"],
        ) == (1, 0, None, None)

    @pytest.mark.parametrize(
        "overrides,message",
        [
            (
                {"kostenart_id": 1, "ist_verbrauchsabhaengig": "1", "zaehlertyp_id": 3},
                "Diese Kostenart kann nicht verbrauchsabhängig verteilt werden.",
            ),
            ({"ist_verbrauchsabhaengig": "1"}, "Bei verbrauchsabhängiger Verteilung ist ein Zählertyp erforderlich."),
            (
                {"verteilerschluessel_id": 5},
                "Für den Schlüssel „nach gemessenem Verbrauch“ ist ein Zählertyp erforderlich.",
            ),
            (
                {"grundkosten_anteil_prozent": "30"},
                "Ein Grundkostenanteil ist nur bei verbrauchsabhängiger Verteilung möglich.",
            ),
            (
                {"ist_verbrauchsabhaengig": "1", "zaehlertyp_id": 1, "grundkosten_anteil_prozent": "100,01"},
                "Der Grundkostenanteil muss zwischen 0 und 100 liegen.",
            ),
            ({"gueltig_bis": "2023-12-31"}, "Das Ende der Gültigkeit darf nicht vor dem Beginn liegen."),
        ],
    )
    def test_validation(self, admin, query, house, overrides, message):
        response = admin.submit("/verteilung/neu", self.data(house, **overrides))
        assert response.status_code == 422
        assert message in response.get_data(as_text=True)
        assert count(query, "objekt_kostenart_konfiguration") == 0

    def test_same_start_date_is_rejected_by_unique_rule(self, admin, query, house):
        admin.submit("/verteilung/neu", self.data(house))
        response = admin.submit("/verteilung/neu", self.data(house, verteilerschluessel_id=3))
        assert response.status_code == 422
        assert "existiert bereits eine Konfiguration mit diesem Gültigkeitsbeginn" in response.get_data(as_text=True)
        assert count(query, "objekt_kostenart_konfiguration") == 1

    def test_overlapping_validity_is_rejected_but_sequential_versions_are_fine(self, admin, query, house):
        admin.submit("/verteilung/neu", self.data(house, gueltig_bis="2024-12-31"))
        overlap = admin.submit("/verteilung/neu", self.data(house, gueltig_ab="2024-06-01"))
        assert overlap.status_code == 422
        assert "überschneidet sich mit der Konfiguration ab 01.01.2024" in overlap.get_data(as_text=True)
        admin.submit("/verteilung/neu", self.data(house, gueltig_ab="2025-01-01", verteilerschluessel_id=3))
        assert count(query, "objekt_kostenart_konfiguration") == 2

    def test_cost_type_and_property_are_fixed_when_editing(self, admin, query, house):
        admin.submit("/verteilung/neu", self.data(house))
        cfg_id = query("SELECT id FROM objekt_kostenart_konfiguration")[0]["id"]
        soup = admin.soup(admin.get(f"/verteilung/{cfg_id}/bearbeiten"))
        assert soup.select_one("select[name=kostenart_id]") is None
        assert "Kosten der Heizungsanlage" in soup.select_one("#f-kostenart_id").get_text()
        admin.submit(
            f"/verteilung/{cfg_id}/bearbeiten",
            {"kostenart_id": 8, "verteilerschluessel_id": 3, "gueltig_ab": "2024-01-01"},
        )
        cfg = row(query, "objekt_kostenart_konfiguration", id=cfg_id)
        assert (cfg["kostenart_id"], cfg["verteilerschluessel_id"]) == (4, 3), "only editable fields change"

    def test_tree_shows_versions_below_cost_type(self, admin, query, house):
        admin.submit("/verteilung/neu", self.data(house, gueltig_bis="2024-12-31"))
        cfg_id = query("SELECT id FROM objekt_kostenart_konfiguration")[0]["id"]
        soup = admin.soup(admin.get(f"/verteilung/?open=verteilung-{cfg_id}"))
        node = soup.select_one(f"#kostenart-{house['property']}-4")
        assert node.has_attr("open")
        assert "nicht konfiguriert" not in node.select_one("summary").get_text()
        version = node.select_one(f"#verteilung-{cfg_id}")
        assert "ab 01.01.2024 bis 31.12.2024" in version.get_text()
        assert [a["aria-label"] for a in version.select(".actions a")] == ["Anzeigen", "Bearbeiten", "Löschen"]

    def test_delete_configuration(self, admin, query, house):
        admin.submit("/verteilung/neu", self.data(house))
        cfg_id = query("SELECT id FROM objekt_kostenart_konfiguration")[0]["id"]
        admin.delete(f"/verteilung/{cfg_id}")
        assert count(query, "objekt_kostenart_konfiguration") == 0

    def test_delete_blocked_when_statement_exists_for_period(self, admin, query, house):
        admin.submit("/verteilung/neu", self.data(house, gueltig_bis="2024-12-31"))
        cfg_id = query("SELECT id FROM objekt_kostenart_konfiguration")[0]["id"]
        create_statement(admin, query, house["property"], 2024)
        response = admin.delete(f"/verteilung/{cfg_id}")
        assert "Für den Zeitraum existiert bereits eine Abrechnung." in admin.flashes(admin.soup(response))[0]
        assert count(query, "objekt_kostenart_konfiguration") == 1


class TestCostTypeCatalog:
    def test_list_shows_all_17_read_only(self, admin):
        soup = admin.soup(admin.get("/kostenarten/"))
        rows = soup.select("tbody tr")
        assert len(rows) == 17
        assert rows[3].select("td")[0].get_text() == "2 Nr. 4"
        assert rows[3].select("td")[2].get_text() == "Ja" and rows[0].select("td")[2].get_text() == "Nein"
        assert not soup.select(".page-header__actions a"), "no create action"
        assert not soup.select("tbody .actions a"), "no row actions"

    @pytest.mark.parametrize("path", ["/kostenarten/neu", "/kostenarten/1/bearbeiten", "/kostenarten/1/loeschen"])
    def test_catalog_cannot_be_changed(self, admin, query, path):
        assert admin.get(path).status_code == 404
        assert admin.post(path, {"bezeichnung": "x"}, form_url="/kostenarten/").status_code == 404
        assert query("SELECT bezeichnung FROM kostenart WHERE id = 1")[0]["bezeichnung"] == "Grundsteuer"


class TestCostLock:
    """A7: costs are frozen once a statement of an affected year is finalised."""

    def test_finalised_statement_locks_cost_actions(self, admin, query, house):
        cost_id = create_cost(admin, query, house["property"])
        statement_id = create_statement(admin, query, house["property"], 2024)

        soup = admin.soup(admin.get("/kosten/?expand=all"))
        summary = soup.select_one(f"#kosten-{cost_id} > .tree__summary")
        assert [a["aria-label"] for a in summary.select(".actions a[aria-label]")] == [
            "Anzeigen",
            "Bearbeiten",
            "Löschen",
        ]

        admin.post(
            f"/abrechnungen/{statement_id}/status/finalisiert",
            {},
            form_url=f"/abrechnungen/{statement_id}/status/finalisiert",
            follow=True,
        )
        assert row(query, "abrechnung", id=statement_id)["status"] == "FINALISIERT"

        soup = admin.soup(admin.get("/kosten/?expand=all"))
        node = soup.select_one(f"#kosten-{cost_id}")
        row_el = node.select_one(".tree__summary")
        assert "Gesperrt" in row_el.get_text()
        assert [a["aria-label"] for a in row_el.select(".actions a[aria-label]")] == ["Anzeigen"]
        assert admin.get(f"/kosten/{cost_id}/bearbeiten").status_code == 403
        assert admin.post(f"/kosten/{cost_id}/loeschen", {}, form_url="/kosten/").status_code == 403
        assert row(query, "kosten", id=cost_id)["betrag_gesamt"] == Decimal("1200.00")

    def test_draft_statement_does_not_lock(self, admin, query, house):
        cost_id = create_cost(admin, query, house["property"])
        create_statement(admin, query, house["property"], 2024)
        assert admin.get(f"/kosten/{cost_id}/bearbeiten").status_code == 200

    def test_other_year_does_not_lock(self, admin, query, house):
        cost_id = create_cost(admin, query, house["property"])
        statement_id = create_statement(admin, query, house["property"], 2022)
        admin.post(
            f"/abrechnungen/{statement_id}/status/finalisiert",
            {},
            form_url=f"/abrechnungen/{statement_id}/status/finalisiert",
        )
        assert admin.get(f"/kosten/{cost_id}/bearbeiten").status_code == 200
