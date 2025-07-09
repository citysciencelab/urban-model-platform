

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from ump.config import DatabaseConnection

db = SQLAlchemy()
migrate = Migrate()

def create_migration_app():
    from ump.api.models import (
        ensemble, job_comments, job_status, job,
        process
    )
    
    app = Flask(__name__)

    db_settings = DatabaseConnection()

    db_settings.print_settings()  # Print settings for debugging
    
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql+psycopg2://{db_settings.UMP_DATABASE_USER}:{db_settings.UMP_DATABASE_PASSWORD.get_secret_value()}"
        f"@{db_settings.UMP_DATABASE_HOST}:{db_settings.UMP_DATABASE_PORT}/{db_settings.UMP_DATABASE_NAME}"
    )

    db.init_app(app)

    migrate.init_app(app, db)

    return app