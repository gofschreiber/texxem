"""Kosten: Kostenpositionen, Belege, Verteilung (Konfiguration je Kostenart), Kostenarten."""

import logging
import uuid
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    request,
    send_from_directory,
)
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (
    AllocationKey,
    Cost,
    CostReceipt,
    CostType,
    CostYearShare,
    Property,
    PropertyCostTypeConfig,
    Statement,
)
from app.ui import choices
from app.ui.context import active_property_id
from app.ui.crud import REGISTRY, apply_open_state, register_crud
from app.ui.fields import Field
from app.ui.formatting import fmt_date, fmt_decimal, fmt_enum, fmt_money
from app.ui.resource import Action, ChildTable, Column, Node, Resource

logger = logging.getLogger(__name__)
bp = Blueprint("kosten", __name__)

LOCKED_STATUSES = ("FINALISIERT", "VERSENDET")


def cost_years(cost: Cost) -> set[int]:
    return {cost.invoice_date.year, *range(cost.service_period_from.year, cost.service_period_to.year + 1)}


def cost_is_locked(cost: Cost) -> bool:
    """Costs are frozen once a finalised/sent statement of an affected year exists (A7)."""
    return (
        db.session.scalar(
            sa.select(sa.func.count())
            .select_from(Statement)
            .where(
                Statement.property_id == cost.property_id,
                Statement.billing_year.in_(cost_years(cost)),
                Statement.status.in_(LOCKED_STATUSES),
            )
        )
        > 0
    )


class CostResource(Resource):
    slug = "kosten"
    model = Cost
    singular = "Kostenposition"
    plural = "Kostenpositionen"
    fields = [
        Field("property_id", "Objekt", choices=choices.properties, section="Zuordnung"),
        Field("cost_type_id", "Kostenart", choices=choices.cost_types, section="Zuordnung"),
        Field("total_amount", "Betrag (€)", section="Rechnung"),
        Field("invoice_date", "Rechnungsdatum", section="Rechnung"),
        Field("supplier", "Lieferant", section="Rechnung"),
        Field("service_period_from", "Leistungszeitraum von", section="Zeitraum und Abgrenzung"),
        Field("service_period_to", "Leistungszeitraum bis", section="Zeitraum und Abgrenzung"),
        Field(
            "accrual_method",
            "Abgrenzungsart",
            section="Zeitraum und Abgrenzung",
            help=(
                "Abflussprinzip: 100 % im Jahr des Rechnungsdatums. Periodengerecht: Aufteilung auf die "
                "betroffenen Kalenderjahre (tagesgenau oder über einen Stichtags-Zählerstand)."
            ),
        ),
        Field("description", "Beschreibung", section="Weitere Angaben"),
    ]
    columns = [
        Column("Kostenart", lambda c: c.cost_type.name, link=True),
        Column("Objekt", lambda c: c.property.name),
        Column("Betrag", "total_amount", "money"),
        Column("Rechnungsdatum", "invoice_date", "date"),
        Column("Leistungszeitraum", lambda c: f"{fmt_date(c.service_period_from)} – {fmt_date(c.service_period_to)}"),
        Column("Lieferant", "supplier"),
    ]

    def title(self, obj):
        return f"{obj.cost_type.name}, {fmt_money(obj.total_amount)} ({fmt_date(obj.invoice_date)})"

    def order(self):
        return [Cost.invoice_date.desc(), Cost.id.desc()]

    def can_edit(self, obj):
        return not cost_is_locked(obj)

    def can_delete(self, obj):
        return not cost_is_locked(obj)

    def validate(self, values, obj):
        errors = {}
        start, end = values.get("leistungszeitraum_von"), values.get("leistungszeitraum_bis")
        if start and end and end < start:
            errors["leistungszeitraum_bis"] = "Das Ende des Leistungszeitraums darf nicht vor dem Beginn liegen."
        amount = values.get("betrag_gesamt")
        if amount is not None and amount == 0:
            errors["betrag_gesamt"] = "Der Betrag darf nicht 0 sein."
        return errors

    def children(self, obj):
        receipts = REGISTRY["belege"]
        here = self.url("detail", obj)
        return [
            ChildTable(
                "Belege",
                receipts,
                list(obj.receipts),
                receipts.add_action("+ Beleg hochladen", kosten_id=obj.id, next=here),
            ),
            ChildTable("Jahresanteile", year_share_res, sorted(obj.year_shares, key=lambda s: s.billing_year)),
        ]


class YearShareResource(Resource):
    """Read-only view of the accrual result (computed by the calculation engine)."""

    slug = "kosten_jahresanteile"
    model = CostYearShare
    singular = "Jahresanteil"
    plural = "Jahresanteile"
    creatable = editable = deletable = has_detail = False
    columns = [
        Column("Abrechnungsjahr", "billing_year", "num"),
        Column("Anteil", "share_amount", "money"),
        Column("Berechnungsgrundlage", "calculation_basis"),
    ]


