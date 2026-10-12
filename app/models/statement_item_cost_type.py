from app.extensions import db


class StatementItemCostType(db.Model):
    """Abrechnungsposition-Kostenart: detail line per cost type within a statement item."""

    __tablename__ = "abrechnungsposition_kostenart"

    id = db.Column("id", db.Integer, primary_key=True)
    item_id = db.Column(
        "abrechnungsposition_id",
        db.Integer,
        db.ForeignKey("abrechnungsposition.id"),
        nullable=False,
    )
    cost_type_id = db.Column("kostenart_id", db.Integer, db.ForeignKey("kostenart.id"), nullable=False)
    allocation_key_id = db.Column(
        "verteilerschluessel_id",
        db.Integer,
        db.ForeignKey("verteilerschluessel.id"),
        nullable=False,
    )
    amount = db.Column("betrag", db.Numeric(10, 2), nullable=False)
    base_cost_amount = db.Column("grundkosten_betrag", db.Numeric(10, 2))
    consumption_cost_amount = db.Column("verbrauchskosten_betrag", db.Numeric(10, 2))
    consumption_value = db.Column("verbrauchswert", db.Numeric(14, 4))
    share_percent = db.Column("anteil_prozent", db.Numeric(7, 4))

    item = db.relationship("StatementItem", back_populates="cost_type_lines")
    cost_type = db.relationship("CostType")
    allocation_key = db.relationship("AllocationKey")
