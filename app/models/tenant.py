from app.extensions import db
from app.models.mixins import TimestampMixin


class Tenant(TimestampMixin, db.Model):
    """Mieter: master data only, no application login."""

    __tablename__ = "mieter"

    id = db.Column("id", db.Integer, primary_key=True)
    salutation = db.Column("anrede", db.String(50))
    first_name = db.Column("vorname", db.String(150), nullable=False)
    last_name = db.Column("nachname", db.String(150), nullable=False)
    phone = db.Column("telefon", db.String(50))
    email = db.Column("email", db.String(255))
    iban = db.Column("iban", db.String(34))
    bic = db.Column("bic", db.String(11))
    forwarding_street = db.Column("nachsendeadresse_strasse", db.String(150))
    forwarding_postal_code = db.Column("nachsendeadresse_plz", db.String(10))
    forwarding_city = db.Column("nachsendeadresse_ort", db.String(100))
    forwarding_valid_from = db.Column("nachsendeadresse_gueltig_ab", db.Date)
    notes = db.Column("notizen", db.Text)

    tenancies = db.relationship("TenancyAgreement", back_populates="tenant")