class ReceiptResource(Resource):
    slug = "belege"
    model = CostReceipt
    singular = "Beleg"
    plural = "Belege"
    editable = False
    has_detail = False
    create_label = "Beleg hochladen"
    fields = [
        Field("cost_id", "Kostenposition", kind="hidden"),
        Field("file", "Datei", kind="file", virtual=True, required=True),
    ]
    columns = [
        Column("Dateiname", "file_name", link=True),
        Column("Typ", "mime_type"),
        Column("Hochgeladen am", "uploaded_at", "date"),
    ]

    def title(self, obj):
        return obj.file_name

    def view_url(self, obj):
        return self.url("download", obj)

    def validate(self, values, obj):
        if db.session.get(Cost, values.get("kosten_id")) is None:
            return {"_form": "Die Kostenposition existiert nicht."}
        return {}

    def populate(self, obj, values, creating):
        upload = values["file"]
        original = Path(upload.filename.replace("\\", "/")).name
        reference = f"{values['kosten_id']}/{uuid.uuid4().hex[:8]}_{secure_filename(original) or 'beleg'}"
        target = Path(current_app.config["UPLOAD_DIRECTORY"]) / reference
        target.parent.mkdir(parents=True, exist_ok=True)
        upload.save(target)
        obj.cost_id = values["kosten_id"]
        obj.file_name = original[:255]
        obj.storage_reference = reference
        obj.mime_type = (upload.mimetype or "application/octet-stream")[:127]
        logger.info("Receipt stored at %s", reference)

    def prepare_delete(self, obj):
        path = Path(current_app.config["UPLOAD_DIRECTORY"]) / obj.storage_reference

        def cleanup():
            path.unlink(missing_ok=True)
            logger.info("Receipt file removed: %s", path)

        return cleanup


class ConfigResource(Resource):
    slug = "verteilung"
    model = PropertyCostTypeConfig
    singular = "Verteilungskonfiguration"
    plural = "Verteilungskonfigurationen"
    create_label = "Konfiguration anlegen"
    fields = [
        Field("property_id", "Objekt", choices=choices.properties, section="Zuordnung", editable=False),
        Field("cost_type_id", "Kostenart", choices=choices.cost_types, section="Zuordnung", editable=False),
        Field("allocation_key_id", "Verteilerschlüssel", choices=choices.allocation_keys, section="Verteilung"),
        Field("consumption_based", "Verbrauchsabhängig", section="Verbrauch", help="Zählerdaten werden einbezogen"),
        Field("meter_type_id", "Zählertyp", choices=choices.meter_types, section="Verbrauch"),
        Field(
            "base_cost_percent",
            "Grundkostenanteil (%)",
            section="Verbrauch",
            help="Nur bei Heizung/Warmwasser: Anteil, der nach Fläche verteilt wird; der Rest nach Verbrauch",
        ),
        Field("valid_from", "Gültig ab", section="Gültigkeit"),
        Field("valid_to", "Gültig bis", section="Gültigkeit"),
    ]
    unique_messages = {
        (
            "objekt_id",
            "kostenart_id",
            "gueltig_ab",
        ): "Für diese Kostenart existiert bereits eine Konfiguration mit diesem Gültigkeitsbeginn."
    }
    columns = [
        Column("Kostenart", lambda c: c.cost_type.name, link=True),
        Column("Objekt", lambda c: c.property.name),
        Column("Schlüssel", lambda c: c.allocation_key.name),
        Column("Verbrauchsabhängig", "consumption_based", "bool"),
        Column("Gültig ab", "valid_from", "date"),
        Column("Gültig bis", "valid_to", "date"),
    ]

    def title(self, obj):
        return f"{obj.cost_type.name} ab {fmt_date(obj.valid_from)}"

    def order(self):
        return [
            PropertyCostTypeConfig.property_id,
            PropertyCostTypeConfig.cost_type_id,
            PropertyCostTypeConfig.valid_from.desc(),
        ]

    def validate(self, values, obj):
        errors = {}
        cost_type = db.session.get(CostType, values.get("kostenart_id"))
        key = db.session.get(AllocationKey, values.get("verteilerschluessel_id"))
        consumption = bool(values.get("ist_verbrauchsabhaengig"))
        percent = values.get("grundkosten_anteil_prozent")
        if consumption and cost_type is not None and not cost_type.consumption_based_possible:
            errors["ist_verbrauchsabhaengig"] = "Diese Kostenart kann nicht verbrauchsabhängig verteilt werden."
        if consumption and values.get("zaehlertyp_id") is None:
            errors["zaehlertyp_id"] = "Bei verbrauchsabhängiger Verteilung ist ein Zählertyp erforderlich."
        if key is not None and key.code == "VERBRAUCH" and values.get("zaehlertyp_id") is None:
            errors["zaehlertyp_id"] = "Für den Schlüssel „nach gemessenem Verbrauch“ ist ein Zählertyp erforderlich."
        if percent is not None:
            if not consumption:
                errors["grundkosten_anteil_prozent"] = (
                    "Ein Grundkostenanteil ist nur bei verbrauchsabhängiger Verteilung möglich."
                )
            elif not 0 <= percent <= 100:
                errors["grundkosten_anteil_prozent"] = "Der Grundkostenanteil muss zwischen 0 und 100 liegen."
        start, end = values.get("gueltig_ab"), values.get("gueltig_bis")
        if start and end and end < start:
            errors["gueltig_bis"] = "Das Ende der Gültigkeit darf nicht vor dem Beginn liegen."
        elif start:
            query = sa.select(PropertyCostTypeConfig).where(
                PropertyCostTypeConfig.property_id == values.get("objekt_id"),
                PropertyCostTypeConfig.cost_type_id == values.get("kostenart_id"),
                PropertyCostTypeConfig.valid_from <= (end or date.max),
                sa.or_(PropertyCostTypeConfig.valid_to.is_(None), PropertyCostTypeConfig.valid_to >= start),
            )
            if obj is not None:
                query = query.where(PropertyCostTypeConfig.id != obj.id)
            other = db.session.scalars(query).first()
            if other is not None:
                errors["gueltig_ab"] = (
                    f"Der Zeitraum überschneidet sich mit der Konfiguration ab {fmt_date(other.valid_from)}."
                )
        return errors

    def delete_blocker(self, obj):
        last_year = obj.valid_to.year if obj.valid_to else 9999
        exists = db.session.scalar(
            sa.select(sa.func.count())
            .select_from(Statement)
            .where(
                Statement.property_id == obj.property_id,
                Statement.billing_year >= obj.valid_from.year,
                Statement.billing_year <= last_year,
            )
        )
        if exists:
            return "Die Konfiguration kann nicht gelöscht werden: Für den Zeitraum existiert bereits eine Abrechnung."
        return None


