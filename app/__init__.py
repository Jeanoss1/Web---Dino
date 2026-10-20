import os
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify

from app.database import db
from app.oauth import registrar_proveedores

load_dotenv()


def create_app(config=None):
    """`config` sobrescribe valores (lo usan las pruebas de tests/ para su BD)."""
    app = Flask(__name__, template_folder='views')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'cambia-esta-clave')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    # --- Rendimiento ---
    # Conexiones a PostgreSQL que se reutilizan entre peticiones. Debe haber
    # al menos tantas como hilos tenga el servidor (servidor.py usa 32), y la
    # suma de todos los procesos no debe pasar el max_connections de Postgres
    # (100 por defecto).
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': int(os.getenv('DB_POOL_SIZE', 20)),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', 20)),
        'pool_timeout': 15,       # segundos esperando una conexión libre
        'pool_recycle': 1800,     # renueva conexiones viejas
        'pool_pre_ping': True,    # descarta conexiones cortadas por Postgres
    }
    # El navegador guarda en caché logos e imágenes de static/ por 1 día
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(days=1)

    # --- Inicio de sesión con Google (vacío = botón desactivado) ---
    for clave in ('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET'):
        app.config[clave] = os.getenv(clave, '')

    # --- Pagos con Yape ---
    app.config['YAPE_NUMERO'] = '972751444'
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024        # capturas de hasta 5 MB
    # Las capturas se guardan FUERA de static/ (en <proyecto>/uploads/comprobantes)
    app.config['UPLOAD_FOLDER'] = os.path.join(
        os.path.dirname(app.root_path), 'uploads', 'comprobantes'
    )
    app.config['SEMBRAR_DATOS'] = True
    if config:
        app.config.update(config)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    @app.context_processor
    def datos_de_pago():
        # Disponibles en todas las plantillas: {{ yape_numero }} y {{ yape_numero_formato }}
        n = app.config['YAPE_NUMERO']
        return {'yape_numero': n, 'yape_numero_formato': f'{n[:3]} {n[3:6]} {n[6:]}'}

    @app.context_processor
    def datos_de_rol():
        # {{ logo_rol(rol) }}: logo de cada rol (archivos de static/img)
        logos = {'administrador': 'img/Administrador.png', 'cajero': 'img/Caja.png'}
        nombres = {'administrador': 'Administrador', 'cajero': 'Caja', 'cliente': 'Usuario'}
        return {
            'logo_rol': lambda rol: logos.get(rol, 'img/Usuario.png'),
            'nombre_rol': lambda rol: nombres.get(rol, 'Usuario'),
        }

    @app.errorhandler(413)
    def archivo_muy_grande(_):
        return jsonify(error='La imagen supera los 5 MB'), 413

    db.init_app(app)
    registrar_proveedores(app)

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

    if app.config['SEMBRAR_DATOS']:
        with app.app_context():
            db.create_all()   # crea la tabla nueva comprobantes_reserva
            from app.esquema import actualizar_esquema
            actualizar_esquema()   # columnas e índices nuevos en tablas existentes
            from app.seed import cargar_datos_iniciales
            cargar_datos_iniciales()

    return app