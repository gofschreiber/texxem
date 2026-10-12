from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.mixins import CURRENT_TS


class User(UserMixin, db.Model):
    """Benutzer: operator login (tenants have no access)."""

    __tablename__ = "benutzer"

    id = db.Column("id", db.Integer, primary_key=True)
    username = db.Column("benutzername", db.String(100), nullable=False, unique=True)
    email = db.Column("email", db.String(255), nullable=False, unique=True)
    password_hash = db.Column("passwort_hash", db.String(255), nullable=False)
    active = db.Column("aktiv", db.Boolean, nullable=False, default=True, server_default=db.true())
    created_at = db.Column("erstellt_am", db.TIMESTAMP, nullable=False, server_default=CURRENT_TS)
    last_login = db.Column("letzter_login", db.TIMESTAMP, nullable=True)

    @property
    def is_active(self) -> bool:
        return bool(self.active)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
