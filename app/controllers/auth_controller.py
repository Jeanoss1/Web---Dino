from flask import (
    Blueprint,
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

from app.database import db
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

    confirmar_correo = f.get(
        'confirmar_correo',
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

    elif correo != confirmar_correo:
        error = 'Los correos no coinciden.'

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

    session.permanent = bool(
        request.form.get('recordarme')
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


@auth_bp.route('/cerrar-sesion')
def cerrar_sesion():

    session.clear()

    return redirect(
        url_for('home.index')
    )