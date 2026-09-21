from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash

from app.controllers.decoradores import (destino_seguro, login_requerido,
                                         pagina_inicial, usuario_actual)
from app.models.Cliente import Cliente
from app.models.usuario import Usuario
from app.services import seguridad, usuarios
from app.services.errores import ErrorNegocio

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'GET':
        return render_template('Registro.html')
    try:
        usuarios.registrar_cliente(request.form)
    except ErrorNegocio as e:
        flash(e.mensaje, 'error')
        return render_template('Registro.html'), 400
    flash('¡Cuenta creada! Ya puedes iniciar sesión.', 'exito')
    return redirect(url_for('auth.iniciar_sesion'))


def _buscar_usuario(identificador):
    """Se puede entrar con el correo o con el DNI del cliente."""
    if '@' in identificador:
        return Usuario.query.filter_by(correo=identificador.lower()).first()
    cliente = Cliente.query.filter_by(dni=identificador).first()
    return cliente.usuario if cliente else None


@auth_bp.route('/iniciar-sesion', methods=['GET', 'POST'])
def iniciar_sesion():
    if request.method == 'GET':
        actual = usuario_actual()
        if actual:
            return redirect(pagina_inicial(actual))
        return render_template('iniciar_sesion.html')

    identificador = request.form.get('identificador', '').strip()[:120]
    contrasena = request.form.get('contrasena', '')
    clave_limite = f'{identificador.lower()}|{request.remote_addr}'

    if seguridad.bloqueado(clave_limite):
        flash('Demasiados intentos fallidos. Espera unos minutos e inténtalo de nuevo.', 'error')
        return render_template('iniciar_sesion.html'), 429

    usuario = _buscar_usuario(identificador)
    if usuario is None or not usuario.estado or not check_password_hash(usuario.contrasena, contrasena):
        seguridad.registrar_fallo(clave_limite)
        flash('Correo/DNI o contraseña incorrectos.', 'error')
        return render_template('iniciar_sesion.html'), 401

    seguridad.limpiar(clave_limite)
    session.clear()                      # nueva sesión: evita fijación de sesión
    session['id_usuario'] = usuario.id_usuario
    session['nombre'] = usuario.nombre
    session['rol'] = usuario.rol_nombre  # solo para mostrar el menú; la seguridad lee la BD
    session.permanent = bool(request.form.get('recordarme'))

    siguiente = destino_seguro(request.form.get('next') or request.args.get('next'))
    return redirect(siguiente or pagina_inicial(usuario))


@auth_bp.route('/cerrar-sesion', methods=['POST'])
def cerrar_sesion():
    session.clear()
    return redirect(url_for('home.index'))
