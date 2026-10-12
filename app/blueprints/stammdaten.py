"""Stammdaten: Eigentümer, Objekte & Wohneinheiten, Mieter, Mietverhältnisse."""

from datetime import date

import sqlalchemy as sa
from flask import Blueprint, render_template, request

from app.extensions import db
from app.models import Owner, Property, TenancyAgreement, Tenant, Unit
from app.services.vacancy import vacancy_periods
from app.ui import choices
from app.ui.context import active_property_id
from app.ui.crud import REGISTRY, apply_open_state, register_crud
from app.ui.fields import Field
from app.ui.formatting import fmt_date, fmt_decimal
from app.ui.resource import ChildTable, Column, Node, Resource

bp = Blueprint("stammdaten", __name__)


def _period(start: date | None, end: date | None) -> str:
    return f"{fmt_date(start)} – {fmt_date(end) if end else 'laufend'}"


class OwnerResource(Resource):
    slug = "eigentuemer"
    model = Owner
    singular = "Eigentümer"
    plural = "Eigentümer"
    fields = [
        Field("name", "Name", section="Stammdaten"),
        Field("legal_form", "Rechtsform", section="Stammdaten", help="z. B. KG, natürliche Person"),
        Field("street", "Straße", section="Anschrift"),
        Field("postal_code", "PLZ", section="Anschrift"),
        Field("city", "Ort", section="Anschrift"),
        Field("input_tax_deductible", "Vorsteuerabzugsberechtigt", section="Steuer", help="Nur informativ"),
        Field("iban", "IBAN", section="Bankverbindung"),
        Field("bic", "BIC", section="Bankverbindung"),
    ]
    columns = [
        Column("Name", "name", link=True),
        Column("Rechtsform", "legal_form"),
        Column("Ort", lambda o: f"{o.postal_code} {o.city}"),
        Column("Vorsteuerabzug", "input_tax_deductible", "bool"),
    ]

    def order(self):
        return [Owner.name]

    def children(self, obj):
        props = REGISTRY["objekte"]
        return [
            ChildTable(
                "Objekte",
                props,
                list(obj.properties),
                props.add_action("+ Objekt", eigentuemer_id=obj.id, next=self.url("detail", obj)),
            )
        ]


class PropertyResource(Resource):
    slug = "objekte"
    model = Property
    singular = "Objekt"
    plural = "Objekte"
    fields = [
        Field("owner_id", "Eigentümer", choices=choices.owners, section="Stammdaten"),
        Field("name", "Bezeichnung", section="Stammdaten", help="z. B. Hauptstraße 12"),
        Field("street", "Straße", section="Anschrift"),
        Field("house_number", "Hausnummer", section="Anschrift"),
        Field("postal_code", "PLZ", section="Anschrift"),
        Field("city", "Ort", section="Anschrift"),
        Field("year_built", "Baujahr", section="Gebäude"),
    ]
    columns = [
        Column("Bezeichnung", "name", link=True),
        Column("Anschrift", lambda p: f"{p.street} {p.house_number}, {p.postal_code} {p.city}"),
        Column("Eigentümer", lambda p: p.owner.name),
        Column("Baujahr", "year_built", "num"),
    ]

    def order(self):
        return [Property.name]

    def children(self, obj):
        units = REGISTRY["wohneinheiten"]
        return [
            ChildTable(
                "Wohneinheiten",
                units,
                list(obj.units),
                units.add_action("+ Wohneinheit", objekt_id=obj.id, next=self.url("detail", obj)),
            )
        ]


class UnitResource(Resource):
    slug = "wohneinheiten"
    model = Unit
    singular = "Wohneinheit"
    plural = "Wohneinheiten"
    fields = [
        Field("property_id", "Objekt", choices=choices.properties, section="Stammdaten"),
        Field("name", "Bezeichnung", section="Stammdaten", help="z. B. EG links"),
        Field("unit_type", "Typ", section="Stammdaten"),
        Field("living_area_m2", "Wohnfläche (m²)", section="Flächen und Anteile"),
        Field(
            "co_ownership_share",
            "Miteigentumsanteile",
            section="Flächen und Anteile",
            help="Nur falls der MEA-Schlüssel genutzt wird",
        ),
        Field("available_from", "Verfügbar ab", section="Vermietung", help="Startpunkt für die Leerstandsberechnung"),
    ]
    columns = [
        Column("Bezeichnung", "name", link=True),
        Column("Objekt", lambda u: u.property.name),
        Column("Typ", "unit_type", "enum"),
        Column("Wohnfläche", lambda u: f"{fmt_decimal(u.living_area_m2)} m²", "num"),
        Column("Verfügbar ab", "available_from", "date"),
    ]

    def order(self):
        return [Unit.property_id, Unit.name]

    def children(self, obj):
        tenancies = REGISTRY["mietverhaeltnisse"]
        meters = REGISTRY["zaehler"]
        here = self.url("detail", obj)
        return [
            ChildTable(
                "Mietverhältnisse",
                tenancies,
                sorted(obj.tenancies, key=lambda t: t.move_in_date, reverse=True),
                tenancies.add_action("+ Mietverhältnis", wohneinheit_id=obj.id, next=here),
            ),
            ChildTable(
                "Zähler",
                meters,
                list(obj.meters),
                meters.add_action("+ Zähler", wohneinheit_id=obj.id, next=here),
            ),
        ]


