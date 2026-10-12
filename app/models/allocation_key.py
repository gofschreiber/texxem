from app.extensions import db


class AllocationKey(db.Model):
    """Verteilerschlüssel: fixed catalog (seeded by migration)."""

    __tablename__ = "verteilerschluessel"

    id = db.Column("id", db.Integer, primary_key=True)
    code = db.Column("code", db.String(50), nullable=False, unique=True)
    name = db.Column("bezeichnung", db.String(255), nullable=False)
