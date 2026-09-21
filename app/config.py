import os
import secrets

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bool(nombre, defecto='0'):
    return os.getenv(nombre, defecto).strip().lower() in ('1', 'true', 'si', 'sí')


class Config:
    """Configuración base. Todo lo sensible viene de variables de entorno (.env)."""
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY')

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = _bool('SESSION_COOKIE_SECURE')

    # Pagos con Yape
    YAPE_NUMERO = os.getenv('YAPE_NUMERO', '')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024          # capturas de hasta 5 MB
    UPLOAD_FOLDER = os.getenv(
        'UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads', 'comprobantes')
    )

    # Reglas del negocio
    HORA_APERTURA = os.getenv('HORA_APERTURA', '10:00')
    HORA_CIERRE = os.getenv('HORA_CIERRE', '22:00')
    DIAS_ANTICIPACION = int(os.getenv('DIAS_ANTICIPACION', '14'))
    MINUTOS_LIMITE_PAGO = int(os.getenv('MINUTOS_LIMITE_PAGO', '15'))
    TOLERANCIA_MINUTOS = int(os.getenv('TOLERANCIA_MINUTOS', '2'))
    MAX_BLOQUES_VENTA = 10
    LIMITE_INTENTOS_LOGIN = 5           # intentos fallidos permitidos
    VENTANA_INTENTOS_LOGIN = 600        # en segundos

    WTF_CSRF_ENABLED = True
    TESTING = False
    DEBUG = False


class DesarrolloConfig(Config):
    DEBUG = True

    @classmethod
    def init(cls):
        if not cls.SECRET_KEY:
            # Solo para desarrollo: las sesiones se reinician al reiniciar el servidor.
            cls.SECRET_KEY = secrets.token_hex(32)
            print('[aviso] Falta SECRET_KEY en .env: se usa una clave temporal.')


class ProduccionConfig(Config):
    @classmethod
    def init(cls):
        if not cls.SECRET_KEY:
            raise RuntimeError('Define SECRET_KEY en las variables de entorno.')
        if not cls.SQLALCHEMY_DATABASE_URI:
            raise RuntimeError('Define DATABASE_URL en las variables de entorno.')


class PruebasConfig(Config):
    TESTING = True
    SECRET_KEY = 'clave-solo-para-pruebas'
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False
    YAPE_NUMERO = '900000000'
    LIMITE_INTENTOS_LOGIN = 5

    @classmethod
    def init(cls):
        pass


def obtener_config():
    entorno = os.getenv('APP_ENV', 'development').lower()
    return ProduccionConfig if entorno.startswith('prod') else DesarrolloConfig
