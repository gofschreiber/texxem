from app.extensions import db
from app.models.mixins import TimestampMixin


class Owner(TimestampMixin, db.Model):
    __tablename__ = "eigentuemer"

    id = db.Column("id", db.Integer, primary_key=True)
    name = db.Column("name", db.String(255), nullable=False)
    legal_form = db.Column("rechtsform", db.String(100), nullable=False)
    street = db.Column("strasse", db.String(150), nullable=False)
    postal_code = db.Column("plz", db.String(10), nullable=False)
    city = db.Column("ort", db.String(100), nullable=False)
    input_tax_deductible = db.Column(
        "vorsteuerabzugsberechtigt",
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
    )
    iban = db.Column("iban", db.String(34))
    bic = db.Column("bic", db.String(11))

    properties = db.relationship("Property", back_populates="owner")
