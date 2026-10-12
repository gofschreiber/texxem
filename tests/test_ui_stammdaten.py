"""Eigentümer, Objekte, Wohneinheiten, Mieter, Mietverhältnisse via the web interface."""

from datetime import date

import pytest

from tests.helpers import (
    OWNER,
    PROPERTY,
    UNIT,
    create_owner,
    create_property,
    create_tenancy,
    create_tenant,
    create_unit,
    setup_house,
)


def row(query, table, **where):
    clause = " AND ".join(f"{k} = :{k}" for k in where)
    rows = query(f"SELECT * FROM {table} WHERE {clause}", **where)
    assert len(rows) == 1, (table, where, rows)
    return rows[0]


def count(query, table):
    return query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]


# ---------------------------------------------------------------- Eigentümer
class TestOwner:
    def test_create(self, admin, query):
        response = admin.submit("/eigentuemer/neu", {**OWNER, "vorsteuerabzugsberechtigt": "1"})
        assert response.status_code == 200
        assert admin.flashes(admin.soup(response)) == ["Eigentümer „Muster Immobilien KG“ wurde angelegt."]
        owner = row(query, "eigentuemer", name="Muster Immobilien KG")
        assert (owner["rechtsform"], owner["strasse"], owner["plz"], owner["ort"]) == (
            "KG",
            "Weg 1",
            "12345",
            "Musterstadt",
        )
        assert owner["vorsteuerabzugsberechtigt"] == 1
        assert owner["iban"] == "DE02120300000000202051" and owner["bic"] == "BYLADEM1001"
        assert owner["erstellt_am"] is not None and owner["geaendert_am"] is not None

    def test_redirects_to_list_where_new_entry_is_listed(self, admin):
        response = admin.submit("/eigentuemer/neu", OWNER, follow=False)
        assert response.status_code == 302
        assert admin.location(response) == "/eigentuemer/"
        assert "Muster Immobilien KG" in admin.get("/eigentuemer/").get_data(as_text=True)

    def test_optional_fields_stay_null(self, admin, query):
        data = {k: v for k, v in OWNER.items() if k not in ("iban", "bic")}
        admin.submit("/eigentuemer/neu", data)
        owner = row(query, "eigentuemer", name=data["name"])
        assert owner["iban"] is None and owner["bic"] is None
        assert owner["vorsteuerabzugsberechtigt"] == 0

    def test_validation_errors_show_at_fields_and_save_nothing(self, admin, query):
        response = admin.submit(
            "/eigentuemer/neu", {"name": "", "rechtsform": "KG", "strasse": "x" * 200, "plz": "1", "ort": "o"}
        )
        assert response.status_code == 422
        soup = admin.soup(response)
        assert "Bitte korrigieren Sie die markierten Felder." in admin.flashes(soup)[0]
        errors = {
            el.find_parent(class_="form__field").select_one("input")["name"]: el.get_text()
            for el in soup.select(".form__error")
            if el.find_parent(class_="form__field")
        }
        assert errors["name"] == "Bitte ausfüllen."
        assert errors["strasse"] == "Maximal 150 Zeichen erlaubt."
        assert soup.select_one("input[name=rechtsform]")["value"] == "KG", "entered values are preserved"
        assert count(query, "eigentuemer") == 0

    def test_edit_form_is_prefilled_and_saves_changes(self, admin, query):
        owner_id = create_owner(admin, query)
        form = admin.soup(admin.get(f"/eigentuemer/{owner_id}/bearbeiten"))
        assert form.select_one("input[name=name]")["value"] == "Muster Immobilien KG"
        response = admin.submit(
            f"/eigentuemer/{owner_id}/bearbeiten", {**OWNER, "name": "Neue Firma GmbH", "rechtsform": "GmbH"}
        )
        assert "Eigentümer „Neue Firma GmbH“ wurde gespeichert." in admin.flashes(admin.soup(response))
        owner = row(query, "eigentuemer", id=owner_id)
        assert (owner["name"], owner["rechtsform"]) == ("Neue Firma GmbH", "GmbH")
        assert count(query, "eigentuemer") == 1

    def test_cancel_link_returns_without_change(self, admin, query):
        owner_id = create_owner(admin, query)
        soup = admin.soup(admin.get(f"/eigentuemer/{owner_id}/bearbeiten"))
        cancel = next(iter(soup.select(".form__actions a")))
        assert cancel.get_text() == "Abbrechen" and cancel["href"] == "/eigentuemer/"
        assert row(query, "eigentuemer", id=owner_id)["name"] == "Muster Immobilien KG"

    def test_delete_is_two_step(self, admin, query):
        owner_id = create_owner(admin, query)
        confirm = admin.get(f"/eigentuemer/{owner_id}/loeschen")
        assert confirm.status_code == 200
        assert "Muster Immobilien KG" in confirm.get_data(as_text=True)
        assert count(query, "eigentuemer") == 1, "GET must not delete"
        response = admin.delete(f"/eigentuemer/{owner_id}")
        assert "Eigentümer „Muster Immobilien KG“ wurde gelöscht." in admin.flashes(admin.soup(response))
        assert count(query, "eigentuemer") == 0

    def test_delete_with_dependency_is_refused(self, admin, query):
        owner_id = create_owner(admin, query)
        create_property(admin, query, owner_id)
        response = admin.delete(f"/eigentuemer/{owner_id}")
        assert "Wird noch verwendet von: 1 Objekt" in admin.flashes(admin.soup(response))[0]
        assert count(query, "eigentuemer") == 1 and count(query, "objekt") == 1

    def test_detail_lists_properties(self, admin, query):
        owner_id = create_owner(admin, query)
        create_property(admin, query, owner_id)
        soup = admin.soup(admin.get(f"/eigentuemer/{owner_id}"))
        assert "Hauptstraße 12" in soup.select_one(".card + .card").get_text()
        assert soup.select_one("a[href*='/objekte/neu']").get_text() == "+ Objekt"


