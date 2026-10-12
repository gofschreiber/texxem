"""Create test data through the web interface (forms), returning the new database ids."""

from datetime import date

OWNER = {
    "name": "Muster Immobilien KG",
    "rechtsform": "KG",
    "strasse": "Weg 1",
    "plz": "12345",
    "ort": "Musterstadt",
    "iban": "DE02120300000000202051",
    "bic": "BYLADEM1001",
}
PROPERTY = {
    "bezeichnung": "Hauptstraße 12",
    "strasse": "Hauptstraße",
    "hausnummer": "12",
    "plz": "12345",
    "ort": "Musterstadt",
    "baujahr": "1985",
}
UNIT = {"bezeichnung": "EG links", "typ": "WOHNUNG", "wohnflaeche_m2": "65,50", "verfuegbar_ab": "2020-01-01"}
TENANT = {"anrede": "Frau", "vorname": "Erika", "nachname": "Mustermann", "email": "erika@example.com"}


def _id(query, table: str, where: str, **params) -> int:
    rows = query(f"SELECT id FROM {table} WHERE {where}", **params)
    assert len(rows) == 1, f"expected exactly one row in {table} for {where} {params}, got {len(rows)}"
    return rows[0]["id"]


def create(ui, url: str, data: dict) -> None:
    response = ui.submit(url, data)
    assert response.status_code == 200, f"{url}: {response.status_code}\n{response.get_data(as_text=True)[:2000]}"
    errors = ui.soup(response).select(".form__error")
    assert not errors, f"{url}: unexpected form errors {[e.get_text() for e in errors]}"


def create_owner(ui, query, **overrides) -> int:
    data = {**OWNER, **overrides}
    create(ui, "/eigentuemer/neu", data)
    return _id(query, "eigentuemer", "name = :n", n=data["name"])


def create_property(ui, query, owner_id: int, **overrides) -> int:
    data = {"eigentuemer_id": owner_id, **PROPERTY, **overrides}
    create(ui, "/objekte/neu", data)
    return _id(query, "objekt", "bezeichnung = :n", n=data["bezeichnung"])


def create_unit(ui, query, property_id: int, **overrides) -> int:
    data = {"objekt_id": property_id, **UNIT, **overrides}
    create(ui, "/wohneinheiten/neu", data)
    return _id(query, "wohneinheit", "objekt_id = :o AND bezeichnung = :n", o=property_id, n=data["bezeichnung"])


def create_tenant(ui, query, **overrides) -> int:
    data = {**TENANT, **overrides}
    create(ui, "/mieter/neu", data)
    return _id(query, "mieter", "vorname = :v AND nachname = :n", v=data["vorname"], n=data["nachname"])


def create_tenancy(ui, query, unit_id: int, tenant_id: int, move_in="2024-03-01", move_out="", persons="2") -> int:
    create(
        ui,
        "/mietverhaeltnisse/neu",
        {
            "wohneinheit_id": unit_id,
            "mieter_id": tenant_id,
            "einzugsdatum": move_in,
            "auszugsdatum": move_out,
            "personenanzahl": persons,
        },
    )
    return _id(query, "mietverhaeltnis", "wohneinheit_id = :u AND einzugsdatum = :d", u=unit_id, d=move_in)


def create_meter(ui, query, type_id=3, unit_id="", property_id="", device="DEV-001", installed="2020-01-01") -> int:
    create(
        ui,
        "/zaehler/neu",
        {
            "zaehlertyp_id": type_id,
            "wohneinheit_id": unit_id,
            "objekt_id": property_id,
            "externe_geraete_id": device,
            "einbaudatum": installed,
        },
    )
    return _id(query, "zaehler", "externe_geraete_id = :d", d=device)


def create_reading(ui, query, meter_id: int, day="2024-12-31", value="1234,5678") -> int:
    create(ui, "/zaehlerstaende/neu", {"zaehler_id": meter_id, "ablesedatum": day, "stand": value})
    return _id(query, "zaehlerstand", "zaehler_id = :m AND ablesedatum = :d", m=meter_id, d=day)


def create_cost(
    ui, query, property_id: int, cost_type_id=1, amount="1200,00", invoice="2024-05-01", **overrides
) -> int:
    data = {
        "objekt_id": property_id,
        "kostenart_id": cost_type_id,
        "betrag_gesamt": amount,
        "rechnungsdatum": invoice,
        "leistungszeitraum_von": "2024-01-01",
        "leistungszeitraum_bis": "2024-12-31",
        "abgrenzungsart": "ABFLUSSPRINZIP",
        "lieferant": "Stadtwerke",
        **overrides,
    }
    create(ui, "/kosten/neu", data)
    return _id(
        query,
        "kosten",
        "objekt_id = :o AND betrag_gesamt = :b AND rechnungsdatum = :d",
        o=property_id,
        b=amount.replace(".", "").replace(",", "."),
        d=invoice,
    )


def create_statement(ui, query, property_id: int, year=2024) -> int:
    create(ui, "/abrechnungen/neu", {"objekt_id": property_id, "abrechnungsjahr": year})
    return _id(query, "abrechnung", "objekt_id = :o AND abrechnungsjahr = :y", o=property_id, y=year)


def setup_house(ui, query) -> dict:
    """Owner → property → unit → tenant → tenancy, all created via the UI."""
    owner = create_owner(ui, query)
    prop = create_property(ui, query, owner)
    unit = create_unit(ui, query, prop)
    tenant = create_tenant(ui, query)
    tenancy = create_tenancy(ui, query, unit, tenant)
    return {"owner": owner, "property": prop, "unit": unit, "tenant": tenant, "tenancy": tenancy}


def today_iso() -> str:
    return date.today().isoformat()
