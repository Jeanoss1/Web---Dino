import secrets

from authlib.integrations.base_client import OAuthError
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)

from app.controllers.decoradores import login_requerido
from app.database import db
from app.oauth import cliente_oauth, perfil_del_proveedor
from app.models.Cliente import Cliente
from app.models.Rol import Rol
from app.models.usuario import Usuario


auth_bp = Blueprint(
    'auth',
    __name__
)


def _obtener_rol_cliente():

    rol = Rol.query.filter_by(
        nombre='cliente'
    ).first()

    if rol is None:
        rol = Rol(
            nombre='cliente',
            descripcion='Cliente del parque'
        )

        db.session.add(rol)
        db.session.flush()

    return rol


@auth_bp.route(
    '/registro',
    methods=['GET', 'POST']
)
def registro():

    if request.method == 'GET':
        return render_template(
            'registro.html'
        )

    f = request.form

    nombres = f.get(
        'nombres',
        ''
    ).strip()

    apellidos = f.get(
        'apellidos',
        ''
    ).strip()

    dni = f.get(
        'dni',
        ''
    ).strip()

    telefono = f.get(
        'telefono',
        ''
    ).strip()

    correo = f.get(
        'correo',
        ''
    ).strip().lower()

    contrasena = f.get(
        'contrasena',
        ''
    )

    confirmar_contrasena = f.get(
        'confirmar_contrasena',
        ''
    )

    error = None

    if not all([
        nombres,
        apellidos,
        dni,
        telefono,
        correo,
        contrasena
    ]):
        error = (
            'Completa todos los campos obligatorios.'
        )

    elif contrasena != confirmar_contrasena:
        error = (
            'Las contraseñas no coinciden.'
        )

    elif len(contrasena) < 8:
        error = (
            'La contraseña debe tener al menos 8 caracteres.'
        )

    elif (
        not f.get('terminos')
        or not f.get('declaracion')
    ):
        error = (
            'Debes aceptar los términos y la declaración.'
        )

    elif Usuario.query.filter_by(
        correo=correo
    ).first():
        error = (
            'Ya existe una cuenta con ese correo.'
        )

    elif Cliente.query.filter_by(
        dni=dni
    ).first():
        error = (
            'Ya existe una cuenta con ese documento.'
        )

    if error:

        flash(
            error,
            'error'
        )

        return render_template(
            'registro.html'
        ), 400

    rol = _obtener_rol_cliente()

    usuario = Usuario(
        nombre=nombres,
        apellido=apellidos,
        correo=correo,
        contrasena=generate_password_hash(
            contrasena
        ),
        estado=True,
        id_rol=rol.id_rol
    )

    cliente = Cliente(
        nombre=nombres,
        apellido=apellidos,
        dni=dni,
        telefono=telefono,
        correo=correo
    )

    db.session.add_all([
        usuario,
        cliente
    ])

    db.session.commit()

    flash(
        '¡Cuenta creada! Ya puedes iniciar sesión.',
        'exito'
    )

    return redirect(
        url_for('auth.iniciar_sesion')
    )


@auth_bp.route(
    '/iniciar-sesion',
    methods=['GET', 'POST']
)
def iniciar_sesion():

    if request.method == 'GET':
        return render_template(
            'iniciar_sesion.html'
        )

    identificador = request.form.get(
        'identificador',
        ''
    ).strip()

    contrasena = request.form.get(
        'contrasena',
        ''
    )

    # Se puede entrar con el correo o con el DNI
    if '@' in identificador:

        usuario = Usuario.query.filter_by(
            correo=identificador.lower()
        ).first()

    else:

        cliente = Cliente.query.filter_by(
            dni=identificador
        ).first()

        usuario = (
            Usuario.query.filter_by(
                correo=cliente.correo
            ).first()
            if cliente
            else None
        )

    if (
        usuario is None
        or not usuario.estado
        or not check_password_hash(
            usuario.contrasena,
            contrasena
        )
    ):

        flash(
            'Correo/DNI o contraseña incorrectos.',
            'error'
        )

        return render_template(
            'iniciar_sesion.html'
        ), 401

    return _abrir_sesion(
        usuario,
        recordar=bool(request.form.get('recordarme'))
    )