# ---------------------------------------------------------------- Objekt / Wohneinheit
class TestPropertyAndUnit:
    def test_property_create_edit_delete(self, admin, query):
        owner_id = create_owner(admin, query)
        prop_id = create_property(admin, query, owner_id)
        prop = row(query, "objekt", id=prop_id)
        assert prop["eigentuemer_id"] == owner_id and prop["baujahr"] == 1985 and prop["hausnummer"] == "12"

        admin.submit(
            f"/objekte/{prop_id}/bearbeiten", {**PROPERTY, "eigentuemer_id": owner_id, "baujahr": "", "ort": "Neustadt"}
        )
        prop = row(query, "objekt", id=prop_id)
        assert prop["ort"] == "Neustadt" and prop["baujahr"] is None

        admin.delete(f"/objekte/{prop_id}")
        assert count(query, "objekt") == 0

    def test_property_requires_owner_selection(self, admin, query):
        response = admin.submit("/objekte/neu", {**PROPERTY, "eigentuemer_id": ""})
        assert response.status_code == 422
        assert count(query, "objekt") == 0

    def test_property_rejects_non_numeric_year(self, admin, query):
        owner_id = create_owner(admin, query)
        response = admin.submit("/objekte/neu", {**PROPERTY, "eigentuemer_id": owner_id, "baujahr": "abc"})
        assert response.status_code == 422
        assert "Bitte eine ganze Zahl eingeben." in response.get_data(as_text=True)

    def test_unit_create_stores_german_decimal_and_enum(self, admin, query):
        prop_id = create_property(admin, query, create_owner(admin, query))
        unit_id = create_unit(
            admin, query, prop_id, typ="GEWERBE", wohnflaeche_m2="1.234,5", miteigentumsanteile="125,5"
        )
        unit = row(query, "wohneinheit", id=unit_id)
        assert str(unit["wohnflaeche_m2"]) == "1234.50"
        assert str(unit["miteigentumsanteile"]) == "125.5000"
        assert unit["typ"] == "GEWERBE"
        assert unit["verfuegbar_ab"] == date(2020, 1, 1)

    @pytest.mark.parametrize(
        "field,value,message",
        [
            ("wohnflaeche_m2", "65,555", "Maximal 2 Nachkommastellen erlaubt."),
            ("wohnflaeche_m2", "1234567,00", "Wert ist zu groß"),
            ("wohnflaeche_m2", "abc", "Bitte eine Zahl eingeben."),
            ("typ", "GARAGE", "Bitte einen gültigen Eintrag auswählen."),
            ("verfuegbar_ab", "31.02.2020", "Bitte ein gültiges Datum eingeben."),
            ("verfuegbar_ab", "", "Bitte ausfüllen."),
        ],
    )
    def test_unit_validation(self, admin, query, field, value, message):
        prop_id = create_property(admin, query, create_owner(admin, query))
        response = admin.submit("/wohneinheiten/neu", {"objekt_id": prop_id, **UNIT, field: value})
        assert response.status_code == 422
        assert message in response.get_data(as_text=True)
        assert count(query, "wohneinheit") == 0

    def test_unit_name_must_be_unique_per_property(self, admin, query):
        prop_id = create_property(admin, query, create_owner(admin, query))
        create_unit(admin, query, prop_id)
        response = admin.submit("/wohneinheiten/neu", {"objekt_id": prop_id, **UNIT})
        assert response.status_code == 422
        assert "Ein Eintrag mit diesen Werten existiert bereits." in response.get_data(as_text=True)
        assert count(query, "wohneinheit") == 1

    def test_same_unit_name_in_other_property_is_allowed(self, admin, query):
        owner_id = create_owner(admin, query)
        p1 = create_property(admin, query, owner_id)
        p2 = create_property(admin, query, owner_id, bezeichnung="Nebenstraße 3")
        create_unit(admin, query, p1)
        create_unit(admin, query, p2)
        assert count(query, "wohneinheit") == 2

    def test_unit_edit_keeps_own_name_without_unique_error(self, admin, query):
        prop_id = create_property(admin, query, create_owner(admin, query))
        unit_id = create_unit(admin, query, prop_id)
        response = admin.submit(
            f"/wohneinheiten/{unit_id}/bearbeiten", {"objekt_id": prop_id, **UNIT, "wohnflaeche_m2": "70"}
        )
        assert response.status_code == 200
        assert str(row(query, "wohneinheit", id=unit_id)["wohnflaeche_m2"]) == "70.00"

    def test_unit_delete_blocked_by_tenancy_then_allowed(self, admin, query):
        house = setup_house(admin, query)
        response = admin.delete(f"/wohneinheiten/{house['unit']}")
        assert "Wird noch verwendet von: 1 Mietverhältnis" in admin.flashes(admin.soup(response))[0]
        assert count(query, "wohneinheit") == 1
        admin.delete(f"/mietverhaeltnisse/{house['tenancy']}")
        admin.delete(f"/wohneinheiten/{house['unit']}")
        assert count(query, "wohneinheit") == 0

    def test_unit_detail_shows_tenancies_and_meters(self, admin, query):
        house = setup_house(admin, query)
        soup = admin.soup(admin.get(f"/wohneinheiten/{house['unit']}"))
        titles = [h.get_text() for h in soup.select(".card__title")]
        assert titles == ["Mietverhältnisse", "Zähler"]
        assert "Mustermann, Erika" in soup.get_text()


