"""Initial schema (phase 1)

Revision ID: 0001
Revises:
Create Date: 2026-10-11 09:14:00.773066

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "benutzer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("benutzername", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("passwort_hash", sa.String(length=255), nullable=False),
        sa.Column("aktiv", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("letzter_login", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_benutzer")),
        sa.UniqueConstraint("benutzername", name=op.f("uq_benutzer_benutzername")),
        sa.UniqueConstraint("email", name=op.f("uq_benutzer_email")),
    )
    op.create_table(
        "eigentuemer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rechtsform", sa.String(length=100), nullable=False),
        sa.Column("strasse", sa.String(length=150), nullable=False),
        sa.Column("plz", sa.String(length=10), nullable=False),
        sa.Column("ort", sa.String(length=100), nullable=False),
        sa.Column(
            "vorsteuerabzugsberechtigt",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("iban", sa.String(length=34), nullable=True),
        sa.Column("bic", sa.String(length=11), nullable=True),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "geaendert_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eigentuemer")),
    )
    op.create_table(
        "kostenart",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nummer_betrkv", sa.String(length=20), nullable=False),
        sa.Column("bezeichnung", sa.String(length=255), nullable=False),
        sa.Column("verbrauchsabhaengig_moeglich", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kostenart")),
        sa.UniqueConstraint("nummer_betrkv", name=op.f("uq_kostenart_nummer_betrkv")),
    )
    op.create_table(
        "mieter",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("anrede", sa.String(length=50), nullable=True),
        sa.Column("vorname", sa.String(length=150), nullable=False),
        sa.Column("nachname", sa.String(length=150), nullable=False),
        sa.Column("telefon", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("iban", sa.String(length=34), nullable=True),
        sa.Column("bic", sa.String(length=11), nullable=True),
        sa.Column("nachsendeadresse_strasse", sa.String(length=150), nullable=True),
        sa.Column("nachsendeadresse_plz", sa.String(length=10), nullable=True),
        sa.Column("nachsendeadresse_ort", sa.String(length=100), nullable=True),
        sa.Column("nachsendeadresse_gueltig_ab", sa.Date(), nullable=True),
        sa.Column("notizen", sa.Text(), nullable=True),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "geaendert_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mieter")),
    )
    op.create_table(
        "verteilerschluessel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("bezeichnung", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verteilerschluessel")),
        sa.UniqueConstraint("code", name=op.f("uq_verteilerschluessel_code")),
    )
    op.create_table(
        "zaehlertyp",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bezeichnung", sa.String(length=100), nullable=False),
        sa.Column("einheit", sa.String(length=20), nullable=False),
        sa.Column("aktiv", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zaehlertyp")),
    )
    op.create_table(
        "objekt",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("eigentuemer_id", sa.Integer(), nullable=False),
        sa.Column("bezeichnung", sa.String(length=255), nullable=False),
        sa.Column("strasse", sa.String(length=150), nullable=False),
        sa.Column("hausnummer", sa.String(length=20), nullable=False),
        sa.Column("plz", sa.String(length=10), nullable=False),
        sa.Column("ort", sa.String(length=100), nullable=False),
        sa.Column("baujahr", sa.Integer(), nullable=True),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "geaendert_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["eigentuemer_id"],
            ["eigentuemer.id"],
            name=op.f("fk_objekt_eigentuemer_id_eigentuemer"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_objekt")),
    )
    op.create_table(
        "abrechnung",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("objekt_id", sa.Integer(), nullable=False),
        sa.Column("abrechnungsjahr", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ENTWURF", "FINALISIERT", "VERSENDET", name="abrechnung_status"),
            server_default="ENTWURF",
            nullable=False,
        ),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["objekt_id"], ["objekt.id"], name=op.f("fk_abrechnung_objekt_id_objekt")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_abrechnung")),
        sa.UniqueConstraint(
            "objekt_id",
            "abrechnungsjahr",
            name=op.f("uq_abrechnung_objekt_id_abrechnungsjahr"),
        ),
    )
    op.create_table(
        "kosten",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("objekt_id", sa.Integer(), nullable=False),
        sa.Column("kostenart_id", sa.Integer(), nullable=False),
        sa.Column("betrag_gesamt", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("rechnungsdatum", sa.Date(), nullable=False),
        sa.Column("leistungszeitraum_von", sa.Date(), nullable=False),
        sa.Column("leistungszeitraum_bis", sa.Date(), nullable=False),
        sa.Column(
            "abgrenzungsart",
            sa.Enum(
                "ABFLUSSPRINZIP",
                "PERIODENGERECHT_TAGESGENAU",
                "PERIODENGERECHT_ZAEHLERSTAND",
                name="kosten_abgrenzungsart",
            ),
            nullable=False,
        ),
        sa.Column("lieferant", sa.String(length=255), nullable=True),
        sa.Column("beschreibung", sa.Text(), nullable=True),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "geaendert_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "leistungszeitraum_bis >= leistungszeitraum_von",
            name=op.f("ck_kosten_leistungszeitraum"),
        ),
        sa.ForeignKeyConstraint(
            ["kostenart_id"],
            ["kostenart.id"],
            name=op.f("fk_kosten_kostenart_id_kostenart"),
        ),
        sa.ForeignKeyConstraint(["objekt_id"], ["objekt.id"], name=op.f("fk_kosten_objekt_id_objekt")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kosten")),
    )
    op.create_table(
        "objekt_kostenart_konfiguration",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("objekt_id", sa.Integer(), nullable=False),
        sa.Column("kostenart_id", sa.Integer(), nullable=False),
        sa.Column("verteilerschluessel_id", sa.Integer(), nullable=False),
        sa.Column("ist_verbrauchsabhaengig", sa.Boolean(), nullable=False),
        sa.Column(
            "grundkosten_anteil_prozent",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        sa.Column("zaehlertyp_id", sa.Integer(), nullable=True),
        sa.Column("gueltig_ab", sa.Date(), nullable=False),
        sa.Column("gueltig_bis", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["kostenart_id"],
            ["kostenart.id"],
            name=op.f("fk_objekt_kostenart_konfiguration_kostenart_id_kostenart"),
        ),
        sa.ForeignKeyConstraint(
            ["objekt_id"],
            ["objekt.id"],
            name=op.f("fk_objekt_kostenart_konfiguration_objekt_id_objekt"),
        ),
        sa.ForeignKeyConstraint(
            ["verteilerschluessel_id"],
            ["verteilerschluessel.id"],
            name=op.f("fk_objekt_kostenart_konfiguration_verteilerschluessel_id_verteilerschluessel"),
        ),
        sa.ForeignKeyConstraint(
            ["zaehlertyp_id"],
            ["zaehlertyp.id"],
            name=op.f("fk_objekt_kostenart_konfiguration_zaehlertyp_id_zaehlertyp"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_objekt_kostenart_konfiguration")),
        sa.UniqueConstraint(
            "objekt_id",
            "kostenart_id",
            "gueltig_ab",
            name=op.f("uq_objekt_kostenart_konfiguration_objekt_id_kostenart_id_gueltig_ab"),
        ),
    )
    op.create_table(
        "wohneinheit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("objekt_id", sa.Integer(), nullable=False),
        sa.Column("bezeichnung", sa.String(length=255), nullable=False),
        sa.Column("typ", sa.Enum("WOHNUNG", "GEWERBE", name="wohneinheit_typ"), nullable=False),
        sa.Column("wohnflaeche_m2", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("miteigentumsanteile", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("verfuegbar_ab", sa.Date(), nullable=False),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "geaendert_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["objekt_id"], ["objekt.id"], name=op.f("fk_wohneinheit_objekt_id_objekt")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wohneinheit")),
        sa.UniqueConstraint(
            "objekt_id",
            "bezeichnung",
            name=op.f("uq_wohneinheit_objekt_id_bezeichnung"),
        ),
    )
    op.create_table(
        "kosten_beleg",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kosten_id", sa.Integer(), nullable=False),
        sa.Column("dateiname", sa.String(length=255), nullable=False),
        sa.Column("speicherreferenz", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=False),
        sa.Column(
            "hochgeladen_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["kosten_id"], ["kosten.id"], name=op.f("fk_kosten_beleg_kosten_id_kosten")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kosten_beleg")),
    )
    op.create_table(
        "mietverhaeltnis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wohneinheit_id", sa.Integer(), nullable=False),
        sa.Column("mieter_id", sa.Integer(), nullable=False),
        sa.Column("einzugsdatum", sa.Date(), nullable=False),
        sa.Column("auszugsdatum", sa.Date(), nullable=True),
        sa.Column("personenanzahl", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "geaendert_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "auszugsdatum IS NULL OR auszugsdatum >= einzugsdatum",
            name=op.f("ck_mietverhaeltnis_auszug_nach_einzug"),
        ),
        sa.ForeignKeyConstraint(
            ["mieter_id"],
            ["mieter.id"],
            name=op.f("fk_mietverhaeltnis_mieter_id_mieter"),
        ),
        sa.ForeignKeyConstraint(
            ["wohneinheit_id"],
            ["wohneinheit.id"],
            name=op.f("fk_mietverhaeltnis_wohneinheit_id_wohneinheit"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mietverhaeltnis")),
    )
    op.create_table(
        "zaehler",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("zaehlertyp_id", sa.Integer(), nullable=False),
        sa.Column("wohneinheit_id", sa.Integer(), nullable=True),
        sa.Column("objekt_id", sa.Integer(), nullable=True),
        sa.Column("externe_geraete_id", sa.String(length=100), nullable=False),
        sa.Column("einbaudatum", sa.Date(), nullable=False),
        sa.Column("ausbaudatum", sa.Date(), nullable=True),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "wohneinheit_id IS NOT NULL OR objekt_id IS NOT NULL",
            name=op.f("ck_zaehler_zuordnung"),
        ),
        sa.ForeignKeyConstraint(["objekt_id"], ["objekt.id"], name=op.f("fk_zaehler_objekt_id_objekt")),
        sa.ForeignKeyConstraint(
            ["wohneinheit_id"],
            ["wohneinheit.id"],
            name=op.f("fk_zaehler_wohneinheit_id_wohneinheit"),
        ),
        sa.ForeignKeyConstraint(
            ["zaehlertyp_id"],
            ["zaehlertyp.id"],
            name=op.f("fk_zaehler_zaehlertyp_id_zaehlertyp"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zaehler")),
        sa.UniqueConstraint("externe_geraete_id", name=op.f("uq_zaehler_externe_geraete_id")),
    )
    op.create_table(
        "abrechnungsposition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("abrechnung_id", sa.Integer(), nullable=False),
        sa.Column("mietverhaeltnis_id", sa.Integer(), nullable=False),
        sa.Column("zeitraum_von", sa.Date(), nullable=False),
        sa.Column("zeitraum_bis", sa.Date(), nullable=False),
        sa.Column("nutzungstage", sa.Integer(), nullable=False),
        sa.Column(
            "vorauszahlung_erhalten",
            sa.Numeric(precision=10, scale=2),
            server_default="0",
            nullable=False,
        ),
        sa.Column("kostenanteil_gesamt", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("saldo", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("zustelladresse_strasse", sa.String(length=150), nullable=False),
        sa.Column("zustelladresse_plz", sa.String(length=10), nullable=False),
        sa.Column("zustelladresse_ort", sa.String(length=100), nullable=False),
        sa.Column(
            "erstellt_am",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["abrechnung_id"],
            ["abrechnung.id"],
            name=op.f("fk_abrechnungsposition_abrechnung_id_abrechnung"),
        ),
        sa.ForeignKeyConstraint(
            ["mietverhaeltnis_id"],
            ["mietverhaeltnis.id"],
            name=op.f("fk_abrechnungsposition_mietverhaeltnis_id_mietverhaeltnis"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_abrechnungsposition")),
        sa.UniqueConstraint(
            "abrechnung_id",
            "mietverhaeltnis_id",
            name=op.f("uq_abrechnungsposition_abrechnung_id_mietverhaeltnis_id"),
        ),
    )
    op.create_table(
        "zaehlerstand",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("zaehler_id", sa.Integer(), nullable=False),
        sa.Column("ablesedatum", sa.Date(), nullable=False),
        sa.Column("stand", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column(
            "quelle",
            sa.Enum("SCHNITTSTELLE", "MANUELL", name="zaehlerstand_quelle"),
            nullable=False,
        ),
        sa.Column("importiert_am", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(
            ["zaehler_id"],
            ["zaehler.id"],
            name=op.f("fk_zaehlerstand_zaehler_id_zaehler"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zaehlerstand")),
        sa.UniqueConstraint(
            "zaehler_id",
            "ablesedatum",
            name=op.f("uq_zaehlerstand_zaehler_id_ablesedatum"),
        ),
    )
    op.create_table(
        "abrechnungsposition_kostenart",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("abrechnungsposition_id", sa.Integer(), nullable=False),
        sa.Column("kostenart_id", sa.Integer(), nullable=False),
        sa.Column("verteilerschluessel_id", sa.Integer(), nullable=False),
        sa.Column("betrag", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("grundkosten_betrag", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("verbrauchskosten_betrag", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("verbrauchswert", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("anteil_prozent", sa.Numeric(precision=7, scale=4), nullable=True),
        sa.ForeignKeyConstraint(
            ["abrechnungsposition_id"],
            ["abrechnungsposition.id"],
            name=op.f("fk_abrechnungsposition_kostenart_abrechnungsposition_id_abrechnungsposition"),
        ),
        sa.ForeignKeyConstraint(
            ["kostenart_id"],
            ["kostenart.id"],
            name=op.f("fk_abrechnungsposition_kostenart_kostenart_id_kostenart"),
        ),
        sa.ForeignKeyConstraint(
            ["verteilerschluessel_id"],
            ["verteilerschluessel.id"],
            name=op.f("fk_abrechnungsposition_kostenart_verteilerschluessel_id_verteilerschluessel"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_abrechnungsposition_kostenart")),
    )
    op.create_table(
        "kosten_jahresanteil",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kosten_id", sa.Integer(), nullable=False),
        sa.Column("abrechnungsjahr", sa.Integer(), nullable=False),
        sa.Column("betrag_anteil", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("berechnungsgrundlage", sa.Text(), nullable=False),
        sa.Column("referenz_zaehlerstand_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["kosten_id"],
            ["kosten.id"],
            name=op.f("fk_kosten_jahresanteil_kosten_id_kosten"),
        ),
        sa.ForeignKeyConstraint(
            ["referenz_zaehlerstand_id"],
            ["zaehlerstand.id"],
            name=op.f("fk_kosten_jahresanteil_referenz_zaehlerstand_id_zaehlerstand"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kosten_jahresanteil")),
    )

    _seed_catalogs()


# Cost types per § 2 BetrKV (specification 3.6): (number, name, consumption-based possible)
COST_TYPES = [
    (1, "Grundsteuer", False),
    (2, "Kosten der Wasserversorgung", True),
    (3, "Kosten der Entwässerung", False),
    (4, "Kosten der Heizungsanlage", True),
    (5, "Kosten der Warmwasserversorgung", True),
    (6, "Kosten verbundener Heizungs-/Warmwasseranlagen", True),
    (7, "Kosten des Aufzugs", False),
    (8, "Straßenreinigung und Müllbeseitigung", False),
    (9, "Gebäudereinigung und Ungezieferbekämpfung", False),
    (10, "Gartenpflege", False),
    (11, "Beleuchtung", True),
    (12, "Schornsteinreinigung", False),
    (13, "Sach- und Haftpflichtversicherung", False),
    (14, "Hauswart", False),
    (15, "Gemeinschafts-Antenne/Kabelanschluss", False),
    (16, "Einrichtungen der Wäschepflege", False),
    (17, "Sonstige Betriebskosten", False),
]

# Allocation keys (specification 3.7)
ALLOCATION_KEYS = [
    (1, "WOHNFLAECHE", "nach m²"),
    (2, "PERSONENANZAHL", "nach Personenzahl"),
    (3, "ANZAHL_EINHEITEN", "nach Anzahl Wohneinheiten"),
    (4, "MITEIGENTUMSANTEILE", "nach MEA"),
    (5, "VERBRAUCH", "nach gemessenem Verbrauch"),
]

# Initial meter types (specification 3.8, extensible catalog): (name, unit)
METER_TYPES = [
    ("Heizung", "kWh"),
    ("Warmwasser", "m³"),
    ("Kaltwasser", "m³"),
    ("Allgemeinstrom", "kWh"),
]


def _seed_catalogs():
    cost_type = sa.table(
        "kostenart",
        sa.column("id", sa.Integer),
        sa.column("nummer_betrkv", sa.String),
        sa.column("bezeichnung", sa.String),
        sa.column("verbrauchsabhaengig_moeglich", sa.Boolean),
    )
    op.bulk_insert(
        cost_type,
        [
            {
                "id": number,
                "nummer_betrkv": f"2 Nr. {number}",
                "bezeichnung": name,
                "verbrauchsabhaengig_moeglich": consumption,
            }
            for number, name, consumption in COST_TYPES
        ],
    )

    allocation_key = sa.table(
        "verteilerschluessel",
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("bezeichnung", sa.String),
    )
    op.bulk_insert(
        allocation_key,
        [{"id": i, "code": code, "bezeichnung": name} for i, code, name in ALLOCATION_KEYS],
    )

    meter_type = sa.table(
        "zaehlertyp",
        sa.column("bezeichnung", sa.String),
        sa.column("einheit", sa.String),
        sa.column("aktiv", sa.Boolean),
    )
    op.bulk_insert(
        meter_type,
        [{"bezeichnung": name, "einheit": unit, "aktiv": True} for name, unit in METER_TYPES],
    )


def downgrade():
    op.drop_table("kosten_jahresanteil")
    op.drop_table("abrechnungsposition_kostenart")
    op.drop_table("zaehlerstand")
    op.drop_table("abrechnungsposition")
    op.drop_table("zaehler")
    op.drop_table("mietverhaeltnis")
    op.drop_table("kosten_beleg")
    op.drop_table("wohneinheit")
    op.drop_table("objekt_kostenart_konfiguration")
    op.drop_table("kosten")
    op.drop_table("abrechnung")
    op.drop_table("objekt")
    op.drop_table("zaehlertyp")
    op.drop_table("verteilerschluessel")
    op.drop_table("mieter")
    op.drop_table("kostenart")
    op.drop_table("eigentuemer")
    op.drop_table("benutzer")
