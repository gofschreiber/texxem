from app.extensions import db


class CostYearShare(db.Model):
    """Kosten-Jahresanteil: result of accrual, share of a cost item per billing year."""

    __tablename__ = "kosten_jahresanteil"

    id = db.Column("id", db.Integer, primary_key=True)
    cost_id = db.Column("kosten_id", db.Integer, db.ForeignKey("kosten.id"), nullable=False)
    billing_year = db.Column("abrechnungsjahr", db.Integer, nullable=False)
    share_amount = db.Column("betrag_anteil", db.Numeric(10, 2), nullable=False)
    calculation_basis = db.Column("berechnungsgrundlage", db.Text, nullable=False)
    reference_reading_id = db.Column("referenz_zaehlerstand_id", db.Integer, db.ForeignKey("zaehlerstand.id"))

    cost = db.relationship("Cost", back_populates="year_shares")
    reference_reading = db.relationship("MeterReading")