class CostTypeResource(Resource):
    slug = "kostenarten"
    model = CostType
    singular = "Kostenart"
    plural = "Kostenarten"
    creatable = editable = deletable = has_detail = False
    columns = [
        Column("Nr. BetrKV", "betrkv_number"),
        Column("Bezeichnung", "name"),
        Column("Verbrauchsabhängig möglich", "consumption_based_possible", "bool"),
    ]

    def order(self):
        return [CostType.id]


year_share_res = YearShareResource()
cost_res = register_crud(bp, CostResource(), index=False)
receipt_res = register_crud(bp, ReceiptResource(), index=False)
config_res = register_crud(bp, ConfigResource(), index=False)
register_crud(bp, CostTypeResource())


@bp.route("/belege/<int:id>/download")
def belege_download(id: int):
    receipt = db.session.get(CostReceipt, id)
    if receipt is None:
        abort(404)
    return send_from_directory(
        current_app.config["UPLOAD_DIRECTORY"],
        receipt.storage_reference,
        as_attachment=True,
        download_name=receipt.file_name,
        mimetype=receipt.mime_type,
    )


def _properties(active: int | None):
    query = sa.select(Property).order_by(Property.name)
    if active:
        query = query.where(Property.id == active)
    return db.session.scalars(query).all()


def _property_node(prop: Property, adds: list[Action], children: list[Node]) -> Node:
    return Node(
        key=f"objekte-{prop.id}",
        kind="property",
        title=prop.name,
        url=REGISTRY["objekte"].url("detail", prop),
        actions=[*adds, Action("view", "Anzeigen", REGISTRY["objekte"].url("detail", prop))],
        children=children,
        empty="Keine Einträge",
    )


