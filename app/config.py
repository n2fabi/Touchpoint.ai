import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    MONGO_URI = 'mongodb://localhost:27017/crm_db'

    # Scheduler settings
    SCHEDULER_API_ENABLED = True
