import os
from urllib.parse import urlparse

from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   url_for)
from flask_wtf.csrf import CSRFError

from app.config import obtener_config
from app.database import db
from app.extensions import csrf, migrate
from app.services.errores import ErrorNegocio


def create_app(config_class=None):
    config_class = config_class or obtener_config()
    config_class.init()

    app = Flask(__name__, template_folder='views')
    app.config.from_object(config_class)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    from app import models  # noqa: F401  (registra todos los modelos)
    migrate.init_app(app, db)
    csrf.init_app(app)

    _registrar_blueprints(app)
    _registrar_contexto(app)
    _registrar_errores(app)
    _registrar_comandos(app)
    return app


def _registrar_blueprints(app):
    from app.controllers.admin_controller import admin_bp
    from app.controllers.auth_controller import auth_bp
    from app.controllers.caja_controller import caja_bp
    from app.controllers.home_controller import home_bp
    from app.controllers.mantenimiento_controller import mantenimiento_bp
    from app.controllers.reportes_controller import reportes_bp
    from app.controllers.reserva_controller import reserva_bp
    from app.controllers.venta_controller import venta_bp

    for bp in (home_bp, auth_bp, reserva_bp, venta_bp, caja_bp,
               reportes_bp, admin_bp, mantenimiento_bp):
        app.register_blueprint(bp)


def _registrar_contexto(app):
    from app.controllers.decoradores import usuario_actual
    from app.models.Tarifa import Tarifa

    @app.context_processor
    def variables_globales():
        n = app.config['YAPE_NUMERO'] or ''
        usuario = usuario_actual()
        tarifa = Tarifa.query.filter_by(activa=True).order_by(Tarifa.id_tarifa.desc()).first()
        return {
            'yape_numero': n,
            'yape_numero_formato': f'{n[:3]} {n[3:6]} {n[6:]}'.strip(),
            'usuario': usuario,
            'rol': usuario.rol_nombre if usuario else None,
            'sede_cajero': (usuario.cajero.sucursal.nombre
                            if usuario and usuario.cajero else None),
            'tarifa': tarifa,
        }

    @app.after_request
    def cabeceras_seguras(respuesta):
        respuesta.headers.setdefault('X-Content-Type-Options', 'nosniff')
        respuesta.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        respuesta.headers.setdefault('Referrer-Policy', 'same-origin')
        return respuesta


def _volver():
    """Página anterior si es del mismo sitio; si no, el inicio."""
    anterior = request.referrer
    if anterior:
        partes = urlparse(anterior)
        if partes.netloc == request.host:
            return anterior
    return url_for('home.index')


def _registrar_errores(app):
    from app.controllers.decoradores import es_peticion_api

    def responder(codigo, mensaje):
        if es_peticion_api() or request.is_json:
            return jsonify(error=mensaje), codigo
        return render_template('error.html', codigo=codigo, mensaje=mensaje), codigo

    @app.errorhandler(ErrorNegocio)
    def error_de_negocio(e):
        db.session.rollback()
        if es_peticion_api() or request.is_json:
            return jsonify(error=e.mensaje), e.codigo
        if request.method == 'GET':
            return render_template('error.html', codigo=e.codigo, mensaje=e.mensaje), e.codigo
        flash(e.mensaje, 'error')
        return redirect(_volver())

    @app.errorhandler(CSRFError)
    def error_csrf(_):
        return responder(400, 'La página caducó. Recárgala e inténtalo de nuevo.')

    @app.errorhandler(403)
    def prohibido(_):
        return responder(403, 'No tienes permiso para esta acción.')

    @app.errorhandler(404)
    def no_encontrado(_):
        return responder(404, 'No encontramos lo que buscabas.')

    @app.errorhandler(413)
    def archivo_muy_grande(_):
        return responder(413, 'La imagen supera los 5 MB.')

    @app.errorhandler(500)
    def error_interno(_):
        db.session.rollback()
        return responder(500, 'Ocurrió un error inesperado. Inténtalo de nuevo.')


def _registrar_comandos(app):
    import click

    @app.cli.command('finalizar-vencidos')
    def finalizar_vencidos():
        """Finaliza los alquileres cuyo tiempo ya venció (útil para un cron)."""
        from app.services import uso
        print(f'Alquileres finalizados: {uso.finalizar_vencidos()}')

    @app.cli.command('seed')
    @click.option('--demo', is_flag=True,
                  help='Agrega además ventas de las últimas semanas para probar reportes y cuadre.')
    def seed(demo):
        """Carga los datos de prueba (roles, sedes, tarifa, usuarios, flota, turnos)."""
        from app.seed import cargar_datos_iniciales
        cargar_datos_iniciales(demo=demo)