# ---------------------------------------------------------------- Mieter
class TestTenant:
    def test_create_edit_delete(self, admin, query):
        tenant_id = create_tenant(admin, query, telefon="0123 456", notizen="Hund")
        tenant = row(query, "mieter", id=tenant_id)
        assert (tenant["vorname"], tenant["nachname"], tenant["telefon"], tenant["notizen"]) == (
            "Erika",
            "Mustermann",
            "0123 456",
            "Hund",
        )
        assert tenant["nachsendeadresse_strasse"] is None

        admin.submit(
            f"/mieter/{tenant_id}/bearbeiten",
            {
                "vorname": "Erika",
                "nachname": "Muster-Meier",
                "nachsendeadresse_strasse": "Neuer Weg 4",
                "nachsendeadresse_plz": "54321",
                "nachsendeadresse_ort": "Anderswo",
                "nachsendeadresse_gueltig_ab": "2025-01-01",
            },
        )
        tenant = row(query, "mieter", id=tenant_id)
        assert tenant["nachname"] == "Muster-Meier"
        assert tenant["nachsendeadresse_ort"] == "Anderswo" and tenant["nachsendeadresse_gueltig_ab"] == date(
            2025, 1, 1
        )

        admin.delete(f"/mieter/{tenant_id}")
        assert count(query, "mieter") == 0

    def test_email_is_validated(self, admin, query):
        response = admin.submit("/mieter/neu", {"vorname": "A", "nachname": "B", "email": "keine-mail"})
        assert response.status_code == 422
        assert "Bitte eine gültige E-Mail-Adresse eingeben." in response.get_data(as_text=True)
        assert count(query, "mieter") == 0

    def test_form_is_grouped_into_sections(self, admin):
        soup = admin.soup(admin.get("/mieter/neu"))
        assert [l.get_text() for l in soup.select("legend")] == [
            "Person",
            "Kontakt",
            "Bankverbindung",
            "Nachsendeadresse",
            "Notizen",
        ]

    def test_search_filters_list(self, admin, query):
        create_tenant(admin, query)
        create_tenant(admin, query, vorname="Max", nachname="Beispiel", email="max@example.com")
        soup = admin.soup(admin.get("/mieter/?q=Beispiel"))
        names = [td.get_text(strip=True) for td in soup.select("tbody tr td:first-child")]
        assert names == ["Beispiel, Max"]

    def test_delete_blocked_while_tenancy_exists(self, admin, query):
        house = setup_house(admin, query)
        response = admin.delete(f"/mieter/{house['tenant']}")
        assert "Wird noch verwendet von: 1 Mietverhältnis" in admin.flashes(admin.soup(response))[0]
        assert count(query, "mieter") == 1

    def test_list_shows_current_unit(self, admin, query):
        setup_house(admin, query)
        # tenancy starts 2024-03-01 and is open-ended, so it is active today
        soup = admin.soup(admin.get("/mieter/"))
        assert soup.select_one("tbody tr").select("td")[3].get_text(strip=True) == "EG links"


