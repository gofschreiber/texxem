"""Messwesen: Zählertypen, Zähler, Zählerstände."""

from datetime import date

import sqlalchemy as sa
from flask import Blueprint, render_template, request

from app.extensions import db
from app.models import Meter, MeterReading, MeterType, Property
from app.ui import choices
from app.ui.context import active_property_id
from app.ui.crud import REGISTRY, apply_open_state, register_crud
from app.ui.fields import Field
from app.ui.formatting import fmt_date, fmt_decimal
from app.ui.resource import Action, ChildTable, Column, Node, Resource

bp = Blueprint("zaehler", __name__)


class MeterTypeResource(Resource):
    slug = "zaehlertypen"
    model = MeterType
    singular = "Zählertyp"
    plural = "Zählertypen"
    fields = [
        Field("name", "Bezeichnung", help="z. B. Heizung, Warmwasser, Kaltwasser, Allgemeinstrom"),
        Field("unit", "Einheit", help="z. B. kWh, m³"),
        Field("active", "Aktiv"),
    ]
    columns = [
        Column("Bezeichnung", "name", link=True),
        Column("Einheit", "unit"),
        Column("Aktiv", "active", "bool"),
    ]

    def order(self):
        return [MeterType.name]


class MeterResource(Resource):
    slug = "zaehler"
    model = Meter
    singular = "Zähler"
    plural = "Zähler"
    fields = [
        Field("meter_type_id", "Zählertyp", choices=choices.meter_types, section="Gerät"),
        Field(
            "external_device_id", "Externe Geräte-ID", section="Gerät", help="ID/Seriennummer aus der Messapplikation"
        ),
        Field(
            "unit_id",
            "Wohneinheit",
            choices=choices.units,
            section="Zuordnung",
            help="Wohneinheit oder Objekt (mindestens eines)",
        ),
        Field(
            "property_id",
            "Objekt",
            choices=choices.properties,
            section="Zuordnung",
            help="Für objektweite Zähler, z. B. Allgemeinstrom",
        ),
        Field("installed_on", "Einbaudatum", section="Zeitraum"),
        Field("removed_on", "Ausbaudatum", section="Zeitraum", help="Bei Gerätewechsel"),
    ]

    def assignment(meter: Meter) -> str:
        if meter.unit is not None:
            return f"{meter.unit.name} ({meter.unit.property.name})"
        return f"{meter.property.name} (objektweit)" if meter.property else ""

    columns = [
        Column("Geräte-ID", "external_device_id", link=True),
        Column("Zählertyp", lambda m: m.meter_type.name),
        Column("Zuordnung", assignment),
        Column("Einbau", "installed_on", "date"),
        Column("Ausbau", "removed_on", "date"),
    ]

    def title(self, obj):
        return obj.external_device_id

    def order(self):
        return [Meter.external_device_id]

    def validate(self, values, obj):
        errors = {}
        if values.get("wohneinheit_id") is None and values.get("objekt_id") is None:
            errors["wohneinheit_id"] = "Bitte eine Wohneinheit oder ein Objekt zuordnen."
        installed, removed = values.get("einbaudatum"), values.get("ausbaudatum")
        if installed and removed and removed < installed:
            errors["ausbaudatum"] = "Das Ausbaudatum darf nicht vor dem Einbaudatum liegen."
        return errors

    def children(self, obj):
        readings = REGISTRY["zaehlerstaende"]
        latest = db.session.scalars(
            sa.select(MeterReading)
            .where(MeterReading.meter_id == obj.id)
            .order_by(MeterReading.reading_date.desc())
            .limit(10)
        ).all()
        return [
            ChildTable(
                "Letzte Zählerstände",
                readings,
                latest,
                readings.add_action("+ Zählerstand", zaehler_id=obj.id, next=self.url("detail", obj)),
            )
        ]


