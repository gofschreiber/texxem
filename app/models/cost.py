from app.extensions import db
from app.models.mixins import TimestampMixin

ACCRUAL_METHODS = (
    "ABFLUSSPRINZIP",
    "PERIODENGERECHT_TAGESGENAU",
    "PERIODENGERECHT_ZAEHLERSTAND",
)


class Cost(TimestampMixin, db.Model):
    """Kosten: a single recorded cost item (invoice/expense)."""

    __tablename__ = "kosten"
    __table_args__ = (db.CheckConstraint("leistungszeitraum_bis >= leistungszeitraum_von", name="leistungszeitraum"),)

    id = db.Column("id", db.Integer, primary_key=True)
    property_id = db.Column("objekt_id", db.Integer, db.ForeignKey("objekt.id"), nullable=False)
    cost_type_id = db.Column("kostenart_id", db.Integer, db.ForeignKey("kostenart.id"), nullable=False)
    total_amount = db.Column("betrag_gesamt", db.Numeric(10, 2), nullable=False)
    invoice_date = db.Column("rechnungsdatum", db.Date, nullable=False)
    service_period_from = db.Column("leistungszeitraum_von", db.Date, nullable=False)
    service_period_to = db.Column("leistungszeitraum_bis", db.Date, nullable=False)
    accrual_method = db.Column(
        "abgrenzungsart",
        db.Enum(*ACCRUAL_METHODS, name="kosten_abgrenzungsart"),
        nullable=False,
    )
    supplier = db.Column("lieferant", db.String(255))
    description = db.Column("beschreibung", db.Text)

    property = db.relationship("Property")
    cost_type = db.relationship("CostType")
    year_shares = db.relationship("CostYearShare", back_populates="cost")
    receipts = db.relationship("CostReceipt", back_populates="cost")