# ---------------------------------------------------------------- Mietverhältnis
class TestTenancy:
    @pytest.fixture
    def base(self, admin, query):
        prop_id = create_property(admin, query, create_owner(admin, query))
        return {"unit": create_unit(admin, query, prop_id), "tenant": create_tenant(admin, query), "prop": prop_id}

    def test_create_stores_values_and_defaults(self, admin, query, base):
        form = admin.soup(admin.get("/mietverhaeltnisse/neu"))
        assert form.select_one("input[name=personenanzahl]")["value"] == "1", "default is prefilled"
        tenancy_id = create_tenancy(admin, query, base["unit"], base["tenant"], "2024-03-15", "2024-12-31", "3")
        tenancy = row(query, "mietverhaeltnis", id=tenancy_id)
        assert tenancy["wohneinheit_id"] == base["unit"] and tenancy["mieter_id"] == base["tenant"]
        assert (tenancy["einzugsdatum"], tenancy["auszugsdatum"], tenancy["personenanzahl"]) == (
            date(2024, 3, 15),
            date(2024, 12, 31),
            3,
        )

    def test_open_ended_tenancy_has_null_move_out(self, admin, query, base):
        tenancy_id = create_tenancy(admin, query, base["unit"], base["tenant"])
        assert row(query, "mietverhaeltnis", id=tenancy_id)["auszugsdatum"] is None

    def test_move_out_before_move_in_is_rejected(self, admin, query, base):
        response = admin.submit(
            "/mietverhaeltnisse/neu",
            {
                "wohneinheit_id": base["unit"],
                "mieter_id": base["tenant"],
                "einzugsdatum": "2024-05-01",
                "auszugsdatum": "2024-04-30",
                "personenanzahl": "1",
            },
        )
        assert response.status_code == 422
        assert "Das Auszugsdatum darf nicht vor dem Einzugsdatum liegen." in response.get_data(as_text=True)
        assert count(query, "mietverhaeltnis") == 0

    def test_at_least_one_person(self, admin, query, base):
        response = admin.submit(
            "/mietverhaeltnisse/neu",
            {
                "wohneinheit_id": base["unit"],
                "mieter_id": base["tenant"],
                "einzugsdatum": "2024-05-01",
                "personenanzahl": "0",
            },
        )
        assert response.status_code == 422
        assert count(query, "mietverhaeltnis") == 0

    @pytest.mark.parametrize(
        "move_in,move_out",
        [
            ("2024-06-01", "2024-07-31"),  # inside
            ("2024-01-01", "2024-03-15"),  # touches the start
            ("2024-12-31", "2025-02-01"),  # touches the end
            ("2023-01-01", ""),  # open-ended, contains the existing one
            ("2024-06-01", ""),  # open-ended, starts inside
        ],
    )
    def test_overlapping_tenancy_in_same_unit_is_rejected(self, admin, query, base, move_in, move_out):
        create_tenancy(admin, query, base["unit"], base["tenant"], "2024-03-15", "2024-12-31")
        other = create_tenant(admin, query, vorname="Max", nachname="Beispiel")
        response = admin.submit(
            "/mietverhaeltnisse/neu",
            {
                "wohneinheit_id": base["unit"],
                "mieter_id": other,
                "einzugsdatum": move_in,
                "auszugsdatum": move_out,
                "personenanzahl": "1",
            },
        )
        assert response.status_code == 422
        text = response.get_data(as_text=True)
        assert "Überschneidung mit dem Mietverhältnis Mustermann, Erika (15.03.2024)" in text
        assert "15.03.2024 – 31.12.2024" in text
        assert count(query, "mietverhaeltnis") == 1

    def test_adjacent_and_other_unit_tenancies_are_allowed(self, admin, query, base):
        create_tenancy(admin, query, base["unit"], base["tenant"], "2024-03-15", "2024-12-31")
        other = create_tenant(admin, query, vorname="Max", nachname="Beispiel")
        create_tenancy(admin, query, base["unit"], other, "2025-01-01")
        second_unit = create_unit(admin, query, base["prop"], bezeichnung="OG rechts")
        create_tenancy(admin, query, second_unit, other, "2024-06-01")
        assert count(query, "mietverhaeltnis") == 3

    def test_editing_tenancy_does_not_collide_with_itself(self, admin, query, base):
        tenancy_id = create_tenancy(admin, query, base["unit"], base["tenant"], "2024-03-15", "2024-12-31")
        response = admin.submit(
            f"/mietverhaeltnisse/{tenancy_id}/bearbeiten",
            {
                "wohneinheit_id": base["unit"],
                "mieter_id": base["tenant"],
                "einzugsdatum": "2024-03-15",
                "auszugsdatum": "2024-10-31",
                "personenanzahl": "2",
            },
        )
        assert response.status_code == 200
        assert row(query, "mietverhaeltnis", id=tenancy_id)["auszugsdatum"] == date(2024, 10, 31)

    def test_move_in_before_availability_saves_with_warning(self, admin, query, base):
        response = admin.submit(
            "/mietverhaeltnisse/neu",
            {
                "wohneinheit_id": base["unit"],
                "mieter_id": base["tenant"],
                "einzugsdatum": "2019-06-01",
                "personenanzahl": "1",
            },
        )
        flashes = admin.flashes(admin.soup(response))
        assert any("wurde angelegt" in f for f in flashes)
        assert any(f.startswith("Hinweis: Das Einzugsdatum liegt vor dem Datum") and "01.01.2020" in f for f in flashes)
        assert count(query, "mietverhaeltnis") == 1

    def test_delete(self, admin, query, base):
        tenancy_id = create_tenancy(admin, query, base["unit"], base["tenant"])
        response = admin.delete(f"/mietverhaeltnisse/{tenancy_id}")
        assert "wurde gelöscht" in admin.flashes(admin.soup(response))[0]
        assert count(query, "mietverhaeltnis") == 0
        assert count(query, "mieter") == 1, "tenant master data is kept"


