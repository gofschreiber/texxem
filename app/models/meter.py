from app.extensions import db
from app.models.mixins import CreatedMixin


class Meter(CreatedMixin, db.Model):
    """Zähler: physical device bound to a unit or (e.g. common electricity) to the property."""

    __tablename__ = "zaehler"
    __table_args__ = (db.CheckConstraint("wohneinheit_id IS NOT NULL OR objekt_id IS NOT NULL", name="zuordnung"),)

    id = db.Column("id", db.Integer, primary_key=True)
    meter_type_id = db.Column("zaehlertyp_id", db.Integer, db.ForeignKey("zaehlertyp.id"), nullable=False)
    unit_id = db.Column("wohneinheit_id", db.Integer, db.ForeignKey("wohneinheit.id"))
    property_id = db.Column("objekt_id", db.Integer, db.ForeignKey("objekt.id"))
    external_device_id = db.Column("externe_geraete_id", db.String(100), nullable=False, unique=True)
    installed_on = db.Column("einbaudatum", db.Date, nullable=False)
    removed_on = db.Column("ausbaudatum", db.Date)

    meter_type = db.relationship("MeterType")
    unit = db.relationship("Unit", back_populates="meters")
    property = db.relationship("Property")
    readings = db.relationship("MeterReading", back_populates="meter")
