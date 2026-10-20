"""Inicio de sesión y registro con Google (OAuth 2.0 con Authlib).

Las credenciales se leen del .env:
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
Si faltan, el acceso con Google queda desactivado.
"""
from authlib.integrations.flask_client import OAuth

oauth = OAuth()

PROVEEDORES = {
    'google': {
        'server_metadata_url': 'https://accounts.google.com/.well-known/openid-configuration',
        'client_kwargs': {'scope': 'openid email profile'},
    },
}


def registrar_proveedores(app):
    oauth.init_app(app)
    for nombre, opciones in PROVEEDORES.items():
        clave = nombre.upper()
        if app.config.get(f'{clave}_CLIENT_ID') and app.config.get(f'{clave}_CLIENT_SECRET'):
            oauth.register(nombre, overwrite=True, **opciones)


def cliente_oauth(nombre):
    """El cliente de Authlib del proveedor, o None si no está configurado."""
    return oauth.create_client(nombre) if nombre in PROVEEDORES else None


def perfil_del_proveedor(nombre, cliente):
    """Canjea el código que devuelve el proveedor y retorna sus datos:
    {'correo', 'nombre', 'apellido', 'foto'}. 'correo' puede venir vacío."""
    token = cliente.authorize_access_token()

    # Authlib ya validó el id_token (firma, audiencia y nonce)
    datos = token.get('userinfo') or cliente.userinfo()
    correo = datos.get('email') if datos.get('email_verified') else None
    return {
        'correo': correo,
        'nombre': datos.get('given_name') or datos.get('name'),
        'apellido': datos.get('family_name'),
        'foto': datos.get('picture'),
    }