class ReadingResource(Resource):
    slug = "zaehlerstaende"
    model = MeterReading
    singular = "Zählerstand"
    plural = "Zählerstände"
    create_label = "Zählerstand erfassen"
    fields = [
        Field("meter_id", "Zähler", choices=choices.meters),
        Field("reading_date", "Ablesedatum"),
        Field("value", "Zählerstand", help="Absoluter Stand des Zählers"),
    ]
    unique_messages = {("zaehler_id", "ablesedatum"): "Für dieses Datum existiert bereits ein Zählerstand."}

    def source_badge(reading):
        return ("Schnittstelle", "info") if reading.source == "SCHNITTSTELLE" else ("Manuell", "neutral")

    columns = [
        Column("Zähler", lambda r: r.meter.external_device_id, link=True),
        Column("Ablesedatum", "reading_date", "date"),
        Column("Stand", lambda r: fmt_decimal(r.value, 4), "num"),
        Column("Quelle", source_badge, "badge"),
    ]
    filters = [
        ("zaehler_id", "Zähler", "select", choices.meters),
        ("von", "Von", "date", None),
        ("bis", "Bis", "date", None),
    ]

    def title(self, obj):
        return f"{obj.meter.external_device_id} {fmt_date(obj.reading_date)}"

    def can_edit(self, obj):
        return obj.source == "MANUELL"

    def can_delete(self, obj):
        return obj.source == "MANUELL"

    def create_defaults(self, obj):
        obj.source = "MANUELL"

    def new_params(self, args):
        return {"zaehler_id": args.get("zaehler_id")}

    def list_query(self, args):
        query = sa.select(MeterReading).order_by(MeterReading.reading_date.desc(), MeterReading.id.desc())
        meter_id = args.get("zaehler_id", type=int)
        if meter_id:
            query = query.where(MeterReading.meter_id == meter_id)
        for key, op in (("von", "ge"), ("bis", "le")):
            try:
                day = date.fromisoformat(args.get(key, ""))
            except ValueError:
                continue
            query = query.where(getattr(MeterReading.reading_date, f"__{op}__")(day))
        return query


type_res = register_crud(bp, MeterTypeResource())
meter_res = register_crud(bp, MeterResource(), index=False)
reading_res = register_crud(bp, ReadingResource())


@bp.route("/zaehler/")
def zaehler_index():
    """Tree: Objekt → Wohneinheit / Objektweit → Zähler → Zählerstände."""
    here = request.full_path.rstrip("?")
    active = active_property_id()
    query = sa.select(Property).order_by(Property.name)
    if active:
        query = query.where(Property.id == active)
    roots = []
    for prop in db.session.scalars(query):
        children = []
        for unit in sorted(prop.units, key=lambda u: u.name):
            children.append(
                Node(
                    key=f"wohneinheiten-{unit.id}",
                    kind="unit",
                    title=unit.name,
                    url=REGISTRY["wohneinheiten"].url("detail", unit),
                    actions=[
                        meter_res.add_action("+ Zähler", wohneinheit_id=unit.id, next=here),
                        Action("view", "Anzeigen", REGISTRY["wohneinheiten"].url("detail", unit)),
                    ],
                    children=[_meter_node(m, here) for m in unit.meters],
                    empty="Noch keine Zähler",
                )
            )
        property_meters = db.session.scalars(
            sa.select(Meter)
            .where(Meter.property_id == prop.id, Meter.unit_id.is_(None))
            .order_by(Meter.external_device_id)
        ).all()
        children.append(
            Node(
                key=f"objektweit-{prop.id}",
                kind="property",
                title="Objektweit",
                actions=[meter_res.add_action("+ Zähler", objekt_id=prop.id, next=here)],
                children=[_meter_node(m, here) for m in property_meters],
                empty="Noch keine objektweiten Zähler",
            )
        )
        roots.append(
            Node(
                key=f"objekte-{prop.id}",
                kind="property",
                title=prop.name,
                url=REGISTRY["objekte"].url("detail", prop),
                actions=[Action("view", "Anzeigen", REGISTRY["objekte"].url("detail", prop))],
                children=children,
            )
        )
    apply_open_state(roots, request.args)
    return render_template(
        "crud/tree.html",
        roots=roots,
        title="Zähler & Zählerstände",
        primary=meter_res.add_action("+ Zähler anlegen", next=here),
        empty_text="Noch keine Objekte angelegt.",
        empty_action=REGISTRY["objekte"].add_action("+ Objekt anlegen", next=here),
    )


def _meter_node(meter: Meter, here: str) -> Node:
    count, latest = db.session.execute(
        sa.select(sa.func.count(MeterReading.id), sa.func.max(MeterReading.reading_date)).where(
            MeterReading.meter_id == meter.id
        )
    ).one()
    reading_leaf = Node(
        key=f"zaehlerstaende-zaehler-{meter.id}",
        kind="readings",
        title=f"Zählerstände ({count})",
        url=reading_res.url("index", zaehler_id=meter.id),
        meta=[("Letzter Stand vom", fmt_date(latest))] if latest else [],
        actions=[
            reading_res.add_action("+ Zählerstand", zaehler_id=meter.id, next=here),
            Action("view", "Anzeigen", reading_res.url("index", zaehler_id=meter.id)),
        ],
    )
    return meter_res.node(
        meter,
        "meter",
        here,
        meta=[("Typ", meter.meter_type.name), ("Einbau", fmt_date(meter.installed_on))],
        badges=[("Ausgebaut", "neutral")] if meter.removed_on else [],
        children=[reading_leaf],
    )
