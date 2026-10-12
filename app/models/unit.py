from app.extensions import db
from app.models.mixins import TimestampMixin

UNIT_TYPES = ("WOHNUNG", "GEWERBE")


class Unit(TimestampMixin, db.Model):
    """Wohneinheit: residential or commercial unit within a property."""

    __tablename__ = "wohneinheit"
    __table_args__ = (db.UniqueConstraint("objekt_id", "bezeichnung"),)

    id = db.Column("id", db.Integer, primary_key=True)
    property_id = db.Column("objekt_id", db.Integer, db.ForeignKey("objekt.id"), nullable=False)
    name = db.Column("bezeichnung", db.String(255), nullable=False)
    unit_type = db.Column("typ", db.Enum(*UNIT_TYPES, name="wohneinheit_typ"), nullable=False)
    living_area_m2 = db.Column("wohnflaeche_m2", db.Numeric(8, 2), nullable=False)
    co_ownership_share = db.Column("miteigentumsanteile", db.Numeric(10, 4))
    available_from = db.Column("verfuegbar_ab", db.Date, nullable=False)

    property = db.relationship("Property", back_populates="units")
    tenancies = db.relationship("TenancyAgreement", back_populates="unit")
    meters = db.relationship("Meter", back_populates="unit")
