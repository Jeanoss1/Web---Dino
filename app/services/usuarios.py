"""Alta y gestión de cuentas (registro de clientes y administración de personal)."""
from werkzeug.security import generate_password_hash

from app.database import db
from app.models.Cajero import HORAS_POR_TIPO, Cajero
from app.models.Cliente import Cliente
from app.models.Rol import Rol
from app.models.Sucursal import Sucursal
from app.models.usuario import Usuario
from app.services import validadores as v
from app.services.errores import ErrorNegocio

ROLES = ('cliente', 'cajero', 'administrador')


def _rol(nombre):
    rol = Rol.query.filter_by(nombre=nombre).first()
    if rol is None:
        rol = Rol(nombre=nombre, descripcion=nombre.capitalize())
        db.session.add(rol)
        db.session.flush()
    return rol


def _correo_libre(correo):
    if Usuario.query.filter_by(correo=correo).first():
        raise ErrorNegocio('Ya existe una cuenta con ese correo.')


def registrar_cliente(f):
    """Registro público: SIEMPRE crea un usuario con rol cliente."""
    nombres = v.texto(f.get('nombres'), 'nombres')
    apellidos = v.texto(f.get('apellidos'), 'apellidos')
    dni = v.documento(f.get('dni'))
    tel = v.telefono(f.get('telefono'))
    correo = v.correo(f.get('correo'))
    if correo != (f.get('confirmar_correo') or '').strip().lower():
        raise ErrorNegocio('Los correos no coinciden.')
    clave = v.contrasena(f.get('contrasena'))
    if clave != f.get('confirmar_contrasena'):
        raise ErrorNegocio('Las contraseñas no coinciden.')
    if not f.get('terminos') or not f.get('declaracion'):
        raise ErrorNegocio('Debes aceptar los términos y la declaración.')
    _correo_libre(correo)
    if Cliente.query.filter_by(dni=dni).first():
        raise ErrorNegocio('Ya existe una cuenta con ese documento.')

    usuario = Usuario(
        nombre=nombres, apellido=apellidos, correo=correo, estado=True,
        contrasena=generate_password_hash(clave), id_rol=_rol('cliente').id_rol,
    )
    usuario.cliente = Cliente(
        nombre=nombres, apellido=apellidos, dni=dni, telefono=tel, correo=correo,
    )
    db.session.add(usuario)
    db.session.commit()
    return usuario


def crear_personal(f):
    """El administrador crea cajeros u otros administradores."""
    rol = (f.get('rol') or '').strip()
    if rol not in ('cajero', 'administrador'):
        raise ErrorNegocio('El rol debe ser cajero o administrador.')
    correo = v.correo(f.get('correo'))
    _correo_libre(correo)
    usuario = Usuario(
        nombre=v.texto(f.get('nombre'), 'nombre'), apellido=v.texto(f.get('apellido'), 'apellido'),
        correo=correo, estado=True, id_rol=_rol(rol).id_rol,
        contrasena=generate_password_hash(v.contrasena(f.get('contrasena'))),
    )
    if rol == 'cajero':
        tipo = f.get('tipo_turno')
        if tipo not in HORAS_POR_TIPO:
            raise ErrorNegocio('El tipo de turno debe ser completo o medio.')
        sede = db.session.get(Sucursal, v.entero(f.get('id_sucursal'), 'sede', 1, 10**9))
        if sede is None:
            raise ErrorNegocio('La sede no existe.')
        usuario.cajero = Cajero(id_sucursal=sede.id_sucursal, tipo_turno=tipo, estado='activo')
    db.session.add(usuario)
    db.session.commit()
    return usuario


def _usuario(id_usuario):
    usuario = db.session.get(Usuario, id_usuario)
    if usuario is None:
        raise ErrorNegocio('Usuario no encontrado.', 404)
    return usuario


def cambiar_estado(id_usuario, id_admin):
    usuario = _usuario(id_usuario)
    if usuario.id_usuario == id_admin:
        raise ErrorNegocio('No puedes desactivar tu propia cuenta.')
    usuario.estado = not usuario.estado
    if usuario.cajero:
        usuario.cajero.estado = 'activo' if usuario.estado else 'inactivo'
    db.session.commit()
    return usuario


def resetear_contrasena(id_usuario, nueva):
    usuario = _usuario(id_usuario)
    usuario.contrasena = generate_password_hash(v.contrasena(nueva))
    db.session.commit()
    return usuario


def actualizar_cajero(id_usuario, id_sucursal, tipo_turno):
    from app.services.cajas import caja_abierta
    usuario = _usuario(id_usuario)
    if usuario.cajero is None:
        raise ErrorNegocio('El usuario no es cajero.')
    if tipo_turno not in HORAS_POR_TIPO:
        raise ErrorNegocio('El tipo de turno debe ser completo o medio.')
    sede = db.session.get(Sucursal, v.entero(id_sucursal, 'sede', 1, 10**9))
    if sede is None:
        raise ErrorNegocio('La sede no existe.')
    if sede.id_sucursal != usuario.cajero.id_sucursal and caja_abierta(usuario.id_usuario):
        raise ErrorNegocio('El cajero tiene una caja abierta; debe cerrarla antes de cambiar de sede.')
    usuario.cajero.id_sucursal = sede.id_sucursal
    usuario.cajero.tipo_turno = tipo_turno
    db.session.commit()