def _abrir_sesion(usuario, recordar):
    """Guarda al usuario en la sesión y lo lleva a su pantalla."""

    session.clear()

    session['id_usuario'] = (
        usuario.id_usuario
    )

    session['nombre'] = (
        usuario.nombre
    )

    session['correo'] = (
        usuario.correo
    )

    session['rol'] = (
        usuario.rol.nombre
        if usuario.rol
        else None
    )

    session['foto'] = usuario.foto_url

    session.permanent = recordar

    # Las cuentas creadas con Google aún no tienen DNI ni teléfono
    if (
        session['rol'] == 'cliente'
        and not Cliente.query.filter_by(correo=usuario.correo).first()
    ):
        session['perfil_incompleto'] = True
        return redirect(
            url_for('auth.completar_perfil')
        )

    # --------------------------------------------------------
    # REDIRECCIÓN SEGÚN ROL
    # --------------------------------------------------------
    # Los clientes van directo a la vista de disponibilidad
    # para reservar turnos. El personal (administrador/cajero)
    # sigue yendo al home general, a la espera de sus propios
    # paneles.
    # --------------------------------------------------------

    if session['rol'] == 'cliente':
        return redirect(
            url_for('reserva.disponibilidad')
        )

    if session['rol'] == 'cajero':
        return redirect(
            url_for('comprobante.pagina_validaciones')
        )

    return redirect(
        url_for('home.index')
    )


# ============================================================
# GOOGLE
# ============================================================
# /auth/google/ingresar   -> botón de "Iniciar sesión"
# /auth/google/registrar  -> botón de "Crear cuenta"
# ============================================================

ACCIONES = ('ingresar', 'registrar')
NOMBRE_PROVEEDOR = {'google': 'Google'}


@auth_bp.route('/auth/<proveedor>/<accion>')
def oauth_iniciar(proveedor, accion):

    if accion not in ACCIONES:
        abort(404)

    cliente = cliente_oauth(proveedor)
    volver = 'auth.registro' if accion == 'registrar' else 'auth.iniciar_sesion'

    if cliente is None:
        flash(
            f'El acceso con {NOMBRE_PROVEEDOR.get(proveedor, proveedor)} '
            'aún no está disponible.',
            'error'
        )
        return redirect(url_for(volver))

    session['oauth_accion'] = accion

    return cliente.authorize_redirect(
        url_for('auth.oauth_callback', proveedor=proveedor, _external=True)
    )


