"""System: Benutzer."""

import sqlalchemy as sa
from flask import Blueprint
from flask_login import current_user

from app.extensions import db
from app.models import User
from app.ui.crud import register_crud
from app.ui.fields import Field
from app.ui.resource import Column, Resource

bp = Blueprint("system", __name__)


def active_user_count() -> int:
    return db.session.scalar(sa.select(sa.func.count()).select_from(User).where(User.active.is_(True)))


class UserResource(Resource):
    slug = "benutzer"
    model = User
    singular = "Benutzer"
    plural = "Benutzer"
    fields = [
        Field("username", "Benutzername", section="Zugang"),
        Field("email", "E-Mail", kind="email", section="Zugang"),
        Field(
            "passwort",
            "Passwort",
            kind="password",
            virtual=True,
            required=True,
            optional_on_edit=True,
            min_length=8,
            section="Zugang",
            help="Mindestens 8 Zeichen. Beim Bearbeiten leer lassen, um das Passwort beizubehalten.",
        ),
        Field("active", "Aktiv", section="Status"),
    ]
    columns = [
        Column("Benutzername", "username", link=True),
        Column("E-Mail", "email"),
        Column("Aktiv", "active", "bool"),
        Column("Letzter Login", "last_login", "datetime"),
    ]

    def title(self, obj):
        return obj.username

    def order(self):
        return [User.username]

    def can_delete(self, obj):
        return obj.id != current_user.id

    def delete_blocker(self, obj):
        if obj.active and active_user_count() <= 1:
            return "Der letzte aktive Benutzer kann nicht gelöscht werden."
        return None

    def validate(self, values, obj):
        if obj is not None and obj.active and not values.get("aktiv") and active_user_count() <= 1:
            return {"aktiv": "Der letzte aktive Benutzer kann nicht deaktiviert werden."}
        return {}

    def populate(self, obj, values, creating):
        super().populate(obj, values, creating)
        if values.get("passwort"):
            obj.set_password(values["passwort"])


register_crud(bp, UserResource())
