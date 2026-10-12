from sqlalchemy import text

from app.extensions import db

CURRENT_TS = text("CURRENT_TIMESTAMP")
CURRENT_TS_ON_UPDATE = text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")


class CreatedMixin:
    created_at = db.Column("erstellt_am", db.TIMESTAMP, nullable=False, server_default=CURRENT_TS)


class TimestampMixin(CreatedMixin):
    updated_at = db.Column(
        "geaendert_am",
        db.TIMESTAMP,
        nullable=False,
        server_default=CURRENT_TS_ON_UPDATE,
    )
