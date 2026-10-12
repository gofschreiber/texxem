from app.extensions import db

READING_SOURCES = ("SCHNITTSTELLE", "MANUELL")


class MeterReading(db.Model):
    """Zählerstand: absolute daily meter reading."""

    __tablename__ = "zaehlerstand"
    __table_args__ = (db.UniqueConstraint("zaehler_id", "ablesedatum"),)

    id = db.Column("id", db.Integer, primary_key=True)
    meter_id = db.Column("zaehler_id", db.Integer, db.ForeignKey("zaehler.id"), nullable=False)
    reading_date = db.Column("ablesedatum", db.Date, nullable=False)
    value = db.Column("stand", db.Numeric(14, 4), nullable=False)
    source = db.Column("quelle", db.Enum(*READING_SOURCES, name="zaehlerstand_quelle"), nullable=False)
    imported_at = db.Column("importiert_am", db.TIMESTAMP, nullable=True)

    meter = db.relationship("Meter", back_populates="readings")
