from functools import wraps

from flask import jsonify, redirect, request, session, url_for


def _no_autenticado():
    if request.path.startswith('/api/'):
        return jsonify(error='Debes iniciar sesión'), 401
    return redirect(url_for('auth.iniciar_sesion'))


def login_requerido(f):
    """La ruta solo se puede usar con una sesión iniciada."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'id_usuario' not in session:
            return _no_autenticado()
        # Registrado con Google y aún sin DNI ni teléfono
        if session.get('perfil_incompleto') and request.endpoint != 'auth.completar_perfil':
            if request.path.startswith('/api/'):
                return jsonify(error='Completa tu DNI y teléfono para continuar'), 403
            return redirect(url_for('auth.completar_perfil'))
        return f(*args, **kwargs)
    return wrapper


def rol_requerido(*roles):
    """La ruta solo se puede usar con uno de los roles indicados."""
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'id_usuario' not in session:
                return _no_autenticado()
            if session.get('rol') not in roles:
                return jsonify(error='No tienes permiso para esta acción'), 403
            return f(*args, **kwargs)
        return wrapper
    return decorador