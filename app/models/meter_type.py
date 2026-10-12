from app.extensions import db


class MeterType(db.Model):
    """Zählertyp: extensible catalog."""

    __tablename__ = "zaehlertyp"

    id = db.Column("id", db.Integer, primary_key=True)
    name = db.Column("bezeichnung", db.String(100), nullable=False)
    unit = db.Column("einheit", db.String(20), nullable=False)
    active = db.Column("aktiv", db.Boolean, nullable=False, default=True, server_default=db.true())
