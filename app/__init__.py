import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask

from app.database import db

load_dotenv()


def create_app():
    app = Flask(__name__, template_folder='views')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cambia-esta-clave')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    db.init_app(app)

    from app import models  # carga todos los modelos

    from app.controllers.home_controller import home_bp
    from app.controllers.auth_controller import auth_bp
    from app.controllers.reserva_controller import reserva_bp
    from app.controllers.venta_controller import venta_bp
    from app.controllers.caja_controller import caja_bp
    from app.controllers.mantenimiento_controller import mantenimiento_bp

    for bp in (home_bp, auth_bp, reserva_bp, venta_bp, caja_bp, mantenimiento_bp):
        app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        from app.seed import cargar_datos_iniciales
        cargar_datos_iniciales()

    return app