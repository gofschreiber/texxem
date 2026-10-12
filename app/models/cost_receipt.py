from app.extensions import db
from app.models.mixins import CURRENT_TS


class CostReceipt(db.Model):
    """Kosten-Beleg: file attachment of a cost item."""

    __tablename__ = "kosten_beleg"

    id = db.Column("id", db.Integer, primary_key=True)
    cost_id = db.Column("kosten_id", db.Integer, db.ForeignKey("kosten.id"), nullable=False)
    file_name = db.Column("dateiname", db.String(255), nullable=False)
    storage_reference = db.Column("speicherreferenz", db.String(500), nullable=False)
    mime_type = db.Column("mime_type", db.String(127), nullable=False)
    uploaded_at = db.Column("hochgeladen_am", db.TIMESTAMP, nullable=False, server_default=CURRENT_TS)

    cost = db.relationship("Cost", back_populates="receipts")
