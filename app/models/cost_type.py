from app.extensions import db


class CostType(db.Model):
    """Kostenart: fixed catalog according to § 2 BetrKV (seeded by migration)."""

    __tablename__ = "kostenart"

    id = db.Column("id", db.Integer, primary_key=True)
    betrkv_number = db.Column("nummer_betrkv", db.String(20), nullable=False, unique=True)
    name = db.Column("bezeichnung", db.String(255), nullable=False)
    consumption_based_possible = db.Column("verbrauchsabhaengig_moeglich", db.Boolean, nullable=False)
