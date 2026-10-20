"""Crea una cuenta de administrador por consola.

Usa la misma conexión a la BD (DATABASE_URL) y el mismo hash de contraseña
(werkzeug.security, igual que auth_controller.py) que el resto de la app.

Uso:
    python crear_admin.py
"""
import sys
from getpass import getpass

from werkzeug.security import generate_password_hash

from app import create_app
from app.database import db
from app.models.Rol import Rol
from app.models.usuario import Usuario


def pedir_no_vacio(etiqueta):
    while True:
        valor = input(etiqueta).strip()
        if valor:
            return valor
        print('Este dato no puede estar vacío.')


def pedir_clave():
    while True:
        clave = getpass('Contraseña: ')
        if len(clave) < 8:
            print('La contraseña debe tener al menos 8 caracteres.')
            continue
        if clave != getpass('Repite la contraseña: '):
            print('Las contraseñas no coinciden.')
            continue
        return clave


def main():
    app = create_app({'SEMBRAR_DATOS': False})

    with app.app_context():
        rol_admin = Rol.query.filter_by(nombre='administrador').first()
        if rol_admin is None:
            print('FALLO: no existe el rol "administrador" en la BD.')
            sys.exit(1)

        print('=== Crear cuenta de administrador ===')
        nombre = pedir_no_vacio('Nombre: ')
        apellido = pedir_no_vacio('Apellido: ')
        correo = pedir_no_vacio('Correo: ').strip().lower()

        if Usuario.query.filter_by(correo=correo).first():
            print(f'Ya existe una cuenta con el correo {correo}; no se creó nada.')
            sys.exit(1)

        contrasena = pedir_clave()

        usuario = Usuario(
            nombre=nombre, apellido=apellido, correo=correo,
            contrasena=generate_password_hash(contrasena),
            estado=True, id_rol=rol_admin.id_rol,
        )
        db.session.add(usuario)
        db.session.commit()

        print(f'Administrador creado: {correo} (id_usuario={usuario.id_usuario})')


if __name__ == '__main__':
    main()
