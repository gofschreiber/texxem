"""Zählertypen, Zähler, Zählerstände via the web interface."""

from datetime import date
from decimal import Decimal

import pytest

from tests.helpers import (
    create_meter,
    create_reading,
    setup_house,
)


def row(query, table, **where):
    clause = " AND ".join(f"{k} = :{k}" for k in where)
    rows = query(f"SELECT * FROM {table} WHERE {clause}", **where)
    assert len(rows) == 1, (table, where, rows)
    return rows[0]


def count(query, table):
    return query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]


class TestMeterType:
    def test_seed_types_are_listed(self, admin):
        soup = admin.soup(admin.get("/zaehlertypen/"))
        names = [tr.select("td")[0].get_text(strip=True) for tr in soup.select("tbody tr")]
        assert names == ["Allgemeinstrom", "Heizung", "Kaltwasser", "Warmwasser"]

    def test_create_edit_delete(self, admin, query):
        admin.submit("/zaehlertypen/neu", {"bezeichnung": "Fernwärme", "einheit": "MWh", "aktiv": "1"})
        meter_type = row(query, "zaehlertyp", bezeichnung="Fernwärme")
        assert (meter_type["einheit"], meter_type["aktiv"]) == ("MWh", 1)
        assert meter_type["id"] == 5, "new type is appended to the seeded catalog"

        admin.submit(f"/zaehlertypen/{meter_type['id']}/bearbeiten", {"bezeichnung": "Fernwärme", "einheit": "kWh"})
        meter_type = row(query, "zaehlertyp", id=meter_type["id"])
        assert (meter_type["einheit"], meter_type["aktiv"]) == ("kWh", 0), "unchecked box stores false"

        admin.delete(f"/zaehlertypen/{meter_type['id']}")
        assert count(query, "zaehlertyp") == 4

    def test_required_fields(self, admin, query):
        response = admin.submit("/zaehlertypen/neu", {"bezeichnung": "", "einheit": ""})
        assert response.status_code == 422
        assert response.get_data(as_text=True).count("Bitte ausfüllen.") == 2
        assert count(query, "zaehlertyp") == 4

    def test_delete_blocked_when_meter_uses_type(self, admin, query):
        house = setup_house(admin, query)
        create_meter(admin, query, type_id=3, unit_id=house["unit"])
        response = admin.delete("/zaehlertypen/3")
        assert "Wird noch verwendet von: 1 Zähler" in admin.flashes(admin.soup(response))[0]
        assert row(query, "zaehlertyp", id=3)["bezeichnung"] == "Kaltwasser"


