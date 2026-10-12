"""Abrechnung: statement runs per property and calendar year."""

import logging

import sqlalchemy as sa
from flask import Blueprint, abort, flash, redirect, render_template, request

from app.extensions import db
from app.models import Property, Statement, StatementItem
from app.ui import choices
from app.ui.context import active_property_id
from app.ui.crud import REGISTRY, apply_open_state, get_or_404, register_crud, safe_next
from app.ui.fields import Field
from app.ui.formatting import fmt_date, fmt_enum, fmt_money
from app.ui.resource import Action, ChildTable, Column, Node, Resource

logger = logging.getLogger(__name__)
bp = Blueprint("abrechnung", __name__)

STATUS_BADGES = {"ENTWURF": "warning", "FINALISIERT": "info", "VERSENDET": "success"}
# current status -> {target status: action label}
TRANSITIONS = {
    "ENTWURF": {"FINALISIERT": "Finalisieren"},
    "FINALISIERT": {"VERSENDET": "Als versendet markieren", "ENTWURF": "Zurück auf Entwurf"},
    "VERSENDET": {},
}


def status_badge(statement: Statement) -> tuple[str, str]:
    return fmt_enum(statement.status), STATUS_BADGES[statement.status]


class StatementResource(Resource):
    slug = "abrechnungen"
    model = Statement
    singular = "Abrechnung"
    plural = "Abrechnungen"
    editable = False
    create_label = "Abrechnung anlegen"
    fields = [
        Field("property_id", "Objekt", choices=choices.properties),
        Field("billing_year", "Abrechnungsjahr", help="Kalenderjahr"),
    ]
    unique_messages = {
        ("objekt_id", "abrechnungsjahr"): "Für dieses Objekt und Jahr existiert bereits eine Abrechnung."
    }
    columns = [
        Column("Abrechnung", lambda s: f"{s.property.name} {s.billing_year}", link=True),
        Column("Objekt", lambda s: s.property.name),
        Column("Jahr", lambda s: str(s.billing_year), "num"),
        Column("Status", status_badge, "badge"),
        Column("Erstellt am", "created_at", "date"),
    ]

    def title(self, obj):
        return f"{obj.property.name} {obj.billing_year}"

    def order(self):
        return [Statement.billing_year.desc(), Statement.property_id]

    def can_delete(self, obj):
        return obj.status == "ENTWURF"

    def validate(self, values, obj):
        year = values.get("abrechnungsjahr")
        if year is not None and not 2000 <= year <= 2100:
            return {"abrechnungsjahr": "Bitte ein Jahr zwischen 2000 und 2100 eingeben."}
        return {}

    def status_actions(self, obj, next_url: str) -> list[Action]:
        return [
            Action("status", label, self.url("status", obj, ziel=target.lower(), next=next_url))
            for target, label in TRANSITIONS[obj.status].items()
        ]

    def detail_actions(self, obj, next_url):
        return self.status_actions(obj, next_url)

    def children(self, obj):
        return [
            ChildTable(
                "Abrechnungspositionen",
                item_res,
                sorted(obj.items, key=lambda i: i.period_from),
                note="Die Positionen werden vom Abrechnungslauf der Berechnungs-Engine erzeugt.",
            )
        ]


class StatementItemResource(Resource):
    """Read-only view of generated statement items."""

    slug = "abrechnungspositionen"
    model = StatementItem
    singular = "Abrechnungsposition"
    plural = "Abrechnungspositionen"
    creatable = editable = deletable = has_detail = False
    columns = [
        Column("Mieter", lambda i: f"{i.tenancy.tenant.last_name}, {i.tenancy.tenant.first_name}"),
        Column("Zeitraum", lambda i: f"{fmt_date(i.period_from)} – {fmt_date(i.period_to)}"),
        Column("Nutzungstage", "usage_days", "num"),
        Column("Vorauszahlung", "prepayment_received", "money"),
        Column("Kostenanteil", "total_cost_share", "money"),
        Column("Saldo", "balance", "money"),
    ]


