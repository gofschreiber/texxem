from app.extensions import db


class PropertyCostTypeConfig(db.Model):
    """Objekt-Kostenart-Konfiguration: allocation key per cost type and property, historisable."""

    __tablename__ = "objekt_kostenart_konfiguration"
    __table_args__ = (db.UniqueConstraint("objekt_id", "kostenart_id", "gueltig_ab"),)

    id = db.Column("id", db.Integer, primary_key=True)
    property_id = db.Column("objekt_id", db.Integer, db.ForeignKey("objekt.id"), nullable=False)
    cost_type_id = db.Column("kostenart_id", db.Integer, db.ForeignKey("kostenart.id"), nullable=False)
    allocation_key_id = db.Column(
        "verteilerschluessel_id",
        db.Integer,
        db.ForeignKey("verteilerschluessel.id"),
        nullable=False,
    )
    consumption_based = db.Column("ist_verbrauchsabhaengig", db.Boolean, nullable=False)
    base_cost_percent = db.Column("grundkosten_anteil_prozent", db.Numeric(5, 2))
    meter_type_id = db.Column("zaehlertyp_id", db.Integer, db.ForeignKey("zaehlertyp.id"))
    valid_from = db.Column("gueltig_ab", db.Date, nullable=False)
    valid_to = db.Column("gueltig_bis", db.Date)

    property = db.relationship("Property")
    cost_type = db.relationship("CostType")
    allocation_key = db.relationship("AllocationKey")
    meter_type = db.relationship("MeterType")
