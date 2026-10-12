from app.extensions import db
from app.models.mixins import TimestampMixin


class TenancyAgreement(TimestampMixin, db.Model):
    """Mietverhältnis. Non-overlap per unit is enforced in the application layer."""

    __tablename__ = "mietverhaeltnis"
    __table_args__ = (
        db.CheckConstraint(
            "auszugsdatum IS NULL OR auszugsdatum >= einzugsdatum",
            name="auszug_nach_einzug",
        ),
    )

    id = db.Column("id", db.Integer, primary_key=True)
    unit_id = db.Column("wohneinheit_id", db.Integer, db.ForeignKey("wohneinheit.id"), nullable=False)
    tenant_id = db.Column("mieter_id", db.Integer, db.ForeignKey("mieter.id"), nullable=False)
    move_in_date = db.Column("einzugsdatum", db.Date, nullable=False)
    move_out_date = db.Column("auszugsdatum", db.Date)
    occupants = db.Column("personenanzahl", db.Integer, nullable=False, default=1, server_default="1")

    unit = db.relationship("Unit", back_populates="tenancies")
    tenant = db.relationship("Tenant", back_populates="tenancies")
