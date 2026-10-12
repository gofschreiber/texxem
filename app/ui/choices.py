"""Choice lists for select fields."""

import sqlalchemy as sa

from app.extensions import db
from app.models import (
    AllocationKey,
    CostType,
    Meter,
    MeterType,
    Owner,
    Property,
    Tenant,
    Unit,
)


def owners() -> list[tuple]:
    return [(o.id, o.name) for o in db.session.scalars(sa.select(Owner).order_by(Owner.name))]


def properties() -> list[tuple]:
    return [(p.id, p.name) for p in db.session.scalars(sa.select(Property).order_by(Property.name))]


def units() -> list[tuple]:
    rows = db.session.execute(sa.select(Unit, Property.name).join(Property).order_by(Property.name, Unit.name)).all()
    return [(u.id, f"{u.name} ({pname})") for u, pname in rows]


def tenants() -> list[tuple]:
    rows = db.session.scalars(sa.select(Tenant).order_by(Tenant.last_name, Tenant.first_name))
    return [(t.id, f"{t.last_name}, {t.first_name}") for t in rows]


def meter_types(active_only: bool = False) -> list[tuple]:
    query = sa.select(MeterType).order_by(MeterType.name)
    if active_only:
        query = query.where(MeterType.active.is_(True))
    return [(m.id, f"{m.name} ({m.unit})") for m in db.session.scalars(query)]


def cost_types() -> list[tuple]:
    return [
        (c.id, f"{c.betrkv_number}: {c.name}") for c in db.session.scalars(sa.select(CostType).order_by(CostType.id))
    ]


def allocation_keys() -> list[tuple]:
    return [(k.id, k.name) for k in db.session.scalars(sa.select(AllocationKey).order_by(AllocationKey.id))]


def meters() -> list[tuple]:
    rows = db.session.scalars(sa.select(Meter).order_by(Meter.external_device_id))
    return [(m.id, f"{m.external_device_id} ({m.meter_type.name})") for m in rows]
