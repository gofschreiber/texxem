from datetime import date

import sqlalchemy as sa
from flask import Blueprint, redirect, render_template, request, session, url_for

from app.extensions import db
from app.models import Property, Statement, TenancyAgreement, Unit
from app.ui.crud import safe_next

bp = Blueprint("main", __name__)


def property_figures(prop: Property, today: date) -> dict:
    unit_ids = db.session.scalars(sa.select(Unit.id).where(Unit.property_id == prop.id)).all()
    active_unit_ids = set(
        db.session.scalars(
            sa.select(TenancyAgreement.unit_id).where(
                TenancyAgreement.unit_id.in_(unit_ids or [0]),
                TenancyAgreement.move_in_date <= today,
                sa.or_(TenancyAgreement.move_out_date.is_(None), TenancyAgreement.move_out_date >= today),
            )
        )
    )
    last_year = db.session.scalar(
        sa.select(Statement).where(Statement.property_id == prop.id, Statement.billing_year == today.year - 1)
    )
    return {
        "property": prop,
        "units": len(unit_ids),
        "tenancies": len(active_unit_ids),
        "vacant": len(unit_ids) - len(active_unit_ids),
        "last_year": today.year - 1,
        "last_statement": last_year,
    }


@bp.route("/")
def dashboard():
    today = date.today()
    properties = db.session.scalars(sa.select(Property).order_by(Property.name)).all()
    figures = [property_figures(p, today) for p in properties]
    drafts = db.session.scalars(
        sa.select(Statement).where(Statement.status == "ENTWURF").order_by(Statement.billing_year)
    ).all()
    return render_template("dashboard.html", figures=figures, drafts=drafts, title="Übersicht")


@bp.route("/objekt-waehlen", methods=["POST"])
def choose_property():
    chosen = request.form.get("property_id", type=int)
    if chosen is not None and db.session.get(Property, chosen) is not None:
        session["active_property_id"] = chosen
    else:
        session.pop("active_property_id", None)
    return redirect(safe_next(request.form.get("next")) or url_for("main.dashboard"))