class TestMeter:
    @pytest.fixture
    def house(self, admin, query):
        return setup_house(admin, query)

    def test_create_for_unit(self, admin, query, house):
        meter_id = create_meter(admin, query, type_id=2, unit_id=house["unit"], device="WW-100", installed="2021-05-01")
        meter = row(query, "zaehler", id=meter_id)
        assert (meter["zaehlertyp_id"], meter["wohneinheit_id"], meter["objekt_id"]) == (2, house["unit"], None)
        assert meter["einbaudatum"] == date(2021, 5, 1) and meter["ausbaudatum"] is None
        assert meter["erstellt_am"] is not None

    def test_create_property_wide_meter(self, admin, query, house):
        meter_id = create_meter(admin, query, type_id=4, property_id=house["property"], device="STROM-1")
        meter = row(query, "zaehler", id=meter_id)
        assert meter["wohneinheit_id"] is None and meter["objekt_id"] == house["property"]

    def test_assignment_is_required(self, admin, query):
        response = admin.submit(
            "/zaehler/neu", {"zaehlertyp_id": 3, "externe_geraete_id": "X", "einbaudatum": "2020-01-01"}
        )
        assert response.status_code == 422
        assert "Bitte eine Wohneinheit oder ein Objekt zuordnen." in response.get_data(as_text=True)
        assert count(query, "zaehler") == 0

    def test_removal_before_installation_is_rejected(self, admin, query, house):
        response = admin.submit(
            "/zaehler/neu",
            {
                "zaehlertyp_id": 3,
                "wohneinheit_id": house["unit"],
                "externe_geraete_id": "X",
                "einbaudatum": "2022-01-01",
                "ausbaudatum": "2021-12-31",
            },
        )
        assert response.status_code == 422
        assert "Das Ausbaudatum darf nicht vor dem Einbaudatum liegen." in response.get_data(as_text=True)
        assert count(query, "zaehler") == 0

    def test_external_device_id_must_be_unique(self, admin, query, house):
        create_meter(admin, query, unit_id=house["unit"], device="DUP")
        response = admin.submit(
            "/zaehler/neu",
            {
                "zaehlertyp_id": 2,
                "wohneinheit_id": house["unit"],
                "externe_geraete_id": "DUP",
                "einbaudatum": "2020-01-01",
            },
        )
        assert response.status_code == 422
        assert "Ein Eintrag mit diesen Werten existiert bereits." in response.get_data(as_text=True)
        assert count(query, "zaehler") == 1

    def test_replace_device_by_setting_removal_date(self, admin, query, house):
        meter_id = create_meter(admin, query, unit_id=house["unit"])
        admin.submit(
            f"/zaehler/{meter_id}/bearbeiten",
            {
                "zaehlertyp_id": 3,
                "wohneinheit_id": house["unit"],
                "externe_geraete_id": "DEV-001",
                "einbaudatum": "2020-01-01",
                "ausbaudatum": "2024-06-30",
            },
        )
        assert row(query, "zaehler", id=meter_id)["ausbaudatum"] == date(2024, 6, 30)

    def test_delete_blocked_while_readings_exist(self, admin, query, house):
        meter_id = create_meter(admin, query, unit_id=house["unit"])
        reading_id = create_reading(admin, query, meter_id)
        response = admin.delete(f"/zaehler/{meter_id}")
        assert "Wird noch verwendet von: 1 Zählerstand" in admin.flashes(admin.soup(response))[0]
        assert count(query, "zaehler") == 1
        admin.delete(f"/zaehlerstaende/{reading_id}")
        admin.delete(f"/zaehler/{meter_id}")
        assert count(query, "zaehler") == 0

    def test_tree_structure(self, admin, query, house):
        unit_meter = create_meter(admin, query, unit_id=house["unit"], device="UNIT-1")
        prop_meter = create_meter(admin, query, type_id=4, property_id=house["property"], device="PROP-1")
        create_reading(admin, query, unit_meter, "2024-01-01", "10")
        create_reading(admin, query, unit_meter, "2024-02-01", "20")
        soup = admin.soup(admin.get("/zaehler/?expand=all"))
        prop = soup.select_one(f"#objekte-{house['property']}")
        unit = prop.select_one(f"#wohneinheiten-{house['unit']}")
        wide = prop.select_one(f"#objektweit-{house['property']}")
        assert unit.select_one(f"#zaehler-{unit_meter}") is not None
        assert wide.select_one(f"#zaehler-{prop_meter}") is not None
        leaf = unit.select_one(f"#zaehlerstaende-zaehler-{unit_meter}")
        assert leaf.select_one(".tree__title").get_text(strip=True) == "Zählerstände (2)"
        assert leaf.select_one(".tree__title a")["href"] == f"/zaehlerstaende/?zaehler_id={unit_meter}"
        assert "01.02.2024" in leaf.get_text()

    def test_detail_shows_latest_readings(self, admin, query, house):
        meter_id = create_meter(admin, query, unit_id=house["unit"])
        create_reading(admin, query, meter_id, "2024-01-01", "10")
        soup = admin.soup(admin.get(f"/zaehler/{meter_id}"))
        assert "Letzte Zählerstände" in soup.get_text()
        assert soup.select_one("a[href*='/zaehlerstaende/neu']").get_text() == "+ Zählerstand"


