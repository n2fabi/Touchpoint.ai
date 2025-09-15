from flask import Flask
from db import init_db
from config import Config
from background_tasks import init_background, sidebar_cache, refresh_emails, refresh_reminders
from flask_session import Session
    

# Blueprint imports are intentionally minimal; the files exist under blueprints/
# and register_blueprints() will import them lazily to avoid circular imports.

def create_app(config_object=None):
    """App factory. Keep this file tiny — configuration and registration only."""
    print("Creating Flask app...", flush=True)  # Debugging output
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY

    # Session-Konfiguration (serverseitig)
    app.config["SESSION_TYPE"] = "filesystem"   # Alternativ: "redis", "mongodb"
    app.config["SESSION_PERMANENT"] = False     # Session endet, wenn Browser geschlossen wird
    app.config["SESSION_USE_SIGNER"] = True     # Signiert Session-ID für mehr Sicherheit
    app.config["SESSION_FILE_DIR"] = "./flask_session"  # Lokaler Ordner für Filesystem-Sessions
    Session(app)  # Initialisiert die Session-Erweiterung

    # Load config from object or environment
    if config_object:
        app.config.from_object(config_object)
    else:
        # default config path (you may replace with python-dotenv or env vars)
        app.config.from_envvar('APP_CONFIG_FILE', silent=True)

    # Initialize DB (PyMongo wrapper lives in app/db.py)
    print("Initializing database...", flush=True)  # Debugging output
    init_db(app)

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

    # Initialize background tasks (scheduler)
    init_background(app)
    #initial run
    refresh_emails(app)
    refresh_reminders(app)

    @app.context_processor
    def inject_sidebar_data():
        print("inject_sidebar_data called!", sidebar_cache, flush=True)
        return dict(sidebar_unread=sidebar_cache["unread_count"],
                    sidebar_reminder=sidebar_cache["reminders_count"],
                    sidebar_last_update=sidebar_cache["last_update"])

    return app