item_res = StatementItemResource()
statement_res = register_crud(bp, StatementResource(), index=False)


@bp.route("/abrechnungen/<int:id>/status/<ziel>", methods=["GET", "POST"])
def abrechnungen_status(id: int, ziel: str):
    statement = get_or_404(statement_res, id)
    target = ziel.upper()
    label = TRANSITIONS[statement.status].get(target)
    if label is None:
        abort(403)
    next_url = safe_next(request.values.get("next")) or statement_res.url("detail", statement)
    if request.method == "GET":
        return render_template(
            "crud/confirm_status.html",
            res=statement_res,
            obj=statement,
            target=target,
            label=label,
            next_url=next_url,
            title=f"{statement_res.singular}: {label}",
        )
    old = statement.status
    statement.status = target
    db.session.commit()
    logger.info("Statement %s: status %s -> %s", statement.id, old, target)
    flash(f"Abrechnung „{statement_res.title(statement)}“ hat jetzt den Status „{fmt_enum(target)}“.", "success")
    return redirect(next_url)


@bp.route("/abrechnungen/")
def abrechnungen_index():
    """Tree: Objekt → Abrechnung → Abrechnungsposition → Kostenart-Detailzeile."""
    here = request.full_path.rstrip("?")
    active = active_property_id()
    query = sa.select(Property).order_by(Property.name)
    if active:
        query = query.where(Property.id == active)
    roots = []
    for prop in db.session.scalars(query):
        statement_nodes = []
        for statement in sorted(_statements(prop), key=lambda s: s.billing_year, reverse=True):
            item_nodes = []
            for item in sorted(statement.items, key=lambda i: i.period_from):
                lines = [
                    Node(
                        key=f"abrechnungsposition_kostenart-{line.id}",
                        kind="line",
                        title=line.cost_type.name,
                        meta=[("Schlüssel", line.allocation_key.name), ("Betrag", fmt_money(line.amount))],
                    )
                    for line in item.cost_type_lines
                ]
                item_nodes.append(
                    Node(
                        key=f"abrechnungsposition-{item.id}",
                        kind="tenant",
                        title=f"{item.tenancy.tenant.last_name}, {item.tenancy.tenant.first_name}",
                        meta=[
                            ("Zeitraum", f"{fmt_date(item.period_from)} – {fmt_date(item.period_to)}"),
                            ("Kostenanteil", fmt_money(item.total_cost_share)),
                            ("Saldo", fmt_money(item.balance)),
                        ],
                        badges=[("Nachzahlung", "warning")]
                        if item.balance > 0
                        else ([("Guthaben", "success")] if item.balance < 0 else []),
                        children=lines,
                    )
                )
            text, modifier = status_badge(statement)
            statement_nodes.append(
                statement_res.node(
                    statement,
                    "statement",
                    here,
                    adds=statement_res.status_actions(statement, here),
                    title=f"Abrechnung {statement.billing_year}",
                    badges=[(text, modifier)],
                    children=item_nodes,
                    empty="Noch keine Abrechnungspositionen",
                )
            )
        roots.append(
            Node(
                key=f"objekte-{prop.id}",
                kind="property",
                title=prop.name,
                url=REGISTRY["objekte"].url("detail", prop),
                actions=[
                    statement_res.add_action("+ Abrechnung", objekt_id=prop.id, next=here),
                    Action("view", "Anzeigen", REGISTRY["objekte"].url("detail", prop)),
                ],
                children=statement_nodes,
                empty="Noch keine Abrechnungen",
            )
        )
    apply_open_state(roots, request.args)
    return render_template(
        "crud/tree.html",
        roots=roots,
        title="Abrechnungen",
        primary=statement_res.add_action("+ Abrechnung anlegen", next=here),
        empty_text="Noch keine Objekte angelegt.",
        empty_action=REGISTRY["objekte"].add_action("+ Objekt anlegen", next=here),
    )


def _statements(prop: Property) -> list[Statement]:
    return db.session.scalars(sa.select(Statement).where(Statement.property_id == prop.id)).all()
