import os
from flask_pymongo import PyMongo

mongo = PyMongo()

def init_db(app):
    """Initialize PyMongo and attach the client/DB to app context."""
    # Lese die MongoDB URI aus der Umgebung (.env oder Docker-Umgebung)
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/crm_db")
    print("MongoDB initialized with URI:", mongo_uri, flush=True)
    
    mongo.init_app(app, uri=mongo_uri)
    app.db = mongo.db
