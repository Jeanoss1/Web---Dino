"""Decoradores de acceso reutilizables.

El rol se lee SIEMPRE de la base de datos (no de la cookie), de modo que
desactivar una cuenta o cambiarle el rol surte efecto de inmediato.
"""
from functools import wraps
from urllib.parse import urlparse

from flask import abort, jsonify, redirect, request, session, url_for

from app.database import db
from app.models.usuario import Usuario


_CLAVE = 'dinopark.usuario_actual'     # caché por petición (vive en el environ)


def usuario_actual():
    """Usuario de la sesión (o None). Se consulta una sola vez por petición."""
    if _CLAVE in request.environ:
        return request.environ[_CLAVE]
    usuario = None
    id_usuario = session.get('id_usuario')
    if id_usuario:
        usuario = db.session.get(Usuario, id_usuario)
        if usuario is None or not usuario.estado:
            session.clear()
            usuario = None
    request.environ[_CLAVE] = usuario
    return usuario


def es_peticion_api():
    return request.path.startswith('/api/')


def _no_autenticado():
    if es_peticion_api():
        return jsonify(error='Debes iniciar sesión'), 401
    return redirect(url_for('auth.iniciar_sesion', next=request.full_path.rstrip('?')))


def login_requerido(f):
    """La ruta solo se puede usar con una sesión iniciada."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if usuario_actual() is None:
            return _no_autenticado()
        return f(*args, **kwargs)
    return wrapper


def rol_requerido(*roles):
    """La ruta solo se puede usar con uno de los roles indicados."""
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            usuario = usuario_actual()
            if usuario is None:
                return _no_autenticado()
            if usuario.rol_nombre not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorador


def cajero_actual():
    """Perfil de cajero activo del usuario en sesión (403 si no lo tiene)."""
    usuario = usuario_actual()
    cajero = usuario.cajero if usuario else None
    if usuario is None or usuario.rol_nombre != 'cajero' or cajero is None or cajero.estado != 'activo':
        abort(403)
    return cajero


def alcance_sede():
    """Sede a la que se limita la consulta: la del cajero, o None (todas) para el administrador."""
    usuario = usuario_actual()
    if usuario.rol_nombre == 'administrador':
        return None
    return cajero_actual().id_sucursal


def destino_seguro(destino):
    """Solo permite volver a rutas internas del propio sitio (evita redirecciones abiertas)."""
    if not destino:
        return None
    partes = urlparse(destino)
    if partes.scheme or partes.netloc or not destino.startswith('/') or destino.startswith('//'):
        return None
    return destino


def pagina_inicial(usuario):
    rol = usuario.rol_nombre
    if rol == 'administrador':
        return url_for('reportes.dashboard')
    if rol == 'cajero':
        return url_for('caja.panel')
    return url_for('reserva.disponibilidad')