class TenantResource(Resource):
    slug = "mieter"
    model = Tenant
    singular = "Mieter"
    plural = "Mieter"
    searchable = True
    fields = [
        Field("salutation", "Anrede", section="Person"),
        Field("first_name", "Vorname", section="Person"),
        Field("last_name", "Nachname", section="Person", help="Bei Gewerbe: Firmenname"),
        Field("phone", "Telefon", section="Kontakt"),
        Field("email", "E-Mail", kind="email", section="Kontakt"),
        Field("iban", "IBAN", section="Bankverbindung", help="Für die Auszahlung von Guthaben"),
        Field("bic", "BIC", section="Bankverbindung"),
        Field("forwarding_street", "Straße", section="Nachsendeadresse"),
        Field("forwarding_postal_code", "PLZ", section="Nachsendeadresse"),
        Field("forwarding_city", "Ort", section="Nachsendeadresse"),
        Field("forwarding_valid_from", "Gültig ab", section="Nachsendeadresse"),
        Field("notes", "Notizen", section="Notizen"),
    ]

    def title(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def order(self):
        return [Tenant.last_name, Tenant.first_name]

    def search_attrs(self):
        return [Tenant.first_name, Tenant.last_name, Tenant.email]

    @staticmethod
    def current_unit(tenant: Tenant) -> str:
        today = date.today()
        for t in tenant.tenancies:
            if t.move_in_date <= today and (t.move_out_date is None or t.move_out_date >= today):
                return t.unit.name
        return ""

    columns = [
        Column("Name", lambda t: f"{t.last_name}, {t.first_name}", link=True),
        Column("E-Mail", "email"),
        Column("Telefon", "phone"),
        Column("Aktuelle Wohneinheit", lambda t: TenantResource.current_unit(t)),
    ]

    def children(self, obj):
        tenancies = REGISTRY["mietverhaeltnisse"]
        return [
            ChildTable(
                "Mietverhältnisse",
                tenancies,
                sorted(obj.tenancies, key=lambda t: t.move_in_date, reverse=True),
                tenancies.add_action("+ Mietverhältnis", mieter_id=obj.id, next=self.url("detail", obj)),
            )
        ]


class TenancyResource(Resource):
    slug = "mietverhaeltnisse"
    model = TenancyAgreement
    singular = "Mietverhältnis"
    plural = "Mietverhältnisse"
    fields = [
        Field("unit_id", "Wohneinheit", choices=choices.units, section="Zuordnung"),
        Field("tenant_id", "Mieter", choices=choices.tenants, section="Zuordnung"),
        Field("move_in_date", "Einzugsdatum", section="Zeitraum"),
        Field("move_out_date", "Auszugsdatum", section="Zeitraum", help="Leer lassen für ein laufendes Mietverhältnis"),
        Field("occupants", "Personenanzahl", section="Belegung"),
    ]
    columns = [
        Column("Mieter", lambda t: f"{t.tenant.last_name}, {t.tenant.first_name}", link=True),
        Column("Wohneinheit", lambda t: f"{t.unit.name} ({t.unit.property.name})"),
        Column("Einzug", "move_in_date", "date"),
        Column("Auszug", lambda t: fmt_date(t.move_out_date) or "laufend"),
        Column("Personen", "occupants", "num"),
    ]

    def title(self, obj):
        return f"{obj.tenant.last_name}, {obj.tenant.first_name} ({fmt_date(obj.move_in_date)})"

    def order(self):
        return [TenancyAgreement.move_in_date.desc()]

    def validate(self, values, obj):
        errors = {}
        move_in, move_out = values.get("einzugsdatum"), values.get("auszugsdatum")
        if values.get("personenanzahl") is not None and values["personenanzahl"] < 1:
            errors["personenanzahl"] = "Mindestens eine Person erforderlich."
        if move_in and move_out and move_out < move_in:
            errors["auszugsdatum"] = "Das Auszugsdatum darf nicht vor dem Einzugsdatum liegen."
            return errors
        unit_id = values.get("wohneinheit_id")
        if move_in and unit_id:
            query = sa.select(TenancyAgreement).where(
                TenancyAgreement.unit_id == unit_id,
                TenancyAgreement.move_in_date <= (move_out or date.max),
                sa.or_(TenancyAgreement.move_out_date.is_(None), TenancyAgreement.move_out_date >= move_in),
            )
            if obj is not None:
                query = query.where(TenancyAgreement.id != obj.id)
            other = db.session.scalars(query).first()
            if other is not None:
                errors["einzugsdatum"] = (
                    f"Überschneidung mit dem Mietverhältnis {self.title(other)} "
                    f"({_period(other.move_in_date, other.move_out_date)}) derselben Wohneinheit."
                )
        return errors

    def warnings(self, obj):
        if obj.move_in_date < obj.unit.available_from:
            return [
                (
                    f"Hinweis: Das Einzugsdatum liegt vor dem Datum, ab dem die Wohneinheit verfügbar ist "
                    f"({fmt_date(obj.unit.available_from)})."
                )
            ]
        return []


owner_res = register_crud(bp, OwnerResource())
property_res = register_crud(bp, PropertyResource(), index=False)
unit_res = register_crud(bp, UnitResource())
tenant_res = register_crud(bp, TenantResource())
tenancy_res = register_crud(bp, TenancyResource())


@bp.route("/objekte/")
def objekte_index():
    """Tree: Eigentümer → Objekt → Wohneinheit → Mietverhältnis / Leerstand."""
    here = request.full_path.rstrip("?")
    today = date.today()
    active = active_property_id()
    owner_query = sa.select(Owner).order_by(Owner.name)
    if active:
        owner_query = owner_query.where(Owner.id == db.session.get(Property, active).owner_id)
    roots: list[Node] = []
    for owner in db.session.scalars(owner_query):
        prop_nodes = []
        for prop in sorted(owner.properties, key=lambda p: p.name):
            if active and prop.id != active:
                continue
            unit_nodes = [_unit_node(unit, here, today) for unit in sorted(prop.units, key=lambda u: u.name)]
            prop_nodes.append(
                property_res.node(
                    prop,
                    "property",
                    here,
                    adds=[unit_res.add_action("+ Wohneinheit", objekt_id=prop.id, next=here)],
                    meta=[("Anschrift", f"{prop.street} {prop.house_number}, {prop.postal_code} {prop.city}")],
                    children=unit_nodes,
                    empty="Noch keine Wohneinheiten",
                )
            )
        roots.append(
            owner_res.node(
                owner,
                "owner",
                here,
                adds=[property_res.add_action("+ Objekt", eigentuemer_id=owner.id, next=here)],
                meta=[("Rechtsform", owner.legal_form)],
                children=prop_nodes,
                empty="Noch keine Objekte",
            )
        )
    apply_open_state(roots, request.args)
    return render_template(
        "crud/tree.html",
        roots=roots,
        title="Objekte & Wohneinheiten",
        primary=property_res.add_action("+ Objekt anlegen", next=here),
        empty_text="Noch keine Eigentümer angelegt.",
        empty_action=owner_res.add_action("+ Eigentümer anlegen", next=here),
    )


def _unit_node(unit: Unit, here: str, today: date) -> Node:
    entries = []  # (start, Node)
    for tenancy in unit.tenancies:
        node = tenancy_res.node(
            tenancy,
            "tenant",
            here,
            title=f"{tenancy.tenant.last_name}, {tenancy.tenant.first_name}",
            meta=[
                ("Zeitraum", _period(tenancy.move_in_date, tenancy.move_out_date)),
                ("Personen", str(tenancy.occupants)),
            ],
        )
        entries.append((tenancy.move_in_date, node))
    periods = vacancy_periods(unit.available_from, [(t.move_in_date, t.move_out_date) for t in unit.tenancies], today)
    for start, end in periods:
        label = _period(start, end)
        entries.append(
            (
                start,
                Node(
                    key=f"leerstand-{unit.id}-{start.isoformat()}",
                    kind="vacancy",
                    title=f"Leerstand {label}",
                    badges=[("Leerstand", "warning")],
                ),
            )
        )
    entries.sort(key=lambda e: e[0], reverse=True)
    occupied = any(
        t.move_in_date <= today and (t.move_out_date is None or t.move_out_date >= today) for t in unit.tenancies
    )
    return unit_res.node(
        unit,
        "unit",
        here,
        adds=[tenancy_res.add_action("+ Mietverhältnis", wohneinheit_id=unit.id, next=here)],
        meta=[
            ("Typ", dict(unit_res.field_by_name["typ"].choices())[unit.unit_type]),
            ("Fläche", f"{fmt_decimal(unit.living_area_m2)} m²"),
        ],
        badges=[("Vermietet", "success")] if occupied else [("Leerstand", "warning")],
        children=[n for _, n in entries],
        empty="Noch keine Mietverhältnisse",
    )
