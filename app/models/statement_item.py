from app.extensions import db
from app.models.mixins import CreatedMixin


class StatementItem(CreatedMixin, db.Model):
    """Abrechnungsposition: one row per tenancy active (even partially) in the billing year."""

    __tablename__ = "abrechnungsposition"
    __table_args__ = (db.UniqueConstraint("abrechnung_id", "mietverhaeltnis_id"),)

    id = db.Column("id", db.Integer, primary_key=True)
    statement_id = db.Column("abrechnung_id", db.Integer, db.ForeignKey("abrechnung.id"), nullable=False)
    tenancy_id = db.Column(
        "mietverhaeltnis_id",
        db.Integer,
        db.ForeignKey("mietverhaeltnis.id"),
        nullable=False,
    )
    period_from = db.Column("zeitraum_von", db.Date, nullable=False)
    period_to = db.Column("zeitraum_bis", db.Date, nullable=False)
    usage_days = db.Column("nutzungstage", db.Integer, nullable=False)
    prepayment_received = db.Column(
        "vorauszahlung_erhalten",
        db.Numeric(10, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    total_cost_share = db.Column("kostenanteil_gesamt", db.Numeric(10, 2), nullable=False)
    balance = db.Column("saldo", db.Numeric(10, 2), nullable=False)
    delivery_street = db.Column("zustelladresse_strasse", db.String(150), nullable=False)
    delivery_postal_code = db.Column("zustelladresse_plz", db.String(10), nullable=False)
    delivery_city = db.Column("zustelladresse_ort", db.String(100), nullable=False)

    statement = db.relationship("Statement", back_populates="items")
    tenancy = db.relationship("TenancyAgreement")
    cost_type_lines = db.relationship("StatementItemCostType", back_populates="item")
