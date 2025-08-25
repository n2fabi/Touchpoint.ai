from flask import Flask
from db import init_db
from config import Config
from blueprints.reminders import init_reminder
    

# Blueprint imports are intentionally minimal; the files exist under blueprints/
# and register_blueprints() will import them lazily to avoid circular imports.

def create_app(config_object=None):
    """App factory. Keep this file tiny — configuration and registration only."""
    print("Creating Flask app...", flush=True)  # Debugging output
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY

    # Load config from object or environment
    if config_object:
        app.config.from_object(config_object)
    else:
        # default config path (you may replace with python-dotenv or env vars)
        app.config.from_envvar('APP_CONFIG_FILE', silent=True)

    # Initialize DB (PyMongo wrapper lives in app/db.py)
    print("Initializing database...", flush=True)  # Debugging output
    init_db(app)
    init_reminder(app)

    # Register blueprints
    from blueprints.customers import customers_bp
    from blueprints.products import products_bp
    from blueprints.emails import emails_bp
    from blueprints.index import index_bp
    from blueprints.reminders import reminders_bp
    from blueprints.settings import settings_bp
    from blueprints.chats import chats_bp

    app.register_blueprint(customers_bp, url_prefix='/customers')
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(emails_bp, url_prefix='/emails')
    app.register_blueprint(index_bp, url_prefix='/')
    app.register_blueprint(reminders_bp, url_prefix='/reminders')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(chats_bp, url_prefix='/chats')

    from filters import datetimeformat, nl2p
    app.add_template_filter(datetimeformat, "datetimeformat")
    app.add_template_filter(nl2p, "nl2p")

    return app

