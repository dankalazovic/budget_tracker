import os

from flask import Flask
from dotenv import load_dotenv

from app.extensions import db


def create_app(config=None):
    load_dotenv()
    application = Flask(__name__)
    application.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

    if config is not None:
        application.config.update(config)

    db.init_app(application)

    # Ucitavanje modela registruje tabele u zajednickom SQLAlchemy metadata.
    from app import models
    from app.api import register_blueprints
    from app.commands import register_commands

    register_blueprints(application)
    register_commands(application)
    return application


app = create_app()