@auth_bp.route('/auth/<proveedor>/callback')
def oauth_callback(proveedor):

    cliente = cliente_oauth(proveedor)
    accion = session.pop('oauth_accion', 'ingresar')
    volver = 'auth.registro' if accion == 'registrar' else 'auth.iniciar_sesion'
    nombre_proveedor = NOMBRE_PROVEEDOR.get(proveedor, proveedor)

    if cliente is None:
        abort(404)

    try:
        perfil = perfil_del_proveedor(proveedor, cliente)
    except OAuthError:
        # El usuario canceló, o el código ya se usó / expiró
        flash(
            f'No se completó el acceso con {nombre_proveedor}. Inténtalo de nuevo.',
            'error'
        )
        return redirect(url_for(volver))

    correo = (perfil['correo'] or '').strip().lower()

    if not correo:
        flash(
            f'Tu cuenta de {nombre_proveedor} no comparte un correo verificado. '
            'Regístrate con el formulario.',
            'error'
        )
        return redirect(url_for('auth.registro'))

    usuario = Usuario.query.filter_by(correo=correo).first()

    # --------------------------------------------------------
    # INICIAR SESIÓN: el correo ya debe existir
    # --------------------------------------------------------

    if accion == 'ingresar' and usuario is None:
        flash(
            f'No hay una cuenta con el correo {correo}. '
            f'Créala con el botón de {nombre_proveedor}.',
            'error'
        )
        return redirect(url_for('auth.registro'))

    # --------------------------------------------------------
    # SOLO CLIENTES: el personal (Caja / Administrador) entra
    # siempre con su correo y contraseña
    # --------------------------------------------------------

    if usuario is not None and (not usuario.rol or usuario.rol.nombre != 'cliente'):
        flash(
            f'El acceso con {nombre_proveedor} es solo para clientes. '
            'El personal ingresa con su correo y contraseña.',
            'error'
        )
        return redirect(url_for('auth.iniciar_sesion'))

    # --------------------------------------------------------
    # REGISTRO: crea la cuenta con los datos autorizados
    # --------------------------------------------------------

    if usuario is None:

        nombre = (perfil['nombre'] or correo.split('@')[0])[:100]

        usuario = Usuario(
            nombre=nombre,
            apellido=(perfil['apellido'] or '')[:100],
            correo=correo,
            # Clave aleatoria que nadie conoce: esta cuenta entra
            # solo con Google
            contrasena=generate_password_hash(
                secrets.token_urlsafe(32)
            ),
            estado=True,
            id_rol=_obtener_rol_cliente().id_rol,
            proveedor=proveedor,
            foto_url=perfil['foto'],
        )

        db.session.add(usuario)
        db.session.commit()

        flash(
            f'¡Cuenta creada con {nombre_proveedor}!',
            'exito'
        )

    elif accion == 'registrar':
        flash(
            'Ya tenías una cuenta con ese correo: iniciamos tu sesión.',
            'exito'
        )

    if not usuario.estado:
        flash('Tu cuenta está desactivada.', 'error')
        return redirect(url_for('auth.iniciar_sesion'))

    # Mantiene al día la foto de perfil
    if perfil['foto'] and usuario.foto_url != perfil['foto']:
        usuario.foto_url = perfil['foto']
        db.session.commit()

    return _abrir_sesion(usuario, recordar=True)


# ============================================================
# COMPLETAR PERFIL (DNI y teléfono tras registrarse con Google)
# ============================================================

@auth_bp.route(
    '/completar-perfil',
    methods=['GET', 'POST']
)
@login_requerido
def completar_perfil():

    if not session.get('perfil_incompleto'):
        return redirect(url_for('reserva.disponibilidad'))

    if request.method == 'GET':
        return render_template('completar_perfil.html')

    dni = request.form.get('dni', '').strip()
    telefono = request.form.get('telefono', '').strip()

    error = None

    if not dni or not telefono:
        error = 'Completa tu DNI y tu teléfono.'

    elif not dni.isalnum() or not 8 <= len(dni) <= 12:
        error = 'El documento debe tener entre 8 y 12 letras o números.'

    elif len(telefono) > 15:
        error = 'El teléfono puede tener como máximo 15 caracteres.'

    elif Cliente.query.filter_by(dni=dni).first():
        error = 'Ya existe una cuenta con ese documento.'

    if error:
        flash(error, 'error')
        return render_template('completar_perfil.html'), 400

    usuario = db.session.get(Usuario, session['id_usuario'])

    db.session.add(
        Cliente(
            nombre=usuario.nombre,
            apellido=usuario.apellido,
            dni=dni,
            telefono=telefono,
            correo=usuario.correo
        )
    )
    db.session.commit()

    session.pop('perfil_incompleto', None)

    flash('¡Listo! Ya puedes reservar tus turnos.', 'exito')

    return redirect(url_for('reserva.disponibilidad'))


@auth_bp.route('/cerrar-sesion')
def cerrar_sesion():

    session.clear()

    return redirect(
        url_for('home.index')
    )