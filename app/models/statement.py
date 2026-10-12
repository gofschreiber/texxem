from app.extensions import db
from app.models.mixins import CreatedMixin

STATEMENT_STATUSES = ("ENTWURF", "FINALISIERT", "VERSENDET")


class Statement(CreatedMixin, db.Model):
    """Abrechnung: billing run for one property and calendar year."""

    __tablename__ = "abrechnung"
    __table_args__ = (db.UniqueConstraint("objekt_id", "abrechnungsjahr"),)

    id = db.Column("id", db.Integer, primary_key=True)
    property_id = db.Column("objekt_id", db.Integer, db.ForeignKey("objekt.id"), nullable=False)
    billing_year = db.Column("abrechnungsjahr", db.Integer, nullable=False)
    status = db.Column(
        "status",
        db.Enum(*STATEMENT_STATUSES, name="abrechnung_status"),
        nullable=False,
        default="ENTWURF",
        server_default="ENTWURF",
    )

    property = db.relationship("Property")
    items = db.relationship("StatementItem", back_populates="statement")