# ---------------------------------------------------------------- Baum Objekte & Wohneinheiten
class TestPropertyTree:
    def test_tree_structure_and_levels(self, admin, query):
        house = setup_house(admin, query)
        soup = admin.soup(admin.get("/objekte/"))
        owner = soup.select_one(".tree > details")
        assert owner["id"] == f"eigentuemer-{house['owner']}"
        prop = owner.select_one(":scope > .tree__children > details")
        unit = prop.select_one(":scope > .tree__children > details")
        tenancy = unit.select_one(":scope > .tree__children > .tree__node--leaf")
        assert prop["id"] == f"objekte-{house['property']}"
        assert unit["id"] == f"wohneinheiten-{house['unit']}"
        assert tenancy["id"] == f"mietverhaeltnisse-{house['tenancy']}"
        assert "Mustermann, Erika" in tenancy.get_text()

    def test_default_open_state_first_level_only(self, admin, query):
        house = setup_house(admin, query)
        soup = admin.soup(admin.get("/objekte/"))
        assert soup.select_one(f"#eigentuemer-{house['owner']}").has_attr("open")
        assert not soup.select_one(f"#objekte-{house['property']}").has_attr("open")

    def test_expand_all_and_collapse_all(self, admin, query):
        setup_house(admin, query)
        expanded = admin.soup(admin.get("/objekte/?expand=all"))
        assert all(d.has_attr("open") for d in expanded.select("details"))
        collapsed = admin.soup(admin.get("/objekte/?expand=none"))
        assert not any(d.has_attr("open") for d in collapsed.select("details"))
        toolbar = [a.get_text() for a in expanded.select(".toolbar a")]
        assert toolbar == ["Alle aufklappen", "Alle zuklappen"]

    def test_saved_node_is_opened_and_highlighted_after_creation(self, admin, query):
        owner_id = create_owner(admin, query)
        prop_id = create_property(admin, query, owner_id)
        response = admin.submit(
            "/wohneinheiten/neu?next=/objekte/",
            {"objekt_id": prop_id, **UNIT, "next": "/objekte/"},
            follow=False,
        )
        unit_id = query("SELECT id FROM wohneinheit")[0]["id"]
        assert response.headers["Location"] == f"/objekte/?open=wohneinheiten-{unit_id}#wohneinheiten-{unit_id}"
        soup = admin.soup(admin.get(response.headers["Location"]))
        assert soup.select_one(f"#objekte-{prop_id}").has_attr("open"), "ancestor of the saved node is expanded"

    def test_add_actions_are_on_the_parent_nodes_and_prefill_the_parent(self, admin, query):
        house = setup_house(admin, query)
        soup = admin.soup(admin.get("/objekte/"))
        owner_add = soup.select_one(f"#eigentuemer-{house['owner']} > summary a.btn--secondary")
        assert owner_add.get_text() == "+ Objekt"
        assert f"eigentuemer_id={house['owner']}" in owner_add["href"]
        unit_add = soup.select_one(f"#wohneinheiten-{house['unit']} > summary a.btn--secondary")
        assert unit_add.get_text() == "+ Mietverhältnis"
        assert f"wohneinheit_id={house['unit']}" in unit_add["href"]
        form = admin.soup(admin.get(unit_add["href"]))
        assert form.select_one("select[name=wohneinheit_id] option[selected]")["value"] == str(house["unit"])

    def test_vacancy_nodes(self, admin, query):
        house = setup_house(admin, query)
        # available since 2020-01-01, first tenancy from 2024-03-01 -> vacancy before
        create_tenancy_end = admin.submit(
            f"/mietverhaeltnisse/{house['tenancy']}/bearbeiten",
            {
                "wohneinheit_id": house["unit"],
                "mieter_id": house["tenant"],
                "einzugsdatum": "2024-03-01",
                "auszugsdatum": "2024-12-31",
                "personenanzahl": "2",
            },
        )
        assert create_tenancy_end.status_code == 200
        soup = admin.soup(admin.get("/objekte/?expand=all"))
        vacancies = [n for n in soup.select(".tree__node--leaf") if n["id"].startswith("leerstand-")]
        titles = [v.select_one(".tree__title").get_text(strip=True) for v in vacancies]
        assert "Leerstand 01.01.2020 – 29.02.2024" in titles
        assert "Leerstand 01.01.2025 – laufend" in titles
        assert all(not v.select(".actions a") for v in vacancies), "vacancy nodes are read-only"

    def test_empty_levels_show_hints(self, admin, query):
        owner_id = create_owner(admin, query)
        soup = admin.soup(admin.get("/objekte/"))
        assert "Noch keine Objekte" in soup.select_one(f"#eigentuemer-{owner_id} .tree__empty").get_text()

    def test_empty_system_offers_first_step(self, admin):
        soup = admin.soup(admin.get("/objekte/"))
        assert "Noch keine Eigentümer angelegt." in soup.select_one(".empty").get_text()
        assert soup.select_one(".card a.btn--primary").get_text() == "+ Eigentümer anlegen"
