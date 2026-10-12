import logging

import sqlalchemy as sa
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import User
from app.ui.crud import safe_next

logger = logging.getLogger(__name__)
bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.values.get("next"))
    if current_user.is_authenticated:
        return redirect(next_url or url_for("main.dashboard"))
    error = None
    status = 200
    if request.method == "POST":
        identifier = (request.form.get("login") or "").strip()
        password = request.form.get("password") or ""
        user = db.session.scalar(sa.select(User).where(sa.or_(User.username == identifier, User.email == identifier)))
        if user is not None and user.active and user.check_password(password):
            login_user(user)
            user.last_login = sa.func.now()
            db.session.commit()
            logger.info("Login of user '%s'", user.username)
            return redirect(next_url or url_for("main.dashboard"))
        logger.warning("Failed login attempt for '%s'", identifier)
        error = "Anmeldedaten ungültig."
        status = 401
    return render_template("auth/login.html", error=error, next_url=next_url, title="Anmelden"), status


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logger.info("Logout of user '%s'", current_user.username)
    logout_user()
    flash("Sie wurden abgemeldet.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/passwort", methods=["GET", "POST"])
@login_required
def change_password():
    errors: dict[str, str] = {}
    if request.method == "POST":
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        repeat = request.form.get("repeat_password") or ""
        if not current_user.check_password(current):
            errors["current_password"] = "Das aktuelle Passwort ist falsch."
        if len(new) < 8:
            errors["new_password"] = "Mindestens 8 Zeichen erforderlich."
        elif new != repeat:
            errors["repeat_password"] = "Die Passwörter stimmen nicht überein."
        if not errors:
            current_user.set_password(new)
            db.session.commit()
            logger.info("Password changed for user '%s'", current_user.username)
            flash("Das Passwort wurde geändert.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth/password.html", errors=errors, title="Passwort ändern"), (422 if errors else 200)