class TestReading:
    @pytest.fixture
    def meter(self, admin, query):
        house = setup_house(admin, query)
        return create_meter(admin, query, unit_id=house["unit"])

    def test_manual_reading_is_stored_as_manual(self, admin, query, meter):
        reading_id = create_reading(admin, query, meter, "2024-12-31", "1.234,5678")
        reading = row(query, "zaehlerstand", id=reading_id)
        assert reading["quelle"] == "MANUELL"
        assert reading["stand"] == Decimal("1234.5678")
        assert reading["ablesedatum"] == date(2024, 12, 31)
        assert reading["importiert_am"] is None

    def test_one_reading_per_meter_and_day(self, admin, query, meter):
        create_reading(admin, query, meter, "2024-12-31", "100")
        response = admin.submit(
            "/zaehlerstaende/neu", {"zaehler_id": meter, "ablesedatum": "2024-12-31", "stand": "200"}
        )
        assert response.status_code == 422
        assert "Für dieses Datum existiert bereits ein Zählerstand." in response.get_data(as_text=True)
        assert [r["stand"] for r in query("SELECT stand FROM zaehlerstand")] == [Decimal("100.0000")]

    def test_same_day_on_other_meter_is_allowed(self, admin, query, meter):
        house = query("SELECT wohneinheit_id FROM zaehler")[0]["wohneinheit_id"]
        other = create_meter(admin, query, type_id=2, unit_id=house, device="OTHER")
        create_reading(admin, query, meter, "2024-12-31", "100")
        create_reading(admin, query, other, "2024-12-31", "5")
        assert count(query, "zaehlerstand") == 2

    @pytest.mark.parametrize(
        "field,value,message",
        [
            ("stand", "abc", "Bitte eine Zahl eingeben."),
            ("stand", "1,23456", "Maximal 4 Nachkommastellen erlaubt."),
            ("ablesedatum", "", "Bitte ausfüllen."),
        ],
    )
    def test_validation(self, admin, query, meter, field, value, message):
        data = {"zaehler_id": meter, "ablesedatum": "2024-01-01", "stand": "1", field: value}
        response = admin.submit("/zaehlerstaende/neu", data)
        assert response.status_code == 422
        assert message in response.get_data(as_text=True)
        assert count(query, "zaehlerstand") == 0

    def test_edit_and_delete_manual_reading(self, admin, query, meter):
        reading_id = create_reading(admin, query, meter, "2024-12-31", "100")
        admin.submit(
            f"/zaehlerstaende/{reading_id}/bearbeiten",
            {"zaehler_id": meter, "ablesedatum": "2024-12-31", "stand": "150,5"},
        )
        assert row(query, "zaehlerstand", id=reading_id)["stand"] == Decimal("150.5000")
        assert row(query, "zaehlerstand", id=reading_id)["quelle"] == "MANUELL"
        admin.delete(f"/zaehlerstaende/{reading_id}")
        assert count(query, "zaehlerstand") == 0

    def test_new_form_from_meter_prefills_meter_and_returns_there(self, admin, query, meter):
        soup = admin.soup(admin.get(f"/zaehlerstaende/neu?zaehler_id={meter}&next=/zaehler/"))
        assert soup.select_one("select[name=zaehler_id] option[selected]")["value"] == str(meter)
        assert soup.select_one("input[name=next]")["value"] == "/zaehler/"

    def test_interface_readings_are_read_only(self, admin, query, meter):
        query_reading = """INSERT INTO zaehlerstand (zaehler_id, ablesedatum, stand, quelle, importiert_am)
                           VALUES (:m, '2024-06-30', 500.0000, 'SCHNITTSTELLE', NOW())"""
        from sqlalchemy import text

        with admin.client.application.test_engine.begin() as conn:
            conn.execute(text(query_reading), {"m": meter})
        reading_id = query("SELECT id FROM zaehlerstand")[0]["id"]

        # no edit/delete actions offered, only "Anzeigen"
        soup = admin.soup(admin.get(f"/zaehlerstaende/?zaehler_id={meter}"))
        actions = [a["aria-label"] for a in soup.select("tbody tr .actions a")]
        assert actions == ["Anzeigen"]
        assert "Schnittstelle" in soup.select_one("tbody tr .badge").get_text()

        # direct requests are rejected
        assert admin.get(f"/zaehlerstaende/{reading_id}/bearbeiten").status_code == 403
        assert (
            admin.post(
                f"/zaehlerstaende/{reading_id}/bearbeiten",
                {"zaehler_id": meter, "ablesedatum": "2024-06-30", "stand": "1"},
            ).status_code
            == 403
        )
        assert admin.get(f"/zaehlerstaende/{reading_id}/loeschen").status_code == 403
        assert admin.post(f"/zaehlerstaende/{reading_id}/loeschen", {}, form_url="/zaehlerstaende/").status_code == 403
        stored = row(query, "zaehlerstand", id=reading_id)
        assert stored["stand"] == Decimal("500.0000") and stored["quelle"] == "SCHNITTSTELLE"

    def test_manual_value_cannot_replace_interface_value_of_same_day(self, admin, query, meter):
        from sqlalchemy import text

        with admin.client.application.test_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO zaehlerstand (zaehler_id, ablesedatum, stand, quelle) VALUES (:m, '2024-06-30', 500, 'SCHNITTSTELLE')"
                ),
                {"m": meter},
            )
        response = admin.submit(
            "/zaehlerstaende/neu", {"zaehler_id": meter, "ablesedatum": "2024-06-30", "stand": "999"}
        )
        assert response.status_code == 422
        assert query("SELECT stand, quelle FROM zaehlerstand") == [
            {"stand": Decimal("500.0000"), "quelle": "SCHNITTSTELLE"}
        ]

    def test_list_filters_by_meter_and_period_and_is_ordered_newest_first(self, admin, query, meter):
        house = query("SELECT wohneinheit_id FROM zaehler")[0]["wohneinheit_id"]
        other = create_meter(admin, query, type_id=2, unit_id=house, device="OTHER")
        for day in ("2024-01-31", "2024-02-29", "2024-03-31"):
            create_reading(admin, query, meter, day, "1")
        create_reading(admin, query, other, "2024-02-29", "9")

        def dates(url):
            soup = admin.soup(admin.get(url))
            return [tr.select("td")[1].get_text(strip=True) for tr in soup.select("tbody tr")]

        assert dates(f"/zaehlerstaende/?zaehler_id={meter}") == ["31.03.2024", "29.02.2024", "31.01.2024"]
        assert dates(f"/zaehlerstaende/?zaehler_id={meter}&von=2024-02-01&bis=2024-03-01") == ["29.02.2024"]
        assert len(dates("/zaehlerstaende/")) == 4

    def test_pagination_after_25_rows(self, admin, query, meter):
        from sqlalchemy import text

        with admin.client.application.test_engine.begin() as conn:
            for i in range(30):
                conn.execute(
                    text(
                        "INSERT INTO zaehlerstand (zaehler_id, ablesedatum, stand, quelle) VALUES (:m, DATE_ADD('2024-01-01', INTERVAL :i DAY), :i, 'MANUELL')"
                    ),
                    {"m": meter, "i": i},
                )
        page1 = admin.soup(admin.get("/zaehlerstaende/"))
        assert len(page1.select("tbody tr")) == 25
        assert "Seite 1 von 2" in page1.select_one(".pagination").get_text()
        page2 = admin.soup(admin.get("/zaehlerstaende/?page=2"))
        assert len(page2.select("tbody tr")) == 5
