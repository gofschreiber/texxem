import logging

import click
import sqlalchemy as sa
from flask import Flask
from sqlalchemy.exc import OperationalError

from app.config import TEST_DB_SUFFIX, Config, load_config
from app.extensions import csrf, db, login_manager, migrate
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def _verify_test_database(app: Flask) -> None:
    """Abort unless the connected database really is a test database."""
    with app.app_context():
        try:
            name = db.session.scalar(sa.text("SELECT DATABASE()"))
        except OperationalError as exc:
            raise RuntimeError(
                f"Test database '{app.config['DATABASE_NAME']}' is not reachable. Create it and "
                "grant access to the configured user, then run the migrations."
            ) from exc
        finally:
            db.session.remove()
    if not name or not name.endswith(TEST_DB_SUFFIX):
        raise RuntimeError(f"Refusing to start in test mode on database '{name}'")


def create_app(config: Config | None = None, test_mode: bool = False) -> Flask:
    """Application factory.

    In test mode the app uses the ``<database.name>_test`` database (same structure,
    built by the same migrations), a separate uploads directory and log files with a
    ``_test`` suffix.
    """
    config = config or load_config()
    if test_mode:
        config = config.for_test_mode()
    setup_logging(config.logging, suffix=TEST_DB_SUFFIX if test_mode else "")

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.secret_key,
        SQLALCHEMY_DATABASE_URI=config.database.url(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        UPLOAD_DIRECTORY=config.uploads.directory,
        TEST_MODE=test_mode,
        TESTING=test_mode,
        DATABASE_NAME=config.database.name,
    )
    config.uploads.directory.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Bitte melden Sie sich an."
    login_manager.login_message_category = "warning"
    csrf.init_app(app)

    from app import models  # noqa: F401  (registers all tables on db.metadata)
    from app.blueprints import register_blueprints
    from app.models.user import User
    from app.ui.context import register_ui

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        return db.session.get(User, int(user_id))

    register_ui(app)
    register_blueprints(app)
    _register_cli(app)

    if test_mode:
        _verify_test_database(app)

    logger.info("Application created, database '%s', test mode: %s", config.database.name, test_mode)
    return app


def _register_cli(app: Flask) -> None:
    @app.cli.command("create-user")
    @click.argument("username")
    @click.argument("email")
    @click.password_option()
    def create_user(username: str, email: str, password: str) -> None:
        """Create an operator account (benutzer)."""
        from app.models.user import User

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Benutzer '{username}' wurde angelegt.")
