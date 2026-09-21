import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify

from app.database import db

load_dotenv()


def create_app():
    app = Flask(__name__, template_folder='views')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cambia-esta-clave')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    # --- Pagos con Yape ---
    app.config['YAPE_NUMERO'] = '972751444'
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024        # capturas de hasta 5 MB
    # Las capturas se guardan FUERA de static/ (en <proyecto>/uploads/comprobantes)
    app.config['UPLOAD_FOLDER'] = os.path.join(
        os.path.dirname(app.root_path), 'uploads', 'comprobantes'
    )
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    @app.context_processor
    def datos_de_pago():
        # Disponibles en todas las plantillas: {{ yape_numero }} y {{ yape_numero_formato }}
        n = app.config['YAPE_NUMERO']
        return {'yape_numero': n, 'yape_numero_formato': f'{n[:3]} {n[3:6]} {n[6:]}'}

    @app.errorhandler(413)
    def archivo_muy_grande(_):
        return jsonify(error='La imagen supera los 5 MB'), 413

    db.init_app(app)

    from app import models  # carga todos los modelos

    from app.controllers.home_controller import home_bp
    from app.controllers.auth_controller import auth_bp
    from app.controllers.reserva_controller import reserva_bp
    from app.controllers.venta_controller import venta_bp
    from app.controllers.caja_controller import caja_bp
    from app.controllers.mantenimiento_controller import mantenimiento_bp
    from app.controllers.comprobante_controller import comprobante_bp

    for bp in (home_bp, auth_bp, reserva_bp, venta_bp, caja_bp,
               mantenimiento_bp, comprobante_bp):
        app.register_blueprint(bp)

    with app.app_context():
        db.create_all()   # crea la tabla nueva comprobantes_reserva
        from app.seed import cargar_datos_iniciales
        cargar_datos_iniciales()

    return app