from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from app.database import db

migrate = Migrate()
csrf = CSRFProtect()

__all__ = ['db', 'migrate', 'csrf']