@bp.route("/kosten/")
def kosten_index():
    """Tree: Objekt → Rechnungsjahr → Kostenart → Kostenposition → Belege / Jahresanteile."""
    here = request.full_path.rstrip("?")
    roots = []
    for prop in _properties(active_property_id()):
        costs = db.session.scalars(
            sa.select(Cost).where(Cost.property_id == prop.id).order_by(Cost.invoice_date.desc())
        ).all()
        years: dict[int, dict[int, list[Cost]]] = {}
        for cost in costs:
            years.setdefault(cost.invoice_date.year, {}).setdefault(cost.cost_type_id, []).append(cost)
        year_nodes = []
        for year in sorted(years, reverse=True):
            type_nodes = []
            for type_id, items in sorted(years[year].items()):
                cost_type = items[0].cost_type
                type_nodes.append(
                    Node(
                        key=f"kostenart-{prop.id}-{year}-{type_id}",
                        kind="cost_type",
                        title=cost_type.name,
                        meta=[("Summe", fmt_money(sum(c.total_amount for c in items)))],
                        actions=[
                            cost_res.add_action("+ Kostenposition", objekt_id=prop.id, kostenart_id=type_id, next=here)
                        ],
                        children=[_cost_node(c, here) for c in items],
                    )
                )
            year_nodes.append(
                Node(
                    key=f"jahr-{prop.id}-{year}",
                    kind="year",
                    title=f"Rechnungsjahr {year}",
                    meta=[("Summe", fmt_money(sum(c.total_amount for ts in years[year].values() for c in ts)))],
                    actions=[cost_res.add_action("+ Kostenposition", objekt_id=prop.id, next=here)],
                    children=type_nodes,
                )
            )
        roots.append(
            _property_node(prop, [cost_res.add_action("+ Kostenposition", objekt_id=prop.id, next=here)], year_nodes)
        )
    apply_open_state(roots, request.args)
    return render_template(
        "crud/tree.html",
        roots=roots,
        title="Kostenpositionen",
        primary=cost_res.add_action("+ Kostenposition anlegen", next=here),
        empty_text="Noch keine Objekte angelegt.",
        empty_action=REGISTRY["objekte"].add_action("+ Objekt anlegen", next=here),
    )


def _cost_node(cost: Cost, here: str) -> Node:
    children = [receipt_res.node(r, "receipt", here, meta=[("Typ", r.mime_type)]) for r in cost.receipts]
    for share in sorted(cost.year_shares, key=lambda s: s.billing_year):
        children.append(
            Node(
                key=f"kosten_jahresanteil-{share.id}",
                kind="share",
                title=f"Jahresanteil {share.billing_year}: {fmt_money(share.share_amount)}",
                meta=[("Grundlage", share.calculation_basis)],
            )
        )
    return cost_res.node(
        cost,
        "cost",
        here,
        adds=[receipt_res.add_action("+ Beleg", kosten_id=cost.id, next=here)],
        title=f"{fmt_money(cost.total_amount)} vom {fmt_date(cost.invoice_date)}",
        meta=[
            ("Leistungszeitraum", f"{fmt_date(cost.service_period_from)} – {fmt_date(cost.service_period_to)}"),
            ("Abgrenzung", fmt_enum(cost.accrual_method)),
        ],
        badges=[("Gesperrt", "neutral")] if cost_is_locked(cost) else [],
        children=children,
    )


@bp.route("/verteilung/")
def verteilung_index():
    """Tree: Objekt → Kostenart (alle 17) → Konfigurationsversion."""
    here = request.full_path.rstrip("?")
    cost_types = db.session.scalars(sa.select(CostType).order_by(CostType.id)).all()
    roots = []
    for prop in _properties(active_property_id()):
        configs = db.session.scalars(
            sa.select(PropertyCostTypeConfig).where(PropertyCostTypeConfig.property_id == prop.id)
        ).all()
        type_nodes = []
        for cost_type in cost_types:
            versions = sorted(
                (c for c in configs if c.cost_type_id == cost_type.id), key=lambda c: c.valid_from, reverse=True
            )
            version_nodes = [
                config_res.node(
                    c,
                    "config",
                    here,
                    title=f"ab {fmt_date(c.valid_from)}" + (f" bis {fmt_date(c.valid_to)}" if c.valid_to else ""),
                    meta=[
                        ("Schlüssel", c.allocation_key.name),
                        ("Verbrauch", "ja" if c.consumption_based else "nein"),
                    ]
                    + (
                        [("Grundkosten", f"{fmt_decimal(c.base_cost_percent)} %")]
                        if c.base_cost_percent is not None
                        else []
                    ),
                )
                for c in versions
            ]
            type_nodes.append(
                Node(
                    key=f"kostenart-{prop.id}-{cost_type.id}",
                    kind="cost_type",
                    title=f"{cost_type.betrkv_number}: {cost_type.name}",
                    badges=[] if versions else [("nicht konfiguriert", "warning")],
                    actions=[
                        config_res.add_action(
                            "+ Konfiguration", objekt_id=prop.id, kostenart_id=cost_type.id, next=here
                        )
                    ],
                    children=version_nodes,
                )
            )
        roots.append(_property_node(prop, [], type_nodes))
    apply_open_state(roots, request.args)
    return render_template(
        "crud/tree.html",
        roots=roots,
        title="Verteilung",
        primary=config_res.add_action("+ Konfiguration anlegen", next=here),
        empty_text="Noch keine Objekte angelegt.",
        empty_action=REGISTRY["objekte"].add_action("+ Objekt anlegen", next=here),
    )
