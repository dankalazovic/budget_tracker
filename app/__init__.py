import os

from flask import Flask
from dotenv import load_dotenv

from app.extensions import db


def create_app(config=None):
    load_dotenv()
    application = Flask(__name__)
    application.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    application.config["LOG_LEVEL"] = os.getenv("LOG_LEVEL", "INFO")

    if config is not None:
        application.config.update(config)

    db.init_app(application)

    # Ucitavanje modela registruje tabele u zajednickom SQLAlchemy metadata.
    from app import models
    from app.api import register_blueprints
    from app.commands import register_commands
    from app.database import register_session_lifecycle
    from app.errors import register_error_handlers
    from app.logging import configure_logging

    configure_logging(application)
    register_error_handlers(application)
    register_session_lifecycle(application)
    register_blueprints(application)
    register_commands(application)
    return application


app = create_app()
