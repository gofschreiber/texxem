from app.extensions import db
from app.models.mixins import TimestampMixin


class Property(TimestampMixin, db.Model):
    __tablename__ = "objekt"

    id = db.Column("id", db.Integer, primary_key=True)
    owner_id = db.Column("eigentuemer_id", db.Integer, db.ForeignKey("eigentuemer.id"), nullable=False)
    name = db.Column("bezeichnung", db.String(255), nullable=False)
    street = db.Column("strasse", db.String(150), nullable=False)
    house_number = db.Column("hausnummer", db.String(20), nullable=False)
    postal_code = db.Column("plz", db.String(10), nullable=False)
    city = db.Column("ort", db.String(100), nullable=False)
    year_built = db.Column("baujahr", db.Integer)

    owner = db.relationship("Owner", back_populates="properties")
    units = db.relationship("Unit", back_populates="property")
