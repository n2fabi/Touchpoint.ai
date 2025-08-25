from flask import g
from flask_pymongo import PyMongo
from config import Config

mongo = PyMongo()


def init_db(app):
    """Initialize PyMongo and attach the client/DB to app context."""
    print("MongoDB initialized with URI:", Config.MONGO_URI, flush=True)
    mongo.init_app(app, uri=Config.MONGO_URI)
    app.db = mongo.db