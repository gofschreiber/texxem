"""End-to-end scenario across all areas, driven only through the web interface."""

import io
from datetime import date
from decimal import Decimal

from tests.helpers import (
    create_cost,
    create_meter,
    create_owner,
    create_property,
    create_reading,
    create_statement,
    create_tenancy,
    create_tenant,
    create_unit,
)

DATA_TABLES = [
    "abrechnung",
    "kosten_beleg",
    "kosten",
    "objekt_kostenart_konfiguration",
    "zaehlerstand",
    "zaehler",
    "mietverhaeltnis",
    "mieter",
    "wohneinheit",
    "objekt",
    "eigentuemer",
]


def test_full_year_scenario(admin, query):
    # master data
    owner = create_owner(admin, query, name="Haus KG", rechtsform="KG")
    prop = create_property(admin, query, owner, bezeichnung="Lindenweg 5")
    eg = create_unit(admin, query, prop, bezeichnung="EG", wohnflaeche_m2="60,00")
    og = create_unit(admin, query, prop, bezeichnung="OG", wohnflaeche_m2="80,00", verfuegbar_ab="2023-01-01")
    gewerbe = create_unit(admin, query, prop, bezeichnung="Laden", typ="GEWERBE", wohnflaeche_m2="45,25")

    # tenancies: tenant A moves out mid-year, tenant B follows; OG stays vacant until June
    anna = create_tenant(admin, query, vorname="Anna", nachname="Alt")
    bernd = create_tenant(admin, query, vorname="Bernd", nachname="Neu")
    t_anna = create_tenancy(admin, query, eg, anna, "2022-01-01", "2024-06-30", "1")
    t_bernd = create_tenancy(admin, query, eg, bernd, "2024-07-01", "", "3")
    t_og = create_tenancy(admin, query, og, anna, "2024-06-15", "", "2")

    # a forwarding address for the moved-out tenant
    admin.submit(
        f"/mieter/{anna}/bearbeiten",
        {
            "vorname": "Anna",
            "nachname": "Alt",
            "nachsendeadresse_strasse": "Rosenweg 1",
            "nachsendeadresse_plz": "99999",
            "nachsendeadresse_ort": "Ferne",
            "nachsendeadresse_gueltig_ab": "2024-07-01",
        },
    )

    # meters and readings
    water = create_meter(admin, query, type_id=3, unit_id=eg, device="KW-EG")
    power = create_meter(admin, query, type_id=4, property_id=prop, device="AS-1")
    for day, value in [("2024-01-01", "100"), ("2024-06-30", "160,5"), ("2024-12-31", "230,25")]:
        create_reading(admin, query, water, day, value)
    create_reading(admin, query, power, "2024-12-31", "9.876,5")

    # distribution configuration and costs
    admin.submit(
        "/verteilung/neu",
        {
            "objekt_id": prop,
            "kostenart_id": 4,
            "verteilerschluessel_id": 5,
            "ist_verbrauchsabhaengig": "1",
            "zaehlertyp_id": 1,
            "grundkosten_anteil_prozent": "30",
            "gueltig_ab": "2024-01-01",
        },
    )
    admin.submit(
        "/verteilung/neu",
        {"objekt_id": prop, "kostenart_id": 1, "verteilerschluessel_id": 1, "gueltig_ab": "2024-01-01"},
    )
    tax = create_cost(admin, query, prop, 1, "1.560,00", "2024-02-15")
    heating = create_cost(
        admin,
        query,
        prop,
        4,
        "4200,00",
        "2024-12-20",
        abgrenzungsart="PERIODENGERECHT_TAGESGENAU",
        leistungszeitraum_von="2024-07-01",
        leistungszeitraum_bis="2025-06-30",
    )
    admin.post(
        "/belege/neu",
        {
            "kosten_id": heating,
            "next": "/kosten/",
            "file": (io.BytesIO(b"%PDF heating"), "heizung.pdf", "application/pdf"),
        },
        form_url=f"/belege/neu?kosten_id={heating}",
        content_type="multipart/form-data",
    )

    statement = create_statement(admin, query, prop, 2024)
    admin.post(
        f"/abrechnungen/{statement}/status/finalisiert", {}, form_url=f"/abrechnungen/{statement}/status/finalisiert"
    )

    # ---- verify the result in the database -------------------------------------------------
    assert query("SELECT status FROM abrechnung") == [{"status": "FINALISIERT"}]
    assert {r["bezeichnung"]: r["typ"] for r in query("SELECT bezeichnung, typ FROM wohneinheit")} == {
        "EG": "WOHNUNG",
        "OG": "WOHNUNG",
        "Laden": "GEWERBE",
    }

    stays = query(
        """SELECT e.bezeichnung AS unit, CONCAT(m.vorname, ' ', m.nachname) AS tenant, t.einzugsdatum, t.auszugsdatum, t.personenanzahl
           FROM mietverhaeltnis t JOIN wohneinheit e ON e.id = t.wohneinheit_id JOIN mieter m ON m.id = t.mieter_id
           ORDER BY e.bezeichnung, t.einzugsdatum"""
    )
    assert stays == [
        {
            "unit": "EG",
            "tenant": "Anna Alt",
            "einzugsdatum": date(2022, 1, 1),
            "auszugsdatum": date(2024, 6, 30),
            "personenanzahl": 1,
        },
        {
            "unit": "EG",
            "tenant": "Bernd Neu",
            "einzugsdatum": date(2024, 7, 1),
            "auszugsdatum": None,
            "personenanzahl": 3,
        },
        {
            "unit": "OG",
            "tenant": "Anna Alt",
            "einzugsdatum": date(2024, 6, 15),
            "auszugsdatum": None,
            "personenanzahl": 2,
        },
    ]
    assert query("SELECT nachsendeadresse_ort, nachsendeadresse_gueltig_ab FROM mieter WHERE id = :i", i=anna) == [
        {"nachsendeadresse_ort": "Ferne", "nachsendeadresse_gueltig_ab": date(2024, 7, 1)}
    ]

    readings = query(
        "SELECT ablesedatum, stand, quelle FROM zaehlerstand WHERE zaehler_id = :m ORDER BY ablesedatum", m=water
    )
    assert [(r["ablesedatum"], r["stand"], r["quelle"]) for r in readings] == [
        (date(2024, 1, 1), Decimal("100.0000"), "MANUELL"),
        (date(2024, 6, 30), Decimal("160.5000"), "MANUELL"),
        (date(2024, 12, 31), Decimal("230.2500"), "MANUELL"),
    ]
    assert query("SELECT stand FROM zaehlerstand WHERE zaehler_id = :m", m=power) == [{"stand": Decimal("9876.5000")}]
    assert query("SELECT objekt_id, wohneinheit_id FROM zaehler WHERE id = :m", m=power) == [
        {"objekt_id": prop, "wohneinheit_id": None}
    ]

    assert query("SELECT SUM(betrag_gesamt) AS total FROM kosten") == [{"total": Decimal("5760.00")}]
    assert query("SELECT abgrenzungsart FROM kosten WHERE id = :c", c=heating) == [
        {"abgrenzungsart": "PERIODENGERECHT_TAGESGENAU"}
    ]
    assert query("SELECT COUNT(*) AS n FROM kosten_beleg WHERE kosten_id = :c", c=heating)[0]["n"] == 1
    cfg = query(
        "SELECT kostenart_id, ist_verbrauchsabhaengig, grundkosten_anteil_prozent FROM objekt_kostenart_konfiguration ORDER BY kostenart_id"
    )
    assert cfg == [
        {"kostenart_id": 1, "ist_verbrauchsabhaengig": 0, "grundkosten_anteil_prozent": None},
        {"kostenart_id": 4, "ist_verbrauchsabhaengig": 1, "grundkosten_anteil_prozent": Decimal("30.00")},
    ]

    # ---- the frozen year protects the costs; the overview reflects everything ----------------
    assert admin.get(f"/kosten/{tax}/bearbeiten").status_code == 403
    tree = admin.soup(admin.get("/objekte/?expand=all"))
    vacancies = [
        n.select_one(".tree__title").get_text(strip=True)
        for n in tree.select(".tree__node--leaf")
        if n["id"].startswith("leerstand-")
    ]
    assert "Leerstand 01.01.2023 – 14.06.2024" in vacancies, "OG empty before Anna moves in"
    assert "Leerstand 01.01.2020 – laufend" in vacancies, "the shop was never rented"
    dashboard = admin.soup(admin.get("/")).get_text(" ", strip=True)
    assert "Lindenweg 5" in dashboard

    # ---- tear everything down through the UI in dependency order ----------------------------
    admin.post(f"/abrechnungen/{statement}/status/entwurf", {}, form_url=f"/abrechnungen/{statement}/status/entwurf")
    admin.delete(f"/abrechnungen/{statement}")
    receipt = query("SELECT id FROM kosten_beleg")[0]["id"]
    admin.delete(f"/belege/{receipt}")
    for cost in (tax, heating):
        admin.delete(f"/kosten/{cost}")
    for cfg_id in [r["id"] for r in query("SELECT id FROM objekt_kostenart_konfiguration")]:
        admin.delete(f"/verteilung/{cfg_id}")
    for reading in [r["id"] for r in query("SELECT id FROM zaehlerstand")]:
        admin.delete(f"/zaehlerstaende/{reading}")
    for meter in (water, power):
        admin.delete(f"/zaehler/{meter}")
    for tenancy in (t_anna, t_bernd, t_og):
        admin.delete(f"/mietverhaeltnisse/{tenancy}")
    for tenant in (anna, bernd):
        admin.delete(f"/mieter/{tenant}")
    for unit in (eg, og, gewerbe):
        admin.delete(f"/wohneinheiten/{unit}")
    admin.delete(f"/objekte/{prop}")
    admin.delete(f"/eigentuemer/{owner}")

    for table in DATA_TABLES:
        assert query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"] == 0, table
    assert query("SELECT COUNT(*) AS n FROM kostenart")[0]["n"] == 17, "catalog untouched"
